#!/usr/bin/env python3
"""
Tests for the outage alerting: the siren's delivery (retry, reminder, refusal), the
frozen-register rule, the watchdog liveness check, and their wiring in app.py.
Run: python -m unittest discover -s fly/eagle-monitor -p "test_*.py"

Nothing here reaches Pushover or Slack: requests.post is replaced in every test.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import requests

os.environ.pop('EAGLE_PASSWORD', None)  # Basic auth off for the webhook tests
import app as monitor_app  # noqa: E402
import monitor_data_staleness as mds  # noqa: E402
from monitor_data_staleness import DataStalenessMonitor, WatchdogLiveness  # noqa: E402

T0 = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
MIN = timedelta(minutes=1)
HOUR = timedelta(hours=1)
SLACK_URL = 'https://hooks.slack.com/services/T000/B000/SECRETPATH'
WATCHDOG_UA = {'User-Agent': 'linknode-watchdog/1.0'}


class FakePosts:
    """Stands in for requests.post. Records every request and answers Pushover and
    Slack with the status set on it ('down' raises a connection error)."""

    def __init__(self):
        self.pushover_status = 200
        self.slack_status = 200
        self.pushover = []   # form payloads
        self.slack = []      # json payloads

    def __call__(self, url, **kwargs):
        if 'pushover' in url:
            self.pushover.append(kwargs['data'])
            status = self.pushover_status
        else:
            self.slack.append(kwargs['json'])
            status = self.slack_status
        if status == 'down':
            raise requests.ConnectionError(f"could not reach {url}")
        response = MagicMock()
        response.status_code = status
        if status >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(
                f"{status} Client Error for url: {url}", response=response)
        return response

    def sirens(self):
        return [p for p in self.pushover if p['priority'] == 2]

    def normal(self):
        return [p for p in self.pushover if p['priority'] == 0]


class AlertTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_file = os.path.join(self.tmp, 'state.json')
        self.posts = FakePosts()
        patcher = patch('monitor_data_staleness.requests.post', side_effect=self.posts)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def make(self, **kwargs):
        args = dict(state_file=self.state_file, slack_webhook=SLACK_URL,
                    pushover_token='T' * 30, pushover_user='U' * 30, stale_threshold_minutes=5)
        args.update(kwargs)
        return DataStalenessMonitor(**args)

    @staticmethod
    def stale(now):
        return {'last_data_received': (now - 10 * MIN).isoformat(), 'last_power_reading': 422.0}

    @staticmethod
    def fresh(now, **extra):
        return dict({'last_data_received': (now - 20 * timedelta(seconds=1)).isoformat(),
                     'last_power_reading': 422.0}, **extra)

    def saved(self):
        with open(self.state_file) as f:
            return json.load(f)


class TestSirenDelivery(AlertTestCase):
    def test_siren_is_retried_until_accepted_and_slack_is_posted_once(self):
        m = self.make()
        self.posts.pushover_status = 'down'
        m.check_data_freshness(self.stale(T0), now=T0)
        m.check_data_freshness(self.stale(T0 + 5 * MIN), now=T0 + 5 * MIN)
        self.assertFalse(m.siren_accepted)
        self.assertFalse(self.saved()['siren_accepted'])

        self.posts.pushover_status = 200
        m.check_data_freshness(self.stale(T0 + 10 * MIN), now=T0 + 10 * MIN)
        m.check_data_freshness(self.stale(T0 + 15 * MIN), now=T0 + 15 * MIN)

        self.assertEqual(len(self.posts.sirens()), 3)     # two failures, then the one accepted
        self.assertEqual(len(self.posts.normal()), 0)
        self.assertEqual(len(self.posts.slack), 1)        # only the siren is retried
        self.assertTrue(self.saved()['siren_accepted'])
        self.assertEqual(self.saved()['last_message_at'], (T0 + 10 * MIN).isoformat())

    def test_restart_with_the_siren_undelivered_retries_it(self):
        self.posts.pushover_status = 503
        self.make().check_data_freshness(self.stale(T0), now=T0)
        self.posts.pushover_status = 200

        restarted = self.make()
        self.assertEqual(restarted.previous_status, 'unhealthy')
        status, transitioned = restarted.check_data_freshness(self.stale(T0 + 5 * MIN), now=T0 + 5 * MIN)

        self.assertEqual((status, transitioned), ('unhealthy', False))
        self.assertEqual(len(self.posts.sirens()), 2)
        self.assertEqual(len(self.posts.slack), 1)
        self.assertTrue(restarted.siren_accepted)

    def test_a_5xx_is_retried_at_the_next_run(self):
        m = self.make()
        self.posts.pushover_status = 500                  # the first status past the 4xx refusals
        m.check_data_freshness(self.stale(T0), now=T0)
        m.check_data_freshness(self.stale(T0 + 5 * MIN), now=T0 + 5 * MIN)
        self.assertEqual(len(self.posts.sirens()), 2)     # a 5xx is a failure, not a refusal
        self.posts.pushover_status = 200
        m.check_data_freshness(self.stale(T0 + 10 * MIN), now=T0 + 10 * MIN)
        self.assertEqual(len(self.posts.sirens()), 3)
        self.assertTrue(m.siren_accepted)

    def test_the_reminder_clock_survives_a_restart(self):
        self.make().check_data_freshness(self.stale(T0), now=T0)
        restarted = self.make()
        self.assertEqual(restarted.last_message_at, T0)
        self.assertEqual(restarted.status_since, T0)
        restarted.check_data_freshness(self.stale(T0 + 24 * HOUR), now=T0 + 24 * HOUR)
        self.assertEqual(len(self.posts.normal()), 1)     # 24 h after the siren, not after the restart
        self.assertEqual(self.saved()['last_message_at'], (T0 + 24 * HOUR).isoformat())
        self.assertEqual(self.saved()['timestamp'], T0.isoformat())   # still the change of state
        again = self.make()
        again.check_data_freshness(self.stale(T0 + 25 * HOUR), now=T0 + 25 * HOUR)
        self.assertEqual(len(self.posts.normal()), 1)     # not repeated by a restart

    def test_restart_with_the_siren_delivered_stays_quiet(self):
        self.make().check_data_freshness(self.stale(T0), now=T0)
        restarted = self.make()
        restarted.check_data_freshness(self.stale(T0 + 5 * MIN), now=T0 + 5 * MIN)
        self.assertEqual(len(self.posts.pushover), 1)
        self.assertEqual(len(self.posts.slack), 1)

    def test_a_second_outage_gets_a_second_siren(self):
        m = self.make()
        m.check_data_freshness(self.stale(T0), now=T0)
        m.check_data_freshness(self.fresh(T0 + HOUR), now=T0 + HOUR)
        m.check_data_freshness(self.stale(T0 + 2 * HOUR), now=T0 + 2 * HOUR)
        self.assertEqual(len(self.posts.sirens()), 2)
        self.assertEqual(len(self.posts.slack), 3)        # outage, recovery, outage

    def test_reminder_every_24_hours_at_priority_0(self):
        m = self.make()
        m.check_data_freshness(self.stale(T0), now=T0)
        m.check_data_freshness(self.stale(T0 + 23 * HOUR + 55 * MIN), now=T0 + 23 * HOUR + 55 * MIN)
        self.assertEqual(len(self.posts.pushover), 1)

        m.check_data_freshness(self.stale(T0 + 24 * HOUR), now=T0 + 24 * HOUR)
        m.check_data_freshness(self.stale(T0 + 24 * HOUR + 5 * MIN), now=T0 + 24 * HOUR + 5 * MIN)
        self.assertEqual(len(self.posts.normal()), 1)
        self.assertEqual(self.saved()['last_message_at'], (T0 + 24 * HOUR).isoformat())
        reminder = self.posts.normal()[0]
        self.assertNotIn('retry', reminder)
        self.assertNotIn('sound', reminder)
        self.assertIn('Still down since 2026-10-03 12:00 UTC', reminder['message'])

        m.check_data_freshness(self.stale(T0 + 48 * HOUR), now=T0 + 48 * HOUR)
        self.assertEqual(len(self.posts.normal()), 2)
        self.assertEqual(len(self.posts.sirens()), 1)
        self.assertEqual(len(self.posts.slack), 1)        # reminders are Pushover only

    def test_no_reminder_after_a_recovery(self):
        m = self.make()
        m.check_data_freshness(self.stale(T0), now=T0)
        m.check_data_freshness(self.fresh(T0 + HOUR), now=T0 + HOUR)
        m.check_data_freshness(self.fresh(T0 + 30 * HOUR), now=T0 + 30 * HOUR)
        self.assertEqual(len(self.posts.pushover), 1)
        self.assertFalse(self.saved()['siren_accepted'])

    def test_a_reminder_that_fails_is_tried_again_at_the_next_run(self):
        m = self.make()
        m.check_data_freshness(self.stale(T0), now=T0)
        self.posts.pushover_status = 'down'
        m.check_data_freshness(self.stale(T0 + 24 * HOUR), now=T0 + 24 * HOUR)
        self.posts.pushover_status = 200
        m.check_data_freshness(self.stale(T0 + 24 * HOUR + 5 * MIN), now=T0 + 24 * HOUR + 5 * MIN)
        m.check_data_freshness(self.stale(T0 + 24 * HOUR + 10 * MIN), now=T0 + 24 * HOUR + 10 * MIN)
        self.assertEqual(len(self.posts.normal()), 2)     # one failed, one accepted, then quiet

    def test_a_4xx_holds_off_for_24_hours_and_the_next_outage_asks_again(self):
        m = self.make()
        self.posts.pushover_status = 400
        m.check_data_freshness(self.stale(T0), now=T0)
        for minutes in (5, 10, 600, 1435):
            m.check_data_freshness(self.stale(T0 + minutes * MIN), now=T0 + minutes * MIN)
        self.assertEqual(len(self.posts.pushover), 1)     # no second request inside the hold
        self.assertFalse(self.saved()['siren_accepted'])  # a refusal is not a delivery

        self.posts.pushover_status = 429                  # over the quota: a refusal too
        m.check_data_freshness(self.stale(T0 + 24 * HOUR), now=T0 + 24 * HOUR)
        self.assertEqual(len(self.posts.sirens()), 2)     # one more once it has passed: the siren, not a reminder
        m.check_data_freshness(self.stale(T0 + 24 * HOUR + 5 * MIN), now=T0 + 24 * HOUR + 5 * MIN)
        self.assertEqual(len(self.posts.pushover), 2)     # and held again
        self.assertFalse(m.siren_accepted)

        # A recovery and a new outage: asked again at once, not after the hold
        m.check_data_freshness(self.fresh(T0 + 25 * HOUR), now=T0 + 25 * HOUR)
        m.check_data_freshness(self.stale(T0 + 26 * HOUR), now=T0 + 26 * HOUR)
        self.assertEqual(len(self.posts.pushover), 3)

    def test_unset_credentials_send_nothing_and_do_not_raise(self):
        m = self.make(pushover_token=None, pushover_user=None)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('PUSHOVER_API_TOKEN', None)
            os.environ.pop('PUSHOVER_USER_KEY', None)
            m.pushover_token = m.pushover_user = None
            m.check_data_freshness(self.stale(T0), now=T0)
            m.check_data_freshness(self.stale(T0 + 5 * MIN), now=T0 + 5 * MIN)
        self.assertEqual(self.posts.pushover, [])
        self.assertEqual(len(self.posts.slack), 1)

    def test_state_file_in_the_old_format_saying_healthy(self):
        with open(self.state_file, 'w') as f:
            json.dump({'status': 'healthy', 'timestamp': (T0 - HOUR).isoformat()}, f)
        m = self.make()
        m.check_data_freshness(self.stale(T0), now=T0)
        self.assertEqual(len(self.posts.sirens()), 1)

    def test_state_file_in_the_old_format_saying_unhealthy(self):
        # Written by the code before the siren was tracked: that code announced the
        # outage, so a deploy in the middle of it must not sound the siren again.
        with open(self.state_file, 'w') as f:
            json.dump({'status': 'unhealthy', 'timestamp': T0.isoformat()}, f)
        m = self.make()
        self.assertTrue(m.siren_accepted)
        m.check_data_freshness(self.stale(T0 + HOUR), now=T0 + HOUR)
        self.assertEqual(self.posts.pushover, [])
        self.assertEqual(self.posts.slack, [])

        m.check_data_freshness(self.stale(T0 + 24 * HOUR), now=T0 + 24 * HOUR)
        self.assertEqual(len(self.posts.normal()), 1)     # the first reminder, 24 h after that time
        self.assertEqual(len(self.posts.sirens()), 0)

    def test_state_file_with_an_unknown_status_is_read_as_healthy(self):
        for content in ('{"status": null}', '{"status": "broken"}', 'not json', ''):
            with open(self.state_file, 'w') as f:
                f.write(content)
            self.assertEqual(self.make().previous_status, 'healthy', content)

    def test_a_failed_slack_send_does_not_log_the_webhook(self):
        m = self.make()
        self.posts.slack_status = 404
        with self.assertLogs('monitor_data_staleness', level='ERROR') as logs:
            m.check_data_freshness(self.stale(T0), now=T0)
        text = '\n'.join(logs.output)
        self.assertIn('Failed to send Slack alert', text)
        self.assertNotIn('SECRETPATH', text)
        self.assertNotIn('hooks.slack.com', text)
        self.assertEqual(len(self.posts.sirens()), 1)     # the siren does not depend on Slack


class TestFrozenRegister(AlertTestCase):
    def test_fresh_readings_with_an_unchanged_register_are_unhealthy(self):
        m = self.make()
        stats = self.fresh(T0, register_now=94917.107, register_then=94917.107)
        status, transitioned = m.check_data_freshness(stats, now=T0)
        self.assertEqual((status, transitioned), ('unhealthy', True))
        message = self.posts.sirens()[0]['message']
        self.assertTrue(message.startswith('Meter readings look frozen!'), message)
        self.assertIn('has not changed in over 2 hours', message)
        self.assertNotIn('Data is not arriving', message)
        self.assertIn('Meter readings look frozen!', self.posts.slack[0]['text'])

    def test_a_register_that_moves_is_healthy(self):
        # Up, up by 0.001 kWh, and down (a meter swap): only the same value is frozen.
        for now_value, then_value in ((94917.2, 94916.0), (94917.108, 94917.107), (12.345, 94917.107)):
            m = self.make()
            stats = self.fresh(T0, register_now=now_value, register_then=then_value)
            self.assertEqual(m.check_data_freshness(stats, now=T0), ('healthy', False))

    def test_no_verdict_without_both_values(self):
        m = self.make()
        for now_value, then_value in ((None, None), (94917.1, None), (None, 94917.1)):
            stats = self.fresh(T0, register_now=now_value, register_then=then_value)
            self.assertEqual(m._evaluate_health(stats, T0), 'healthy')
        self.assertEqual(m._evaluate_health(self.fresh(T0), T0), 'healthy')   # keys absent

    def test_a_stale_feed_keeps_the_stale_text_even_when_the_register_matches(self):
        m = self.make()
        stats = dict(self.stale(T0), register_now=94917.1, register_then=94917.1)
        m.check_data_freshness(stats, now=T0)
        message = self.posts.sirens()[0]['message']
        self.assertTrue(message.startswith('Data is not arriving from power meter!'), message)
        self.assertIn('minutes ago', message)
        self.assertNotIn('frozen', message)

    def test_the_zero_rule_comes_before_the_register_rule(self):
        m = self.make()
        stats = self.fresh(T0, register_now=1.0, register_then=1.0)
        stats['last_power_reading'] = 0
        self.assertIn('Invalid power reading', m._get_failure_reason(stats, T0))

    def test_a_register_that_sat_still_through_a_short_outage_is_not_frozen(self):
        # A power cut of just under 2 hours: the house drew nothing, so the register is
        # where it was. Once the feed is back the 2-hour lookup reaches the last row
        # before the cut, which holds the same value. That is not a frozen register.
        m = self.make(stale_threshold_minutes=30)
        gone = {'last_data_received': T0.isoformat(), 'last_power_reading': 422.0,
                'register_now': 5.0, 'register_then': 4.9}
        m.check_data_freshness(gone, now=T0 + 35 * MIN)
        back = T0 + 115 * MIN
        self.assertEqual(m.check_data_freshness(
            self.fresh(back, register_now=5.0, register_then=4.9), now=back), ('healthy', True))
        for minutes in (5, 10, 60, 119):
            when = back + minutes * MIN
            self.assertEqual(m.check_data_freshness(
                self.fresh(when, register_now=5.0, register_then=5.0), now=when), ('healthy', False))
        self.assertEqual(len(self.posts.sirens()), 1)     # the outage's own, and no more

        # Two hours after the recovery the rule applies again
        when = back + 2 * HOUR
        self.assertEqual(m.check_data_freshness(
            self.fresh(when, register_now=5.0, register_then=5.0), now=when), ('unhealthy', True))
        self.assertIn('frozen', self.posts.sirens()[1]['message'])

    def test_frozen_after_an_outage_is_the_same_outage(self):
        # Readings stop (stale), then return with the register where it was: one state,
        # one siren, and the reminder a day later carries whichever text is true then.
        m = self.make()
        m.check_data_freshness(dict(self.stale(T0), register_now=5.0, register_then=5.0), now=T0)
        later = T0 + 3 * HOUR
        status, transitioned = m.check_data_freshness(
            self.fresh(later, register_now=5.0, register_then=5.0), now=later)
        self.assertEqual((status, transitioned), ('unhealthy', False))
        self.assertEqual(len(self.posts.sirens()), 1)
        self.assertIn('Data is not arriving', self.posts.sirens()[0]['message'])


class TestWatchdogLiveness(AlertTestCase):
    def setUp(self):
        super().setUp()
        self.kept = {}                       # stands in for the store's meta table
        self.monitor = self.make()

    def liveness(self, started=T0):
        return WatchdogLiveness(self.monitor, started=started,
                                load=lambda: self.kept.get('state'),
                                save=lambda state: self.kept.__setitem__('state', state))

    def test_silence_over_6_hours_sends_one_message(self):
        w = self.liveness()
        last_seen = T0
        for hours in (1, 3, 5.9):
            w.check(last_seen, 'healthy', now=T0 + hours * HOUR)
        self.assertEqual(self.posts.pushover, [])

        w.check(last_seen, 'healthy', now=T0 + 6 * HOUR)
        w.check(last_seen, 'healthy', now=T0 + 6 * HOUR + 5 * MIN)
        self.assertEqual(len(self.posts.normal()), 1)
        self.assertEqual(self.posts.sirens(), [])
        message = self.posts.normal()[0]
        self.assertEqual(message['title'], 'Linknode watchdog: silent')
        self.assertIn('No request from the Pi watchdog for over 6 hours', message['message'])
        self.assertTrue(self.kept['state']['alerted'])

    def test_message_is_retried_until_accepted(self):
        w = self.liveness()
        self.posts.pushover_status = 'down'
        w.check(T0, 'healthy', now=T0 + 6 * HOUR)
        w.check(T0, 'healthy', now=T0 + 6 * HOUR + 5 * MIN)
        self.assertFalse(w.alerted)
        self.posts.pushover_status = 200
        w.check(T0, 'healthy', now=T0 + 6 * HOUR + 10 * MIN)
        w.check(T0, 'healthy', now=T0 + 6 * HOUR + 15 * MIN)
        self.assertEqual(len(self.posts.normal()), 3)     # two failures, one accepted, then quiet
        self.assertTrue(w.alerted)

    def test_reminder_every_24_hours_while_the_silence_lasts(self):
        w = self.liveness()
        w.check(T0, 'healthy', now=T0 + 6 * HOUR)
        w.check(T0, 'healthy', now=T0 + 29 * HOUR)
        self.assertEqual(len(self.posts.normal()), 1)
        w.check(T0, 'healthy', now=T0 + 30 * HOUR)
        w.check(T0, 'healthy', now=T0 + 30 * HOUR + 5 * MIN)
        self.assertEqual(len(self.posts.normal()), 2)
        self.assertEqual(self.kept['state']['last_message_at'], (T0 + 30 * HOUR).isoformat())
        # A restart after the repeat: its time is in the store too, so it is not sent again
        self.liveness(started=T0 + 31 * HOUR).check(T0, 'healthy', now=T0 + 31 * HOUR + 5 * MIN)
        self.assertEqual(len(self.posts.normal()), 2)

    def test_quiet_while_the_feed_is_unhealthy(self):
        w = self.liveness()
        for hours in (6, 12, 30):
            w.check(T0, 'unhealthy', now=T0 + hours * HOUR)
        self.assertEqual(self.posts.pushover, [])

    def test_feed_recovers_before_the_watchdog_has_called(self):
        # The Pi was off for a day. Its uploader's first reading lands before the
        # watchdog's first request (its timer waits 3 minutes after boot): no message.
        w = self.liveness()
        w.check(T0, 'unhealthy', now=T0 + 24 * HOUR)
        w.check(T0, 'healthy', now=T0 + 24 * HOUR + 5 * MIN)
        self.assertEqual(self.posts.pushover, [])
        # and if it never calls again, the message comes 6 hours after that run
        w.check(T0, 'healthy', now=T0 + 30 * HOUR)
        self.assertEqual(len(self.posts.normal()), 1)

    def test_no_repeat_at_the_first_healthy_run_after_an_outage(self):
        # Already reported silent, then a feed outage that covers the time the repeat
        # falls due (30 h). The Pi is back and its watchdog has not called yet: no message.
        w = self.liveness()
        w.check(T0, 'healthy', now=T0 + 6 * HOUR)
        for minutes in range(0, 125, 5):
            w.check(T0, 'unhealthy', now=T0 + 29 * HOUR + minutes * MIN)
        w.check(T0, 'healthy', now=T0 + 31 * HOUR + 5 * MIN)
        self.assertEqual(len(self.posts.normal()), 1)
        # and if it never calls again, the repeat comes 6 hours after the last unhealthy run
        w.check(T0, 'healthy', now=T0 + 37 * HOUR)
        self.assertEqual([p['title'] for p in self.posts.normal()], ['Linknode watchdog: silent'] * 2)

    def test_the_next_request_sends_one_recovery_message(self):
        w = self.liveness()
        w.check(T0, 'healthy', now=T0 + 6 * HOUR)
        called = T0 + 7 * HOUR
        w.check(called, 'healthy', now=called + MIN)
        w.check(called + 5 * MIN, 'healthy', now=called + 6 * MIN)
        titles = [p['title'] for p in self.posts.normal()]
        self.assertEqual(titles, ['Linknode watchdog: silent', 'Linknode watchdog: calling again'])
        self.assertFalse(self.kept['state']['alerted'])

    def test_recovery_message_is_tried_once(self):
        w = self.liveness()
        w.check(T0, 'healthy', now=T0 + 6 * HOUR)
        self.posts.pushover_status = 'down'
        called = T0 + 7 * HOUR
        w.check(called, 'healthy', now=called + MIN)
        self.posts.pushover_status = 200
        w.check(called + 5 * MIN, 'healthy', now=called + 6 * MIN)
        self.assertEqual(len(self.posts.normal()), 2)     # the alert, and one failed recovery
        self.assertFalse(w.alerted)

    def test_nothing_saved_counts_from_the_service_start(self):
        w = self.liveness(started=T0)
        w.check(None, 'healthy', now=T0 + 5 * MIN)        # the first run: nothing
        w.check(None, 'healthy', now=T0 + 5 * HOUR)
        self.assertEqual(self.posts.pushover, [])
        w.check(None, 'healthy', now=T0 + 6 * HOUR)
        self.assertEqual(len(self.posts.normal()), 1)
        self.assertIn('has not called since this service started', self.posts.normal()[0]['message'])

    def test_a_restart_before_the_message_does_not_restart_the_6_hours(self):
        self.liveness(started=T0)                          # the first deploy: nothing saved yet
        self.assertEqual(self.kept['state']['silence_from'], T0.isoformat())

        restarted = self.liveness(started=T0 + 3 * HOUR)   # a second deploy, 3 hours later
        restarted.check(None, 'healthy', now=T0 + 5 * HOUR + 55 * MIN)
        self.assertEqual(self.posts.pushover, [])
        restarted.check(None, 'healthy', now=T0 + 6 * HOUR)
        self.assertEqual(len(self.posts.normal()), 1)      # 6 hours after the first start

    def test_a_saved_state_that_is_not_an_object_is_ignored(self):
        for saved in ([1], 'x', 5, True):
            w = WatchdogLiveness(self.monitor, started=T0, load=lambda: saved)
            self.assertEqual(w.silence_from, T0)
            self.assertFalse(w.alerted)

    def test_a_restart_during_the_silence_does_not_send_again(self):
        self.liveness().check(T0, 'healthy', now=T0 + 6 * HOUR)
        restarted = self.liveness(started=T0 + 7 * HOUR)
        self.assertTrue(restarted.alerted)
        restarted.check(T0, 'healthy', now=T0 + 7 * HOUR + 5 * MIN)
        self.assertEqual(len(self.posts.normal()), 1)

    def test_a_save_that_fails_does_not_raise(self):
        def broken(state):
            raise OSError('database is locked')
        w = WatchdogLiveness(self.monitor, started=T0, save=broken)
        w.check(T0, 'unhealthy', now=T0 + HOUR)
        w.check(T0, 'healthy', now=T0 + 8 * HOUR)
        self.assertEqual(len(self.posts.normal()), 1)


class TestWiring(AlertTestCase):
    """The job and the routes in app.py, against a temporary store."""

    def setUp(self):
        super().setUp()
        self.monitor = self.make(slack_webhook=None)
        patcher = patch.object(monitor_app, 'monitor', self.monitor)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.db_path = os.path.join(self.tmp, 'energy.db')
        self.assertTrue(monitor_app.init_store(self.db_path))
        monitor_app.stats.update({'last_data_received': None, 'last_power_reading': None,
                                  'bypass_status': None})
        self.client = monitor_app.app.test_client()
        self.now_ms = int(time.time() * 1000)

    def write(self, seconds_ago, **fields):
        monitor_app.db.write(self.now_ms - int(seconds_ago * 1000), fields)

    def feed(self, hours, register):
        """A reading every 5 minutes over the last `hours`; register(seconds_ago) gives
        the kWh value, or None for a cycle that carries no register row."""
        for seconds_ago in range(int(hours * 3600), 0, -300):
            fields = {'power_w': 500.0}
            value = register(seconds_ago)
            if value is not None:
                fields['energy_delivered_kwh'] = value
            self.write(seconds_ago, **fields)
        self.write(20, power_w=500.0)

    def test_new_timestamps_with_an_unchanged_register_raise_the_alarm(self):
        self.feed(2.1, lambda seconds_ago: 94917.107)     # just past the 2 hours
        monitor_app.check_data_health()
        self.assertEqual(self.monitor.previous_status, 'unhealthy')
        self.assertTrue(self.posts.sirens()[0]['message'].startswith('Meter readings look frozen!'))
        r = self.client.get('/health/data')               # the endpoint is not changed by this rule
        self.assertEqual((r.status_code, r.get_json()['status']), (200, 'fresh'))

    def test_power_arriving_with_no_register_row_for_over_2_hours_raises_it_too(self):
        self.write(30 * 3600, energy_delivered_kwh=94917.107)   # the last register row, however old
        self.feed(3, lambda seconds_ago: None)
        monitor_app.check_data_health()
        self.assertEqual(self.monitor.previous_status, 'unhealthy')
        self.assertIn('frozen', self.posts.sirens()[0]['message'])

    def test_a_register_that_moves_is_healthy(self):
        self.feed(3, lambda seconds_ago: 94917.0 + (10800 - seconds_ago) / 3600.0)
        monitor_app.check_data_health()
        self.assertEqual(self.monitor.previous_status, 'healthy')
        self.assertEqual(self.posts.pushover, [])

    def test_a_store_too_new_to_judge_gives_no_verdict(self):
        self.feed(1.9, lambda seconds_ago: 94917.107)     # nothing from 2 hours ago
        monitor_app.check_data_health()
        self.assertEqual(self.monitor.previous_status, 'healthy')

    def test_an_outage_then_a_first_reading_with_the_register_unchanged_is_one_siren(self):
        for seconds_ago in range(5 * 3600, 3 * 3600, -300):
            self.write(seconds_ago, power_w=500.0, energy_delivered_kwh=94917.107)
        monitor_app.check_data_health()                   # 3 hours stale
        self.assertIn('Data is not arriving', self.posts.sirens()[0]['message'])

        self.write(20, power_w=500.0, energy_delivered_kwh=94917.107)   # e.g. after a power cut
        monitor_app.check_data_health()
        self.assertEqual(self.monitor.previous_status, 'unhealthy')
        self.assertEqual(len(self.posts.sirens()), 1)

        self.write(10, power_w=500.0, energy_delivered_kwh=94917.207)   # the register moves
        monitor_app.check_data_health()
        self.assertEqual(self.monitor.previous_status, 'healthy')
        self.assertEqual(len(self.posts.pushover), 1)

    def test_a_register_query_that_fails_leaves_the_stale_rule_working(self):
        self.write(3600, power_w=500.0)
        with patch.object(monitor_app, 'register_values', side_effect=RuntimeError('no such column')):
            monitor_app.check_data_health()
        self.assertEqual(self.monitor.previous_status, 'unhealthy')
        self.assertIn('Data is not arriving', self.posts.sirens()[0]['message'])

    def test_a_register_query_that_fails_gives_no_verdict_on_a_fresh_feed(self):
        self.write(20, power_w=500.0)
        with patch.object(monitor_app, 'register_values', side_effect=RuntimeError('database is locked')):
            monitor_app.check_data_health()
        self.assertEqual(self.monitor.previous_status, 'healthy')
        self.assertEqual(self.posts.pushover, [])

    def test_watchdog_request_is_noted_on_a_200_and_on_a_503(self):
        self.assertIsNone(monitor_app.stats['watchdog_last_seen'])
        r = self.client.get('/health/data', headers=WATCHDOG_UA)       # empty store: 503
        self.assertEqual(r.status_code, 503)
        first = monitor_app.stats['watchdog_last_seen']
        self.assertIsNotNone(first)

        self.write(20, power_w=500.0)
        time.sleep(0.01)
        r = self.client.get('/health/data', headers=WATCHDOG_UA)       # fresh: 200
        self.assertEqual(r.status_code, 200)
        self.assertGreater(monitor_app.stats['watchdog_last_seen'], first)

    def test_other_user_agents_and_other_routes_are_not_the_watchdog(self):
        self.client.get('/health/data')
        self.client.get('/health/data', headers={'User-Agent': 'curl/8.5.0'})
        self.client.get('/api/stats', headers=WATCHDOG_UA)
        self.assertIsNone(monitor_app.stats['watchdog_last_seen'])
        self.assertIsNone(self.client.get('/api/stats').get_json()['monitor_stats']['watchdog_last_seen'])

    def test_watchdog_time_survives_a_restart_and_is_published(self):
        self.client.get('/health/data', headers=WATCHDOG_UA)
        with patch.object(monitor_app, 'WATCHDOG_SAVE_SECONDS', 0):    # a later request, the save interval past
            self.client.get('/health/data', headers=WATCHDOG_UA)
        seen = monitor_app.stats['watchdog_last_seen']
        monitor_app.stats['watchdog_last_seen'] = None     # a restart loses memory...
        monitor_app.init_store(self.db_path)               # ...and startup restores it
        self.assertEqual(monitor_app.stats['watchdog_last_seen'], seen)
        body = self.client.get('/api/stats').get_json()
        self.assertEqual(body['monitor_stats']['watchdog_last_seen'], seen)

    def test_a_save_that_fails_still_answers_the_watchdog(self):
        with patch.object(monitor_app.db, 'set_meta', side_effect=RuntimeError('database is locked')):
            r = self.client.get('/health/data', headers=WATCHDOG_UA)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.get_json()['status'], 'no_data')
        self.assertIsNotNone(monitor_app.stats['watchdog_last_seen'])

    def test_the_job_reports_a_silent_watchdog_and_its_return(self):
        self.feed(3, lambda seconds_ago: 94917.0 + (10800 - seconds_ago) / 3600.0)
        long_ago = datetime.now(timezone.utc) - timedelta(hours=7)
        monitor_app.stats['watchdog_last_seen'] = long_ago.isoformat()
        monitor_app.watchdog_liveness.silence_from = long_ago

        monitor_app.check_data_health()
        monitor_app.check_data_health()
        self.assertEqual([p['title'] for p in self.posts.pushover], ['Linknode watchdog: silent'])
        self.assertEqual(self.posts.pushover[0]['priority'], 0)

        # A restart during the silence: the mark is in the store, so nothing is sent again
        monitor_app.init_store(self.db_path)
        monitor_app.check_data_health()
        self.assertEqual(len(self.posts.pushover), 1)

        self.client.get('/health/data', headers=WATCHDOG_UA)
        monitor_app.check_data_health()
        self.assertEqual([p['title'] for p in self.posts.pushover],
                         ['Linknode watchdog: silent', 'Linknode watchdog: calling again'])

    def test_the_job_is_quiet_about_the_watchdog_while_the_feed_is_down(self):
        self.write(3600, power_w=500.0)                    # an hour stale
        long_ago = datetime.now(timezone.utc) - timedelta(hours=7)
        monitor_app.stats['watchdog_last_seen'] = long_ago.isoformat()
        monitor_app.watchdog_liveness.silence_from = long_ago
        monitor_app.check_data_health()
        self.assertEqual(len(self.posts.sirens()), 1)      # the feed's own siren
        self.assertEqual(self.posts.normal(), [])

    def test_a_store_with_no_saved_time_starts_the_clock_at_the_service_start(self):
        started = datetime.fromisoformat(monitor_app.stats['start_time'])
        self.assertEqual(monitor_app.watchdog_liveness.silence_from, started)
        self.assertFalse(monitor_app.watchdog_liveness.alerted)
        # and it is saved, so a restart counts from the first start, not from its own
        saved = json.loads(monitor_app.db.get_meta('watchdog_alert'))
        self.assertEqual(saved['silence_from'], monitor_app.stats['start_time'])
        with patch.dict(monitor_app.stats, {'start_time': (started + HOUR).isoformat()}):
            monitor_app.init_store(self.db_path)
        self.assertEqual(monitor_app.watchdog_liveness.silence_from, started)

    def test_current_power_comes_from_the_store_after_a_restart(self):
        self.write(20, power_w=1737.0)
        monitor_app.stats['last_power_reading'] = None     # a restart loses memory
        monitor_app.init_store(self.db_path)               # startup
        body = self.client.get('/api/stats').get_json()
        self.assertEqual(body['current_power'], 1737.0)
        # The in-memory value stays unset: the live stream would send it as live
        self.assertIsNone(monitor_app.stats['last_power_reading'])

    def test_current_power_is_null_with_an_empty_store(self):
        self.assertIsNone(self.client.get('/api/stats').get_json()['current_power'])


if __name__ == '__main__':
    unittest.main()
