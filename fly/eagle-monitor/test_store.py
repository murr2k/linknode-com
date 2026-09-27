#!/usr/bin/env python3
"""
Tests for the SQLite store and the dashboard payload math.
Run: python -m unittest discover -s fly/eagle-monitor -p "test_*.py"
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

import dashboard
import store

H = 3_600_000  # ms per hour
RATE = 0.1187  # a configured Step 1 rate


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = store.Store(os.path.join(self.tmp, 'energy.db'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestStore(StoreTestCase):
    def test_to_ms_floors_microseconds(self):
        dt = datetime(2026, 1, 1, 0, 0, 0, 999_999, tzinfo=timezone.utc)
        self.assertEqual(store.to_ms(dt) % 1000, 999)
        self.assertEqual(store.to_ms(store.EPOCH), 0)

    def test_same_key_overwrites(self):
        # A stale reading re-stamped with the same LastContact must not add a row.
        self.db.write(1000, {'power_w': 100})
        self.db.write(1000, {'power_w': 250})
        agg = self.db.agg('power_w', 0, 10_000)
        self.assertEqual(agg['count'], 1)
        self.assertEqual(agg['max'], 250)

    def test_fields_sharing_a_timestamp_are_both_kept(self):
        self.db.write(1000, {'power_w': 100})
        self.db.write(1000, {'energy_delivered_kwh': 12345.6})
        self.assertEqual(self.db.latest('power_w', 0, 10_000), (1000, 100.0))
        self.assertEqual(self.db.latest('energy_delivered_kwh', 0, 10_000), (1000, 12345.6))

    def test_text_fields_stored_separately(self):
        stored = self.db.write(1000, {'link_strength': '0x64', 'unknown': 1})
        self.assertEqual(stored, 1)
        rows = self.db._query('SELECT field, value FROM text_readings')
        self.assertEqual(rows, [('link_strength', '0x64')])
        self.assertEqual(self.db.agg('power_w', 0, 10_000)['count'], 0)

    def test_reads_exclude_end_and_future(self):
        self.db.write(1000, {'power_w': 100})
        self.db.write(5000, {'power_w': 900})  # "future" relative to end=5000
        self.assertEqual(self.db.agg('power_w', 0, 5000)['count'], 1)
        self.assertEqual(self.db.latest('power_w', 0, 5000), (1000, 100.0))

    def test_empty_window(self):
        agg = self.db.agg('power_w', 0, 10_000)
        self.assertEqual(agg, {'min': None, 'max': None, 'mean': None, 'count': 0})
        self.assertIsNone(self.db.latest('price_per_kwh', 0, 10_000))

    def test_integral_trapezoid(self):
        self.db.write(0, {'power_w': 1000})
        self.db.write(H // 2, {'power_w': 1000})
        self.db.write(H, {'power_w': 3000})
        # 0.5h * 1000W + 0.5h * (1000+3000)/2 W
        self.assertAlmostEqual(self.db.integral_wh(0, H + 1), 1500.0)

    def test_integral_bridges_gaps(self):
        self.db.write(0, {'power_w': 1000})
        self.db.write(2 * H, {'power_w': 1000})
        self.assertAlmostEqual(self.db.integral_wh(0, 2 * H + 1), 2000.0)

    def test_integral_uses_in_range_points_only(self):
        self.db.write(0, {'power_w': 5000})
        self.db.write(H, {'power_w': 1000})
        self.db.write(2 * H, {'power_w': 1000})
        self.assertAlmostEqual(self.db.integral_wh(H, 2 * H + 1), 1000.0)

    def test_integral_zero_and_one_point(self):
        self.assertIsNone(self.db.integral_wh(0, H))
        self.db.write(10, {'power_w': 1000})
        self.assertEqual(self.db.integral_wh(0, H), 0.0)

    def test_series_buckets_stamped_at_end_and_clipped(self):
        for ts, w in ((10_000, 100), (20_000, 300), (70_000, 500)):
            self.db.write(ts, {'power_w': w})
        self.assertEqual(self.db.series('power_w', 0, 100_000, 60_000),
                         [(60_000, 200.0, 100.0, 300.0), (100_000, 500.0, 500.0, 500.0)])

    def test_series_raw(self):
        self.db.write(20, {'power_w': 2})
        self.db.write(10, {'power_w': 1})
        self.assertEqual(self.db.series('power_w', 0, 100), [(10, 1.0, 1.0, 1.0), (20, 2.0, 2.0, 2.0)])

    def test_insert_ignore_keeps_existing(self):
        self.db.write(1000, {'power_w': 100})
        self.db.insert_ignore([(store.FIELD_IDS['power_w'], 1000, 999.0),
                               (store.FIELD_IDS['power_w'], 2000, 200.0)],
                              [('message_text', 1000, 'hello')])
        self.assertEqual([p[:2] for p in self.db.series('power_w', 0, 10_000)], [(1000, 100.0), (2000, 200.0)])
        self.assertEqual(self.db._query('SELECT value FROM text_readings'), [('hello',)])

    def test_prune(self):
        for ts in (0, 10 * 86_400_000, 20 * 86_400_000):
            self.db.write(ts, {'power_w': 1, 'link_strength': '0x10'})
        deleted = self.db.prune(15 * 86_400_000)
        self.assertEqual(deleted, 4)
        self.assertEqual([p[:2] for p in self.db.series('power_w', 0, 30 * 86_400_000)], [(20 * 86_400_000, 1.0)])

    def test_created_ms_survives_reopen(self):
        created = self.db.created_ms()
        reopened = store.Store(self.db.path)
        self.assertEqual(reopened.created_ms(), created)
        self.assertTrue(reopened.ping())


class TestDashboard(StoreTestCase):
    def test_panel_values(self):
        now = 10 * H
        self.db.write(now - 2 * H, {'power_w': 1000})
        self.db.write(now - H, {'power_w': 1000})
        self.db.write(now - 60_000, {'power_w': 2000})
        self.db.write(now - 60_000, {'energy_delivered_kwh': 4321.0})
        self.db.write(now - 3 * H, {'price_per_kwh': 0.1172})

        p = dashboard.build(self.db, '6h', now, RATE)
        self.assertEqual(p['power']['current'], 2000.0)
        self.assertEqual(p['power']['min'], 1000.0)
        self.assertEqual(p['power']['max'], 2000.0)
        self.assertEqual(p['meter_kwh'], 4321.0)
        # The configured rate wins; the Eagle's stale price is only reported
        self.assertEqual(p['price_per_kwh'], RATE)
        self.assertEqual(p['meter_price_per_kwh'], 0.1172)
        self.assertAlmostEqual(p['cost_per_hour'], 2.0 * RATE)
        self.assertAlmostEqual(p['estimated_cost'], p['energy_wh'] / 1000 * RATE * 1.1)

    def test_stale_current_and_meter_are_none(self):
        now = 10 * H
        self.db.write(now - 10 * 60_000, {'power_w': 1000})
        p = dashboard.build(self.db, '1h', now, RATE)
        self.assertIsNone(p['power']['current'])
        self.assertIsNone(p['meter_kwh'])
        self.assertIsNone(p['cost_per_hour'])

    def test_chart_breaks_on_outage(self):
        now = 10 * H
        for ts in (now - 50 * 60_000, now - 49 * 60_000, now - 10 * 60_000):
            self.db.write(ts, {'power_w': 500})
        series = dashboard.build(self.db, '1h', now, RATE)['series']
        self.assertEqual([p[1] for p in series], [500.0, 500.0, None, 500.0])
        self.assertEqual(series[2], [series[1][0] + 1, None, None, None])

    def test_bucket_envelope_keeps_short_peaks(self):
        # A 1-minute 7 kW spike inside a 15-minute bucket of ~1 kW readings: the
        # mean flattens it, the envelope must not.
        now = 40 * 86_400_000
        start = now - 3 * 3_600_000
        for i in range(30):
            self.db.write(start + i * 30_000, {'power_w': 7000 if i == 10 else 1000})
        p = dashboard.build(self.db, '7d', now, RATE)
        mean, lo, hi = zip(*[pt[1:] for pt in p['series'] if pt[1] is not None])
        self.assertEqual(max(hi), 7000.0)
        self.assertEqual(max(hi), p['power']['max'])
        self.assertLess(max(mean), 2000)
        self.assertEqual(min(lo), 1000.0)

    def test_every_range_builds(self):
        for key in dashboard.RANGES:
            p = dashboard.build(self.db, key, 40 * 86_400_000, RATE)
            self.assertEqual(p['range'], key)
            self.assertEqual(p['series'], [])
            self.assertIsNone(p['energy_wh'])


if __name__ == '__main__':
    unittest.main()
