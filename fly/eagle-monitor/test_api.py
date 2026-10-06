#!/usr/bin/env python3
"""
Flask route tests for the SQLite-backed eagle monitor (no InfluxDB, temp DB).
Run: python -m unittest discover -s fly/eagle-monitor -p "test_*.py"
"""

import os
import shutil
import tempfile
import time
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

os.environ.pop('EAGLE_PASSWORD', None)  # Basic auth off for the webhook tests
import app as monitor_app  # noqa: E402

ZIGBEE_EPOCH_OFFSET = 946684800

STATS_KEYS = {
    'current_power', 'min_24h', 'max_24h', 'avg_24h', 'cost_24h', 'price_per_kwh',
    'meter_price_per_kwh',
    'last_update', 'active_viewers', 'packet_interval_ms', 'packets_today', 'reads_24h',
    'bypass_status', 'monitor_stats', 'billing_period', 'site_traffic',
}


def demand_xml(watts, unix_ts):
    return (
        '<rainforest><InstantaneousDemand>'
        '<DeviceMacId>0xd8d5b9000000ef69</DeviceMacId><MeterMacId>0x0013500100c5e5d1</MeterMacId>'
        f'<TimeStamp>{hex(int(unix_ts) - ZIGBEE_EPOCH_OFFSET)}</TimeStamp>'
        f'<Demand>{hex(int(watts))}</Demand><Multiplier>0x1</Multiplier><Divisor>0x3e8</Divisor>'
        '</InstantaneousDemand></rainforest>'
    )


def price_xml(price_hundredths, unix_ts):
    return (
        '<rainforest><PriceCluster>'
        '<DeviceMacId>0xd8d5b9000000ef69</DeviceMacId><MeterMacId>0x0013500100c5e5d1</MeterMacId>'
        f'<TimeStamp>{hex(int(unix_ts) - ZIGBEE_EPOCH_OFFSET)}</TimeStamp>'
        f'<Price>{hex(price_hundredths)}</Price><TrailingDigits>0x4</TrailingDigits>'
        '</PriceCluster></rainforest>'
    )


def bypass_xml(data_uptime='99.92', cycle_period='34.6'):
    return (
        '<rainforest><BypassStatus>'
        '<DeviceMacId>0xd8d5b9000000ef69</DeviceMacId>'
        f'<DataUptimePct>{data_uptime}</DataUptimePct><DeviceUptimePct>100.0</DeviceUptimePct>'
        f'<IntervalSeconds>30</IntervalSeconds><CyclePeriodSeconds>{cycle_period}</CyclePeriodSeconds>'
        '</BypassStatus></rainforest>'
    )


@contextmanager
def pinned_clock(fixed):
    """Hold the clock at `fixed` in app.py and store.py for the length of a test."""
    class PinnedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz is not None else fixed.replace(tzinfo=None)

    with patch.object(monitor_app, 'datetime', PinnedDatetime), \
            patch.object(monitor_app.store, 'datetime', PinnedDatetime):
        yield


class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.assertTrue(monitor_app.init_store(os.path.join(self.tmp, 'energy.db')))
        monitor_app._dashboard_cache.clear()
        monitor_app._billing_days_cache.clear()
        monitor_app.stats.update({'last_data_received': None, 'last_power_reading': None,
                                  'successful_writes': 0, 'failed_writes': 0,
                                  'bypass_status': None})
        self.client = monitor_app.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def post(self, xml):
        return self.client.post('/eagle', data=xml, content_type='application/xml')

    def test_demand_is_stored_and_marks_fresh(self):
        now = time.time()
        r = self.post(demand_xml(1500, now - 30))
        self.assertEqual(r.get_json(), {'status': 'ok'})
        self.assertEqual(monitor_app.stats['successful_writes'], 1)
        self.assertIsNotNone(monitor_app.stats['last_data_received'])
        latest = monitor_app.db.latest('power_w', 0, int(now * 1000))
        self.assertEqual(latest[1], 1500.0)

    def test_restamped_stale_reading_does_not_add_a_row(self):
        ts = time.time() - 60
        self.post(demand_xml(1000, ts))
        self.post(demand_xml(1000, ts))
        now_ms = int(time.time() * 1000)
        self.assertEqual(monitor_app.db.agg('power_w', 0, now_ms)['count'], 1)

    def test_store_failure_does_not_mark_fresh(self):
        monitor_app.db = MagicMock()
        monitor_app.db.write.side_effect = RuntimeError('disk full')
        r = self.post(demand_xml(800, time.time() - 5))
        self.assertEqual(r.get_json()['status'], 'received')
        self.assertIsNone(monitor_app.stats['last_data_received'])
        self.assertEqual(monitor_app.stats['failed_writes'], 1)

    def test_stats_shape_and_values(self):
        # The clock is held in a billing period that has already ended. On the real clock
        # this test failed for the first 40 minutes of each period, before the readings
        # (stamped up to an hour back) fell inside it, and that blocked a CI deploy. The
        # clock is read in three places and all three must agree: `now` here, datetime in
        # app.py and datetime in store.py. Leave any one on the real clock and the
        # readings fall outside the window, so the test fails at once.
        fixed = datetime(2026, 8, 15, 12, 0, tzinfo=monitor_app.BILLING_TZ)
        with pinned_clock(fixed):
            self._stats_shape_and_values(fixed.timestamp())

    def _stats_shape_and_values(self, now):
        for i, w in enumerate((1000, 2000, 3000)):
            self.post(demand_xml(w, now - 3600 + i * 600))
        self.post(price_xml(1172, now - 60))
        body = self.client.get('/api/stats').get_json()
        self.assertEqual(set(body), STATS_KEYS)
        self.assertEqual(body['min_24h'], 1000.0)
        self.assertEqual(body['max_24h'], 3000.0)
        self.assertAlmostEqual(body['avg_24h'], 2000.0)
        # Billing uses the configured BC Hydro rates, not the Eagle's stale price
        self.assertEqual(body['price_per_kwh'], monitor_app.TIER1_RATE)
        self.assertAlmostEqual(body['meter_price_per_kwh'], 0.1172)
        self.assertEqual(body['billing_period']['tiered_cost']['tier1_rate'], monitor_app.TIER1_RATE)
        dash = self.client.get('/api/dashboard?range=24h').get_json()
        self.assertEqual(dash['price_per_kwh'], monitor_app.TIER1_RATE)
        self.assertAlmostEqual(dash['meter_price_per_kwh'], 0.1172)
        self.assertEqual(body['reads_24h']['received'], 3)
        self.assertIsNotNone(body['billing_period']['tiered_cost'])
        self.assertIn(body['billing_period']['cycle_days'], range(59, 63))
        self.assertIsNotNone(body['billing_period']['next_start'])
        self.assertEqual(body['billing_period']['trend']['points'][0], [0.0, 0.0])

    def test_heartbeat_survives_restart(self):
        r = self.post(bypass_xml())
        self.assertEqual(r.get_json(), {'status': 'ok', 'type': 'bypass_status'})
        # A heartbeat is not meter data: it must not mask a staleness alert
        self.assertIsNone(monitor_app.stats['last_data_received'])

        monitor_app.stats['bypass_status'] = None          # a restart loses memory...
        monitor_app.init_store(monitor_app.db.path)        # ...and startup restores it
        body = self.client.get('/api/stats').get_json()
        self.assertEqual(body['bypass_status']['data_uptime_pct'], 99.92)
        self.assertEqual(body['reads_24h']['period_s'], 34.6)

    def test_newer_heartbeat_replaces_saved_one(self):
        self.post(bypass_xml(data_uptime='99.0'))
        self.post(bypass_xml(data_uptime='98.5'))
        monitor_app.stats['bypass_status'] = None
        monitor_app.init_store(monitor_app.db.path)
        self.assertEqual(monitor_app.stats['bypass_status']['data_uptime_pct'], 98.5)

    def test_stats_empty_window(self):
        body = self.client.get('/api/stats').get_json()
        self.assertEqual(set(body), STATS_KEYS)
        self.assertEqual((body['min_24h'], body['avg_24h'], body['cost_24h']), (0, 0, 0))
        self.assertEqual(body['reads_24h']['received'], 0)
        self.assertIsNone(body['billing_period']['tiered_cost'])

    def test_stats_reads_null_without_store(self):
        monitor_app.db = None
        body = self.client.get('/api/stats').get_json()
        self.assertIsNone(body['reads_24h'])

    def test_stats_rejects_bad_hours(self):
        self.assertEqual(self.client.get('/api/stats?hours=abc').status_code, 400)
        self.assertEqual(self.client.get('/api/stats?hours=0').status_code, 400)
        self.assertEqual(self.client.get('/api/stats?hours=721').status_code, 400)

    def test_dashboard_ranges(self):
        self.post(demand_xml(1200, time.time() - 10))
        for key in ('1h', '6h', '24h', '7d', '30d'):
            r = self.client.get(f'/api/dashboard?range={key}')
            self.assertEqual(r.status_code, 200, key)
            body = r.get_json()
            self.assertEqual(body['power']['current'], 1200.0)
            self.assertEqual(len([p for p in body['series'] if p[1] is not None]), 1)
        self.assertEqual(self.client.get('/api/dashboard?range=2h').status_code, 400)

    def test_health(self):
        self.assertEqual(self.client.get('/health').status_code, 200)
        monitor_app.db = None
        r = self.client.get('/health')
        self.assertEqual(r.status_code, 503)
        self.assertFalse(r.get_json()['db_ok'])

    def test_data_health_follows_the_reading_time_not_the_arrival_time(self):
        r = self.client.get('/health/data')
        self.assertEqual((r.status_code, r.get_json()['status']), (503, 'no_data'))

        self.post(demand_xml(900, time.time() - 20))
        r = self.client.get('/health/data')
        self.assertEqual((r.status_code, r.get_json()['status']), (200, 'fresh'))
        self.assertEqual(r.get_json()['power_w'], 900.0)
        self.assertLess(r.get_json()['reading_age_seconds'], 60)

    def test_data_health_goes_stale_while_a_frozen_reading_keeps_arriving(self):
        # The Eagle has lost the meter: the Pi re-posts the same 10-minute-old reading.
        # Arrival time is now, the reading is not.
        frozen = time.time() - 600
        self.post(demand_xml(900, frozen))
        self.post(demand_xml(900, frozen))
        self.assertIsNotNone(monitor_app.stats['last_data_received'])
        r = self.client.get('/health/data')
        self.assertEqual((r.status_code, r.get_json()['status']), (503, 'stale'))
        self.assertGreater(r.get_json()['reading_age_seconds'], 590)

        # The in-process alarm sees the same thing
        with patch.object(monitor_app.monitor, 'check_data_freshness',
                          return_value=('unhealthy', False)) as check:
            monitor_app.check_data_health()
        seen = check.call_args[0][0]
        age = datetime.now(timezone.utc) - datetime.fromisoformat(seen['last_data_received'])
        self.assertGreater(age.total_seconds(), 590)
        self.assertEqual(seen['last_power_reading'], 900.0)

    def test_data_health_without_a_store(self):
        monitor_app.db = None
        self.assertEqual(self.client.get('/health/data').status_code, 503)

    def test_cors_allows_site_origins_only(self):
        for origin in ('https://linknode.com', 'https://www.linknode.com',
                       'https://linknode-web.murr2k.workers.dev',
                       'https://3f2a9c1d-linknode-web.murr2k.workers.dev'):
            r = self.client.get('/api/stats', headers={'Origin': origin})
            self.assertEqual(r.headers.get('Access-Control-Allow-Origin'), origin)
        for origin in ('https://evil.example', 'https://linknode-web.workers.dev.evil.example'):
            r = self.client.get('/api/stats', headers={'Origin': origin})
            self.assertIsNone(r.headers.get('Access-Control-Allow-Origin'))


class TestBilling(unittest.TestCase):
    """The bill-so-far estimate against real BC Hydro bills (Jul 30 and Sep 29, 2026, rate 1101)."""

    def test_matches_july_2026_invoice(self):
        # May 29 - Jul 28, 2026: 855 kWh over 61 days, total due $123.75
        bill = monitor_app.calculate_tiered_cost(855, 61)
        self.assertEqual(bill['threshold_kwh'], 1353.70)   # printed as 1,354 kWh
        self.assertEqual(bill['basic_charge'], 14.30)      # 61 days x $0.2344
        self.assertEqual(bill['tier1_cost'], 101.49)       # 855 kWh x $0.1187
        self.assertEqual(bill['tier2_cost'], 0.00)
        self.assertEqual(bill['rider'], -1.74)             # deferral account rider -1.5%
        self.assertEqual(bill['transit_levy'], 3.81)       # 61 days x $0.0624
        self.assertEqual(bill['subtotal'], 117.86)
        self.assertEqual(bill['gst'], 5.89)                # GST 5% on $117.86
        self.assertEqual(bill['total_cost'], 123.75)

    def test_matches_september_2026_invoice(self):
        # Jul 29 - Sep 25, 2026: 914 kWh over 59 days, total due $130.38
        bill = monitor_app.calculate_tiered_cost(914, 59)
        self.assertEqual(bill['threshold_kwh'], 1309.32)   # printed as 1,309 kWh
        self.assertEqual(bill['basic_charge'], 13.83)      # 59 days x $0.2344
        self.assertEqual(bill['tier1_cost'], 108.49)       # 914 kWh x $0.1187
        self.assertEqual(bill['tier2_cost'], 0.00)
        self.assertEqual(bill['rider'], -1.83)             # deferral account rider -1.5%
        self.assertEqual(bill['transit_levy'], 3.68)       # 59 days x $0.0624
        self.assertEqual(bill['subtotal'], 124.17)
        self.assertEqual(bill['gst'], 6.21)                # GST 5% on $124.17
        self.assertEqual(bill['total_cost'], 130.38)

    def test_usage_over_the_threshold_splits_into_tier2(self):
        bill = monitor_app.calculate_tiered_cost(1500, 61)
        self.assertEqual(bill['tier1_kwh'], 1353.70)
        self.assertEqual(bill['tier2_kwh'], 146.30)
        self.assertEqual(bill['tier2_cost'], round(146.30 * 0.1408, 2))

    def start(self, when):
        now = when if isinstance(when, datetime) else datetime.fromisoformat(when).replace(tzinfo=timezone.utc)
        return monitor_app.get_billing_period_start(now).strftime('%Y-%m-%d')

    def test_period_is_two_months_in_odd_months(self):
        self.assertEqual(self.start('2026-09-27T12:00'), '2026-09-26')
        self.assertEqual(self.start('2026-10-30T12:00'), '2026-09-26')
        self.assertEqual(self.start('2027-01-10T12:00'), '2026-11-26')
        self.assertEqual(self.start('2026-01-26T12:00'), '2026-01-26')

    def test_period_boundary_is_local_midnight(self):
        # Periods turn over at midnight in Vancouver, not UTC. The offset comes from the
        # tz database (BC went to permanent UTC-7 in 2026), so derive it, don't hardcode it.
        boundary = datetime(2026, 11, 26, tzinfo=monitor_app.BILLING_TZ).astimezone(timezone.utc)
        self.assertNotEqual(boundary.hour, 0)
        self.assertEqual(self.start(boundary - timedelta(minutes=1)), '2026-09-26')
        self.assertEqual(self.start(boundary + timedelta(minutes=1)), '2026-11-26')

    def test_period_start_from_the_bill_steps_by_whole_cycles(self):
        saved = monitor_app.BILLING_PERIOD_START
        monitor_app.BILLING_PERIOD_START = '2026-07-29'
        try:
            self.assertEqual(self.start('2026-09-27T12:00'), '2026-07-29')
            self.assertEqual(self.start('2026-09-30T12:00'), '2026-09-29')
        finally:
            monitor_app.BILLING_PERIOD_START = saved

    def period(self, when, next_read):
        saved = monitor_app.BILLING_NEXT_READ
        monitor_app.BILLING_NEXT_READ = next_read
        try:
            now = datetime.fromisoformat(when).replace(tzinfo=monitor_app.BILLING_TZ)
            return tuple(d.strftime('%Y-%m-%d') for d in monitor_app.get_billing_period(now))
        finally:
            monitor_app.BILLING_NEXT_READ = saved

    def test_next_read_from_the_bill_moves_the_boundary(self):
        # Sep 29, 2026 bill: next read on or around Nov 26, so this period is 62 days
        self.assertEqual(self.period('2026-10-02T12:00', '2026-11-26'), ('2026-09-26', '2026-11-27'))
        # The read day itself still belongs to the old period, past the nominal boundary
        self.assertEqual(self.period('2026-11-26T12:00', '2026-11-26'), ('2026-09-26', '2026-11-27'))
        self.assertEqual(self.period('2026-11-27T00:00', '2026-11-26'), ('2026-11-27', '2027-01-26'))
        # A read before the nominal boundary ends the period early
        self.assertEqual(self.period('2026-11-24T12:00', '2026-11-23'), ('2026-11-24', '2027-01-26'))

    def test_next_read_far_from_a_boundary_is_ignored(self):
        self.assertEqual(self.period('2027-02-10T12:00', '2026-11-26'), ('2027-01-26', '2027-03-26'))
        self.assertEqual(self.period('2026-10-02T12:00', None), ('2026-09-26', '2026-11-26'))

    def test_trend_of_a_constant_rate_is_the_bill_at_that_rate(self):
        # 15 kWh/day for 10 full days and half of the 11th, in a 62-day cycle
        trend = monitor_app.billing_trend([15.0 * day for day in range(1, 11)], 10.5, 157.5, 62)
        self.assertEqual(trend['points'][0], [0.0, 0.0])
        self.assertEqual(trend['points'][10], [10.0, monitor_app.calculate_tiered_cost(150, 10)['total_cost']])
        self.assertEqual(trend['points'][-1][0], 10.5)
        self.assertEqual(len(trend['points']), 12)
        # The straight line lands on the real bill for 62 days at that rate, to rounding
        full = monitor_app.calculate_tiered_cost(15.0 * 62, 62)['total_cost']
        self.assertAlmostEqual(trend['projected_total'], full, delta=0.05)
        self.assertAlmostEqual(trend['slope_per_day'], full / 62, delta=0.005)

    def test_trend_slope_follows_the_spend_rate(self):
        slow = monitor_app.billing_trend([10.0 * day for day in range(1, 8)], 7.0, 70.0, 61)
        fast = monitor_app.billing_trend([30.0 * day for day in range(1, 8)], 7.0, 210.0, 61)
        self.assertGreater(fast['slope_per_day'], 2 * slow['slope_per_day'])
        self.assertGreater(fast['projected_total'], slow['projected_total'])

    def test_no_trendline_before_a_full_day(self):
        trend = monitor_app.billing_trend([], 0.4, 6.0, 61)
        self.assertEqual(len(trend['points']), 2)
        self.assertIsNone(trend['slope_per_day'])
        self.assertIsNone(trend['projected_total'])
        self.assertEqual(trend['estimates'], [])
        self.assertIsNone(trend['projected_min'])

    def test_day_one_alone_makes_no_estimate(self):
        # A heavy first day: the line through it alone would point far too high
        trend = monitor_app.billing_trend([60.0], 1.5, 70.0, 62)
        self.assertEqual(len(trend['points']), 3)
        self.assertIsNone(trend['slope_per_day'])
        self.assertEqual(trend['estimates'], [])

    def test_estimates_run_from_day_two_to_now(self):
        # 60 kWh on day 1, then 15 kWh/day: the early lines point high and come down
        day_kwh = [60.0 + 15.0 * day for day in range(6)]
        trend = monitor_app.billing_trend(day_kwh, 6.5, 142.5, 62)
        estimates = trend['estimates']
        self.assertEqual([e[0] for e in estimates], [2.0, 3.0, 4.0, 5.0, 6.0, 6.5])
        # Each is the line through the points up to that day
        points = [tuple(p) for p in trend['points']]
        slope, intercept = monitor_app._linear_fit(points[:4])
        self.assertEqual(estimates[1], [3.0, round(slope, 4), round(intercept, 4),
                                        round(slope * 62 + intercept, 2)])
        # The last one is the trendline, and the range is over all of them
        self.assertEqual(estimates[-1][1:], [trend['slope_per_day'], trend['intercept'],
                                             trend['projected_total']])
        totals = [e[3] for e in estimates]
        self.assertEqual(trend['projected_min'], min(totals))
        self.assertEqual(trend['projected_max'], max(totals))
        self.assertEqual(trend['projected_max'], totals[0])
        self.assertGreater(trend['projected_max'], trend['projected_total'])

    def test_constant_rate_has_no_range_to_speak_of(self):
        # Not exactly none: each line of the bill is rounded to the cent, day by day
        trend = monitor_app.billing_trend([15.0 * day for day in range(1, 11)], 10.5, 157.5, 62)
        self.assertAlmostEqual(trend['projected_min'], trend['projected_max'], delta=0.5)

    def test_previous_bill_is_the_trendline_until_two_days_are_in(self):
        for day_kwh, elapsed, energy in (([], 0.4, 6.0), ([60.0], 1.5, 70.0)):
            trend = monitor_app.billing_trend(day_kwh, elapsed, energy, 62, 144.66)
            self.assertEqual(trend['estimates'], [[0.0, round(144.66 / 62, 4), 0.0, 144.66]])
            self.assertEqual(trend['intercept'], 0.0)
            self.assertEqual(trend['projected_total'], 144.66)
            self.assertEqual((trend['projected_min'], trend['projected_max']), (144.66, 144.66))

    def test_previous_bill_stays_the_first_estimate(self):
        day_kwh = [60.0 + 15.0 * day for day in range(6)]
        seeded = monitor_app.billing_trend(day_kwh, 6.5, 142.5, 62, 40.0)
        plain = monitor_app.billing_trend(day_kwh, 6.5, 142.5, 62)
        self.assertEqual(seeded['estimates'][0], [0.0, round(40.0 / 62, 4), 0.0, 40.0])
        self.assertEqual(seeded['estimates'][1:], plain['estimates'])
        self.assertEqual(seeded['projected_total'], plain['projected_total'])
        self.assertEqual(seeded['projected_min'], 40.0)
        self.assertEqual(seeded['projected_max'], plain['projected_max'])


class TestBillingDays(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.assertTrue(monitor_app.init_store(os.path.join(self.tmp, 'energy.db')))
        monitor_app._billing_days_cache.clear()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cumulative_kwh_at_each_local_midnight(self):
        start = datetime(2026, 9, 26, tzinfo=monitor_app.BILLING_TZ)
        start_ms = monitor_app.store.to_ms(start)
        # A steady 1 kW from the first midnight, read every 30 minutes for 2.5 days
        for i in range(121):
            monitor_app.db.write(start_ms + i * 1_800_000, {'power_w': 1000})
        days = monitor_app._billing_day_kwh(start, 2)
        self.assertEqual(len(days), 2)
        # The reading on each midnight belongs to the next day, so day 1 stops at 23:30
        self.assertAlmostEqual(days[0], 23.5)
        self.assertAlmostEqual(days[1], 47.5)

    def test_no_completed_days(self):
        start = datetime(2026, 9, 26, tzinfo=monitor_app.BILLING_TZ)
        self.assertEqual(monitor_app._billing_day_kwh(start, 0), [])

    def steady_kw(self, first, last):
        """1 kW read every 6 hours from `first` to `last`."""
        power = monitor_app.store.FIELD_IDS['power_w']
        step = 6 * 3_600_000
        monitor_app.db.insert_ignore(num_rows=[
            (power, ms, 1000.0)
            for ms in range(monitor_app.store.to_ms(first), monitor_app.store.to_ms(last) + 1, step)])

    def test_previous_period_bill(self):
        # The period before Nov 27, 2026 ran from Sep 26: 62 days
        previous_start = datetime(2026, 9, 26, tzinfo=monitor_app.BILLING_TZ)
        start = datetime(2026, 11, 27, tzinfo=monitor_app.BILLING_TZ)
        self.steady_kw(previous_start, start + timedelta(days=3))
        kwh = monitor_app.db.integral_wh(monitor_app.store.to_ms(previous_start),
                                         monitor_app.store.to_ms(start)) / 1000.0
        self.assertAlmostEqual(kwh, 24 * 62, delta=6.0)
        self.assertEqual(monitor_app._previous_period_bill(start),
                         monitor_app.calculate_tiered_cost(kwh, 62)['total_cost'])

    def test_no_previous_bill_when_the_store_starts_inside_that_period(self):
        start = datetime(2026, 11, 27, tzinfo=monitor_app.BILLING_TZ)
        self.steady_kw(datetime(2026, 10, 20, tzinfo=monitor_app.BILLING_TZ), start)
        self.assertIsNone(monitor_app._previous_period_bill(start))


if __name__ == '__main__':
    unittest.main()
