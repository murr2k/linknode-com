#!/usr/bin/env python3
"""Tests for the Pi's thermostat uploader (scripts/t5_upload.py) against the real
/thermostat route: the two only work together, so they are tested together."""

import importlib.util
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.pop('EAGLE_PASSWORD', None)

import app as monitor_app  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts', 't5_upload.py')
spec = importlib.util.spec_from_file_location('t5_upload', SCRIPT)
t5_upload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t5_upload)

HEADER = 'time,epoch,event,active,mode,temp,target\n'


class TestUploader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.assertTrue(monitor_app.init_store(os.path.join(self.tmp, 'energy.db')))
        self.client = monitor_app.app.test_client()
        self.events = os.path.join(self.tmp, 'events.csv')
        self.seen = os.path.join(self.tmp, 'last_seen')
        self.base = time.time() - 3600
        self.up = True
        self.posts = []
        patches = [patch.object(t5_upload, 'post', self.post),
                   patch.object(t5_upload, 'LAST_SEEN', self.seen)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.uploader = t5_upload.Uploader(self.events)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def post(self, events, seen):
        """Stands in for the HTTP request: straight into the Flask route."""
        self.posts.append(len(events))
        if not self.up:
            return 0, {}
        r = self.client.post('/thermostat', json={'events': events, 'last_seen': seen})
        return r.status_code, r.get_json()

    def write(self, *lines, mode='a'):
        with open(self.events, mode, encoding='utf-8', newline='') as fp:
            fp.write(''.join(lines))

    def line(self, offset, event='change', active=0, temp=21.5):
        state = f'{active},1,{temp},21' if event not in ('lost',) else ',,,'
        return f'2026-10-10T12:00:00-07:00,{self.base + offset:.3f},{event},{state}\n'

    def stored(self):
        return monitor_app.db.thermostat_events(0, int(time.time() * 1000) + 1)

    def test_ships_what_is_new_and_nothing_twice(self):
        self.write(HEADER, self.line(0, 'start'), self.line(60, active=1))
        self.assertEqual(self.uploader.cycle(), 2)
        self.assertEqual(self.uploader.cycle(), 0)
        self.write(self.line(120))
        self.assertEqual(self.uploader.cycle(), 1)
        rows = self.stored()
        self.assertEqual([row[1:] for row in rows],
                         [('start', 0, 1, 21.5, 21.0), ('change', 1, 1, 21.5, 21.0), ('change', 0, 1, 21.5, 21.0)])
        self.assertEqual(rows[1][0], round((self.base + 60) * 1000))

    def test_a_restart_sends_only_what_the_service_lacks(self):
        self.write(HEADER, self.line(0, 'start'), self.line(60, active=1))
        self.uploader.cycle()
        self.write(self.line(120))
        fresh = t5_upload.Uploader(self.events)
        self.assertEqual(fresh.cycle(), 1)
        self.assertEqual(len(self.stored()), 3)

    def test_a_row_stamped_earlier_keeps_its_place_in_the_file(self):
        # The logger stamps `lost` with its last good read, here before the pushed change
        self.write(HEADER, self.line(0, 'start'), self.line(65, active=1), self.line(60, 'lost'))
        self.uploader.cycle()
        rows = self.stored()
        self.assertEqual([row[1] for row in rows], ['start', 'change', 'lost'])
        self.assertEqual(rows[2][0], rows[1][0] + 1)
        self.assertEqual(rows[2][2:], (None, None, None, None))

    def test_a_row_still_being_written_waits(self):
        whole = self.line(60, active=1)
        self.write(HEADER, self.line(0, 'start'), whole[:-6])
        self.assertEqual(self.uploader.cycle(), 1)
        self.write(whole[-6:])
        self.assertEqual(self.uploader.cycle(), 1)
        self.assertEqual(self.stored()[1][1:], ('change', 1, 1, 21.5, 21.0))

    def test_rows_wait_while_the_service_is_down(self):
        self.write(HEADER, self.line(0, 'start'))
        self.uploader.cycle()
        self.up = False
        self.write(self.line(60, active=1))
        with self.assertLogs(t5_upload.log, 'WARNING'):
            self.assertEqual(self.uploader.cycle(), 0)
        self.assertTrue(self.uploader.failing)
        self.write(self.line(120))
        self.assertEqual(self.uploader.cycle(), 0)
        self.up = True
        with self.assertLogs(t5_upload.log, 'INFO'):
            self.assertEqual(self.uploader.cycle(), 2)
        self.assertFalse(self.uploader.failing)
        self.assertEqual(len(self.stored()), 3)

    def test_a_restored_store_gets_the_file_again(self):
        self.write(HEADER, self.line(0, 'start'), self.line(60, active=1))
        self.uploader.cycle()
        monitor_app.init_store(os.path.join(self.tmp, 'restored.db'))   # an empty store
        self.write(self.line(120))
        with self.assertLogs(t5_upload.log, 'WARNING'):
            self.uploader.cycle()   # learns the service is behind
        self.uploader.cycle()       # and sends the file from the top
        self.assertEqual(len(self.stored()), 3)

    def test_the_last_read_time_is_posted_when_nothing_is_new(self):
        self.write(HEADER, self.line(0, 'start'))
        self.uploader.cycle()
        with open(self.seen, 'w', encoding='utf-8') as fp:
            fp.write(f'{self.base + 600:.3f}')
        self.posts.clear()
        self.uploader.cycle()                        # within the heartbeat: nothing to say
        self.assertEqual(self.posts, [])
        self.uploader.last_post -= t5_upload.HEARTBEAT_SECS
        self.uploader.cycle()
        self.assertEqual(self.posts, [0])
        self.assertEqual(monitor_app.db.get_meta('thermostat_seen_ms'), str(round((self.base + 600) * 1000)))

    def test_no_file_yet(self):
        self.assertEqual(self.uploader.cycle(), 0)
        self.assertEqual(self.stored(), [])


if __name__ == '__main__':
    unittest.main()
