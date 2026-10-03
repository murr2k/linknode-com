#!/usr/bin/env python3
"""
Alert logic of the Pi-side watcher (no network).
Run: python -m unittest discover -s scripts -p "test_*.py"
"""

import json
import unittest
from unittest.mock import patch

import linknode_watchdog as wd

OK = {'ingest': None, 'site': None, 'api': None}


def down(**reasons):
    return dict(OK, **reasons)


class Sender:
    def __init__(self, accept=True):
        self.accept = accept
        self.sent = []

    def __call__(self, title, message, priority):
        self.sent.append((title, message, priority))
        return self.accept


class TestStep(unittest.TestCase):
    def run_passes(self, passes, send, state=None):
        state = state or {}
        for results in passes:
            state = wd.step(state, results, send)
        return state

    def test_healthy_passes_send_nothing_and_do_not_change_state(self):
        send = Sender()
        state = self.run_passes([OK], send)
        self.assertEqual(wd.step(state, OK, send), state)
        self.assertEqual(send.sent, [])

    def test_alerts_once_at_the_threshold(self):
        send = Sender()
        fail = down(ingest='no answer (timeout)')
        state = self.run_passes([fail, fail], send)
        self.assertEqual(send.sent, [])                       # a blip or a deploy restart
        state = self.run_passes([fail], send, state)
        self.assertEqual(len(send.sent), 1)
        title, message, priority = send.sent[0]
        self.assertIn('DOWN', title)
        self.assertIn('Ingest service: no answer (timeout)', message)
        self.assertEqual(priority, wd.PRIORITY)
        self.run_passes([fail, fail, fail], send, state)      # sustained outage: no repeats
        self.assertEqual(len(send.sent), 1)

    def test_a_recovery_in_between_resets_the_count(self):
        send = Sender()
        fail = down(site='HTTP 502')
        self.run_passes([fail, fail, OK, fail, fail], send)
        self.assertEqual(send.sent, [])

    def test_checks_failing_together_share_one_alert(self):
        send = Sender()
        fail = down(ingest='no answer (timeout)', api='no answer (timeout)')
        self.run_passes([fail, fail, fail], send)
        self.assertEqual(len(send.sent), 1)
        self.assertIn('Ingest service', send.sent[0][1])
        self.assertIn('Stats API', send.sent[0][1])

    def test_recovery_message_once_everything_alerted_is_back(self):
        send = Sender()
        both = down(ingest='x', api='x')
        state = self.run_passes([both, both, both], send)
        state = self.run_passes([down(api='x')], send, state)  # one back, one still down
        self.assertEqual(len(send.sent), 1)
        state = self.run_passes([OK], send, state)
        self.assertEqual(len(send.sent), 2)
        self.assertIn('recovered', send.sent[1][0])
        self.assertEqual(send.sent[1][2], 0)
        self.run_passes([OK, OK], send, state)
        self.assertEqual(len(send.sent), 2)

    def test_an_alert_that_could_not_be_sent_is_retried(self):
        refused = Sender(accept=False)
        fail = down(ingest='no answer')
        state = self.run_passes([fail, fail, fail, fail], refused)
        self.assertEqual(len(refused.sent), 2)                # tried on pass 3 and again on 4
        send = Sender()
        self.run_passes([fail, fail], send, state)
        self.assertEqual(len(send.sent), 1)


class TestChecks(unittest.TestCase):
    def fetch(self, status, body, headers=None):
        return patch.object(wd, 'fetch', return_value=(status, headers or {}, body))

    def test_ingest(self):
        with self.fetch(200, json.dumps({'status': 'fresh', 'reading_age_seconds': 20})):
            self.assertIsNone(wd.check_ingest())
        # Stale but alive: the ingester raises that alarm itself
        with self.fetch(503, json.dumps({'status': 'stale', 'reading_age_seconds': 400})):
            self.assertIsNone(wd.check_ingest())
        with self.fetch(503, json.dumps({'status': 'stale', 'reading_age_seconds': 1800})):
            self.assertEqual(wd.check_ingest(), 'newest reading is 30 min old')
        with self.fetch(None, 'URLError: timed out'):
            self.assertIn('no answer', wd.check_ingest())
        with self.fetch(502, '<html>bad gateway</html>'):
            self.assertIn('HTTP 502', wd.check_ingest())

    def test_site(self):
        with self.fetch(200, '<div id="power-chart"></div>'):
            self.assertIsNone(wd.check_site())
        with self.fetch(200, '<html>parked</html>'):
            self.assertIn('markup', wd.check_site())
        with self.fetch(522, ''):
            self.assertEqual(wd.check_site(), 'HTTP 522')

    def test_api(self):
        cors = {'Access-Control-Allow-Origin': wd.SITE_URL}
        with self.fetch(200, json.dumps({'current_power': 355.0}), cors):
            self.assertIsNone(wd.check_api())
        with self.fetch(200, json.dumps({'current_power': 355.0})):
            self.assertIn('CORS', wd.check_api())
        with self.fetch(200, json.dumps({'current_power': None}), cors):
            self.assertIn('current_power', wd.check_api())


if __name__ == '__main__':
    unittest.main()
