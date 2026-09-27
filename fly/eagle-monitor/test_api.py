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
from unittest.mock import MagicMock

os.environ.pop('EAGLE_PASSWORD', None)  # Basic auth off for the webhook tests
import app as monitor_app  # noqa: E402

ZIGBEE_EPOCH_OFFSET = 946684800

STATS_KEYS = {
    'current_power', 'min_24h', 'max_24h', 'avg_24h', 'cost_24h', 'price_per_kwh',
    'last_update', 'active_viewers', 'packet_interval_ms', 'packets_today', 'reads_24h',
    'bypass_status', 'monitor_stats', 'billing_period',
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


class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.assertTrue(monitor_app.init_store(os.path.join(self.tmp, 'energy.db')))
        monitor_app.write_api = None
        monitor_app.STATS_BACKEND = 'sqlite'
        monitor_app._dashboard_cache.clear()
        monitor_app.stats.update({'last_data_received': None, 'last_power_reading': None,
                                  'successful_writes': 0, 'failed_writes': 0,
                                  'influx_failed_writes': 0, 'bypass_status': None})
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

    def test_influx_copy_failure_does_not_affect_freshness(self):
        monitor_app.write_api = MagicMock()
        monitor_app.write_api.write.side_effect = TimeoutError('influx down')
        r = self.post(demand_xml(800, time.time() - 5))
        self.assertEqual(r.get_json(), {'status': 'ok'})
        self.assertIsNotNone(monitor_app.stats['last_data_received'])
        self.assertEqual(monitor_app.stats['influx_failed_writes'], 1)
        self.assertEqual(monitor_app.stats['failed_writes'], 0)

    def test_store_failure_does_not_mark_fresh(self):
        monitor_app.db = MagicMock()
        monitor_app.db.write.side_effect = RuntimeError('disk full')
        r = self.post(demand_xml(800, time.time() - 5))
        self.assertEqual(r.get_json()['status'], 'received')
        self.assertIsNone(monitor_app.stats['last_data_received'])
        self.assertEqual(monitor_app.stats['failed_writes'], 1)

    def test_stats_shape_and_values(self):
        now = time.time()
        for i, w in enumerate((1000, 2000, 3000)):
            self.post(demand_xml(w, now - 3600 + i * 600))
        self.post(price_xml(1172, now - 60))
        body = self.client.get('/api/stats').get_json()
        self.assertEqual(set(body), STATS_KEYS)
        self.assertEqual(body['min_24h'], 1000.0)
        self.assertEqual(body['max_24h'], 3000.0)
        self.assertAlmostEqual(body['avg_24h'], 2000.0)
        self.assertAlmostEqual(body['price_per_kwh'], 0.1172)
        self.assertEqual(body['reads_24h']['received'], 3)
        self.assertIsNotNone(body['billing_period']['tiered_cost'])

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

    def test_cors_allows_site_origins_only(self):
        for origin in ('https://linknode.com', 'https://www.linknode.com',
                       'https://linknode-web.murr2k.workers.dev',
                       'https://3f2a9c1d-linknode-web.murr2k.workers.dev'):
            r = self.client.get('/api/stats', headers={'Origin': origin})
            self.assertEqual(r.headers.get('Access-Control-Allow-Origin'), origin)
        for origin in ('https://evil.example', 'https://linknode-web.workers.dev.evil.example'):
            r = self.client.get('/api/stats', headers={'Origin': origin})
            self.assertIsNone(r.headers.get('Access-Control-Allow-Origin'))


if __name__ == '__main__':
    unittest.main()
