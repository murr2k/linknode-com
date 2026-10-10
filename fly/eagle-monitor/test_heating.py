#!/usr/bin/env python3
"""Tests for the heating side: the thermostat's event log (thermostat.py), the gas bill
model (gas.py), the outdoor temperature (weather.py) and their routes in app.py."""

import base64
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.pop('EAGLE_PASSWORD', None)

import app as monitor_app  # noqa: E402
import gas  # noqa: E402
import thermostat  # noqa: E402
import weather  # noqa: E402
from test_api import pinned_clock  # noqa: E402

TZ = monitor_app.BILLING_TZ
HOUR = 3_600_000


def ms(text):
    """Epoch milliseconds of a local (Vancouver) time like '2026-10-11 06:00'."""
    return monitor_app.store.to_ms(datetime.fromisoformat(text).replace(tzinfo=TZ))


def row(text, event='change', active=0, mode=1, temp=21.0, target=21.0):
    return (ms(text), event, active, mode, temp, target)


class TestGasBill(unittest.TestCase):
    """The estimate against real FortisBC bills (2026, residential, Lower Mainland)."""

    def lines(self, bill):
        return [bill[key] for key in ('basic_charge', 'delivery', 'storage_transport', 'commodity',
                                      'municipal_fee', 'clean_energy_levy', 'gst', 'total_cost')]

    def test_matches_july_2026_invoice(self):
        # Jul 1 - Jul 31, 2026: 1.4 GJ over 31 days, total $32.54
        self.assertEqual(self.lines(gas.bill(1.4, 31)), [13.07, 11.86, 3.46, 2.32, 0.17, 0.12, 1.54, 32.54])

    def test_matches_august_2026_invoice(self):
        # Aug 1 - Aug 31, 2026: 1.3 GJ over 31 days, total $31.22
        self.assertEqual(self.lines(gas.bill(1.3, 31)), [13.07, 11.01, 3.21, 2.16, 0.17, 0.12, 1.48, 31.22])

    def test_matches_september_2026_invoice(self):
        # Sep 1 - Sep 29, 2026: 1.4 GJ over 29 days, total $31.66
        self.assertEqual(self.lines(gas.bill(1.4, 29)), [12.23, 11.86, 3.46, 2.32, 0.17, 0.12, 1.50, 31.66])

    def test_matches_june_2026_invoice_at_the_rate_of_the_time(self):
        # Jun 3 - Jun 30, 2026: 1.4 GJ over 28 days, total $30.90. Storage and transport
        # was $2.255 until Jul 1, and the GST lands on a half cent ($1.4655).
        with patch.object(gas, 'STORAGE_TRANSPORT_PER_GJ', 2.255):
            self.assertEqual(self.lines(gas.bill(1.4, 28)), [11.80, 11.86, 3.16, 2.32, 0.17, 0.12, 1.47, 30.90])

    def test_usage_is_base_load_plus_furnace_hours(self):
        with patch.object(gas, 'FURNACE_INPUT_BTUH', None):
            rate, assumed = gas.furnace_gj_per_hour()
            self.assertTrue(assumed)
            self.assertAlmostEqual(rate, 60_000 / 947_817)
            self.assertAlmostEqual(gas.usage(30, 0), 30 * gas.BASE_GJ_PER_DAY)
            self.assertAlmostEqual(gas.usage(30, 100), 30 * gas.BASE_GJ_PER_DAY + 100 * rate)
        with patch.object(gas, 'FURNACE_INPUT_BTUH', 80_000.0):
            self.assertEqual(gas.furnace_gj_per_hour(), (80_000 / 947_817, False))

    def test_base_load_reproduces_the_summer_bills(self):
        # Jun 3 - Sep 29, 2026: 5.5 GJ billed over 119 days with the furnace off
        self.assertAlmostEqual(gas.usage(119, 0), 5.5, delta=0.05)


class TestGasPeriod(unittest.TestCase):
    def period(self, when, reads='2026-09-29'):
        with patch.object(gas, 'READ_DATES', reads):
            now = datetime.fromisoformat(when).replace(tzinfo=TZ)
            return tuple(d.strftime('%Y-%m-%d') for d in gas.period(now))

    def test_a_read_date_moves_the_first_of_the_month(self):
        # Read on Sep 29: that period ended then and the next began on Sep 30
        self.assertEqual(self.period('2026-10-10T12:00'), ('2026-09-30', '2026-11-01'))
        self.assertEqual(self.period('2026-09-30T00:00'), ('2026-09-30', '2026-11-01'))
        self.assertEqual(self.period('2026-09-29T23:00'), ('2026-09-01', '2026-09-30'))

    def test_without_a_read_date_periods_start_on_the_first(self):
        self.assertEqual(self.period('2026-11-05T12:00'), ('2026-11-01', '2026-12-01'))
        self.assertEqual(self.period('2026-10-10T12:00', ''), ('2026-10-01', '2026-11-01'))
        self.assertEqual(self.period('2026-12-31T23:59', ''), ('2026-12-01', '2027-01-01'))

    def test_several_read_dates(self):
        reads = '2026-09-29, 2026-10-30'
        self.assertEqual(self.period('2026-10-10T12:00', reads), ('2026-09-30', '2026-10-31'))
        self.assertEqual(self.period('2026-10-31T08:00', reads), ('2026-10-31', '2026-12-01'))

    def test_a_read_date_far_from_the_first_is_ignored(self):
        self.assertEqual(self.period('2026-10-10T12:00', '2026-10-15'), ('2026-10-01', '2026-11-01'))


class TestThermostat(unittest.TestCase):
    ROWS = [
        row('2026-10-10 12:00', 'start'),
        row('2026-10-10 23:30', active=1),                # a run that crosses midnight
        row('2026-10-10 23:45', active=1, temp=21.5),     # the room warms: same run
        row('2026-10-11 00:30', active=0, temp=22.0),
        row('2026-10-11 06:00', active=1),
        row('2026-10-11 07:00', active=0),
        row('2026-10-11 08:00', 'lost', None, None, None, None),
        row('2026-10-11 10:00', 'resume', active=1),
        row('2026-10-11 10:15', 'stop', active=1),
        row('2026-10-11 12:00', 'start', active=0),
    ]

    def test_daily_run_time_splits_at_local_midnight(self):
        days = thermostat.daily(self.ROWS, ms('2026-10-11 13:00'), TZ)
        first, second = days[date(2026, 10, 10)], days[date(2026, 10, 11)]
        self.assertEqual(first['heating_s'], 30 * 60)
        self.assertEqual(first['idle_s'], 11.5 * 3600)
        self.assertEqual(second['heating_s'], (30 + 60 + 15) * 60)

    def test_a_run_is_one_cycle_on_the_day_it_began(self):
        days = thermostat.daily(self.ROWS, ms('2026-10-11 13:00'), TZ)
        self.assertEqual(days[date(2026, 10, 10)]['heat_cycles'], 1)   # the 23:30 run
        self.assertEqual(days[date(2026, 10, 11)]['heat_cycles'], 2)   # 06:00, and 10:00 after the gap
        self.assertEqual(days[date(2026, 10, 11)]['cool_cycles'], 0)

    def test_time_not_watched_is_not_counted(self):
        days = thermostat.daily(self.ROWS, ms('2026-10-11 13:00'), TZ)
        second = days[date(2026, 10, 11)]
        observed = second['heating_s'] + second['cooling_s'] + second['idle_s']
        # Of the 13 hours: lost 08:00 to 10:00, and stopped 10:15 to 12:00
        self.assertEqual(observed, (13 - 2 - 1.75) * 3600)

    def test_the_last_state_holds_only_to_the_last_read(self):
        rows = [row('2026-10-10 12:00', 'start'), row('2026-10-10 13:00', active=1)]
        self.assertEqual(thermostat.daily(rows, ms('2026-10-10 13:20'), TZ)[date(2026, 10, 10)]['heating_s'], 1200)
        # No read after the last row: nothing is known past it
        self.assertEqual(thermostat.daily(rows, None, TZ)[date(2026, 10, 10)]['heating_s'], 0)

    def test_room_temperature_is_weighted_by_time(self):
        rows = [row('2026-10-10 00:00', 'start', temp=20.0), row('2026-10-10 18:00', temp=24.0)]
        days = thermostat.daily(rows, ms('2026-10-11 00:00'), TZ)
        self.assertAlmostEqual(days[date(2026, 10, 10)]['room_c'], 21.0)

    def test_current_state_and_when_it_began(self):
        rows = self.ROWS[:6]
        seen = ms('2026-10-11 07:40')
        state = thermostat.current(rows, seen, seen + 30_000, 300_000)
        self.assertEqual(state, {'state': 'idle', 'since_ms': ms('2026-10-11 07:00'), 'mode': 'heat',
                                 'room_c': 21.0, 'target_c': 21.0})
        # Heating since 23:30, through the row at 23:45
        state = thermostat.current(self.ROWS[:3], ms('2026-10-10 23:50'), ms('2026-10-10 23:51'), 300_000)
        self.assertEqual((state['state'], state['since_ms'], state['room_c']),
                         ('heating', ms('2026-10-10 23:30'), 21.5))

    def test_current_state_is_unknown_once_the_logger_goes_quiet(self):
        rows = self.ROWS[:6]
        seen = ms('2026-10-11 07:40')
        state = thermostat.current(rows, seen, seen + 301_000, 300_000)
        self.assertEqual((state['state'], state['since_ms']), ('unobserved', seen))
        self.assertEqual(state['room_c'], 21.0)   # the last temperature seen is kept
        # After a `lost` row it is unknown from that row, whatever the last read says
        state = thermostat.current(self.ROWS[:7], ms('2026-10-11 08:00'), ms('2026-10-11 08:01'), 300_000)
        self.assertEqual((state['state'], state['since_ms'], state['room_c']),
                         ('unobserved', ms('2026-10-11 08:00'), 21.0))
        self.assertEqual(thermostat.current([], None, 0, 300_000)['state'], 'unobserved')

    def test_parse_events(self):
        now = ms('2026-10-11 12:00')
        items = [{'epoch': now / 1000 - 60, 'event': 'change', 'active': 1, 'mode': 1, 'temp': 20.5, 'target': 21},
                 {'epoch': now / 1000 - 30, 'event': 'lost', 'active': None, 'mode': '', 'temp': None}]
        self.assertEqual(thermostat.parse_events(items, now),
                         [(now - 60_000, 'change', 1, 1, 20.5, 21.0), (now - 30_000, 'lost', None, None, None, None)])

    def test_parse_events_rejects_what_is_not_a_row(self):
        now = ms('2026-10-11 12:00')
        good = {'epoch': now / 1000, 'event': 'change', 'active': 0}
        for bad in ({'event': 'change'}, dict(good, event='reboot'), dict(good, active=7),
                    dict(good, temp='warm'), dict(good, epoch=now / 1000 + 7200), dict(good, active=True), 'row'):
            with self.assertRaises(ValueError, msg=bad) as raised:
                thermostat.parse_events([good, bad], now)
            self.assertIn('row 1', str(raised.exception))
        with self.assertRaises(ValueError):
            thermostat.parse_events({'epoch': 1}, now)
        with self.assertRaises(ValueError):
            thermostat.parse_events([good] * (thermostat.MAX_BATCH + 1), now)


class TestWeather(unittest.TestCase):
    NOW = datetime(2026, 10, 10, 21, 20, tzinfo=timezone.utc)

    def reply(self, status=200, **body):
        response = MagicMock()
        response.status_code = status
        response.json.return_value = body
        return response

    def test_hourly_rows_up_to_now_and_the_current_reading(self):
        base = int(datetime(2026, 10, 10, 19, 0, tzinfo=timezone.utc).timestamp())
        body = {'hourly': {'time': [base, base + 3600, base + 7200, base + 10800],
                           'temperature_2m': [12.0, None, 13.5, 14.0]},     # 22:00 is a forecast
                'current': {'time': base + 8100, 'temperature_2m': 13.6}}
        with patch.object(weather.requests, 'get', return_value=self.reply(**body)) as get:
            hourly, current = weather.fetch('49.03', '-122.80', 200, self.NOW)
        self.assertEqual(hourly, [(base * 1000, 12.0), ((base + 7200) * 1000, 13.5)])
        self.assertEqual(current, ((base + 8100) * 1000, 13.6))
        params = get.call_args.kwargs['params']
        self.assertEqual((params['latitude'], params['past_days'], params['timezone']), ('49.03', 92, 'GMT'))

    def test_a_refusal_or_a_failure_raises(self):
        refused = self.reply(400, error=True, reason='Latitude must be in range of -90 to 90')
        with patch.object(weather.requests, 'get', return_value=refused):
            with self.assertRaises(weather.WeatherError) as raised:
                weather.fetch('490', '-122.80', 3, self.NOW)
        self.assertIn('Latitude must be in range', str(raised.exception))
        with patch.object(weather.requests, 'get', side_effect=RuntimeError('no route')):
            with self.assertRaises(weather.WeatherError):
                weather.fetch('49.03', '-122.80', 3, self.NOW)
        with patch.object(weather.requests, 'get', return_value=self.reply(hourly={})):
            with self.assertRaises(weather.WeatherError):
                weather.fetch('49.03', '-122.80', 3, self.NOW)


class TestRoutes(unittest.TestCase):
    NOW = datetime(2026, 10, 12, 12, 0, tzinfo=TZ)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.assertTrue(monitor_app.init_store(os.path.join(self.tmp, 'energy.db')))
        monitor_app._heating_cache.clear()
        monitor_app.weather_state['current'] = None
        self.client = monitor_app.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def event(self, text, event='change', active=0, temp=21.0, target=21.0):
        return {'epoch': ms(text) / 1000, 'event': event, 'active': active, 'mode': 1,
                'temp': temp, 'target': target}

    def upload(self, events, last_seen=None, **kwargs):
        return self.client.post('/thermostat', json={'events': events, 'last_seen': last_seen}, **kwargs)

    def test_rows_are_stored_once_and_the_reply_says_where_to_carry_on(self):
        with pinned_clock(self.NOW):
            events = [self.event('2026-10-12 06:00', 'start'), self.event('2026-10-12 06:30', active=1)]
            r = self.upload(events, ms('2026-10-12 06:31') / 1000)
            self.assertEqual(r.get_json(), {'status': 'ok', 'received': 2, 'previous_epoch': None,
                                            'latest_epoch': ms('2026-10-12 06:30') / 1000})
            r = self.upload(events + [self.event('2026-10-12 07:00')])   # a batch sent again, and one more
            self.assertEqual((r.get_json()['previous_epoch'], r.get_json()['latest_epoch']),
                             (ms('2026-10-12 06:30') / 1000, ms('2026-10-12 07:00') / 1000))
            self.assertEqual(len(monitor_app.db.thermostat_events(0, ms('2026-10-13 00:00'))), 3)
            # With nothing new the uploader still reports the logger's last read
            r = self.upload([], ms('2026-10-12 07:05') / 1000)
            self.assertEqual(r.get_json()['received'], 0)
            self.assertEqual(monitor_app.db.get_meta('thermostat_seen_ms'), str(ms('2026-10-12 07:05')))
            # An older or a future last read does not move it
            self.upload([], ms('2026-10-12 07:00') / 1000)
            self.upload([], ms('2026-10-12 13:00') / 1000)
            self.assertEqual(monitor_app.db.get_meta('thermostat_seen_ms'), str(ms('2026-10-12 12:00')))

    def test_bad_uploads_are_refused(self):
        self.assertEqual(self.client.post('/thermostat', data='<xml/>').status_code, 400)
        r = self.upload([{'epoch': 1, 'event': 'reboot'}])
        self.assertEqual(r.status_code, 400)
        self.assertIn('row 0', r.get_json()['error'])
        monitor_app.db = None
        self.assertEqual(self.upload([]).status_code, 503)

    def test_uploads_need_the_eagle_password_when_one_is_set(self):
        with patch.object(monitor_app, 'EAGLE_PASSWORD', 'test-password-not-a-real-one'):
            self.assertEqual(self.upload([]).status_code, 401)
            token = base64.b64encode(b'eagle:test-password-not-a-real-one').decode()
            r = self.upload([], headers={'Authorization': f'Basic {token}'})
            self.assertEqual(r.status_code, 200)
            # The page reads without one
            self.assertEqual(self.client.get('/api/heating').status_code, 200)

    def test_heating_payload(self):
        with pinned_clock(self.NOW), patch.object(gas, 'READ_DATES', '2026-09-29'), \
                patch.object(gas, 'FURNACE_INPUT_BTUH', None):
            self._heating_payload()

    def _heating_payload(self):
        self.upload([
            self.event('2026-10-10 12:00', 'start'),
            self.event('2026-10-11 06:00', active=1, temp=18.5),
            self.event('2026-10-11 07:00', temp=21.0),
            self.event('2026-10-11 18:00', active=1, temp=20.5),
            self.event('2026-10-11 18:30', temp=21.0),
        ], ms('2026-10-12 11:59:30') / 1000)
        # A degree warmer each 6 hours of Oct 11: 8, 9, 10, 11
        monitor_app.db.write_many('outdoor_temp_c', [
            (ms('2026-10-11 00:00') + i * 6 * HOUR, 8.0 + i) for i in range(4)])
        monitor_app.db.write_many('outdoor_temp_c', [(ms('2026-10-12 11:00'), 12.5)])

        body = self.client.get('/api/heating').get_json()
        self.assertEqual(set(body), {'updated', 'thermostat', 'outdoor', 'days', 'gas'})
        self.assertEqual(body['thermostat'], {
            'state': 'idle', 'mode': 'heat', 'room_c': 21.0, 'target_c': 21.0,
            'since': datetime.fromisoformat('2026-10-11T18:30').replace(tzinfo=TZ).astimezone(timezone.utc).isoformat(),
            'observed_until': datetime.fromisoformat('2026-10-12T11:59:30').replace(tzinfo=TZ).astimezone(timezone.utc).isoformat()})
        self.assertEqual((body['outdoor']['temp_c'], body['outdoor']['source']), (12.5, 'Open-Meteo'))

        # Sep 12 to Oct 12: 31 days, which reaches back past the gas period's start
        days = {day['date']: day for day in body['days']}
        self.assertEqual((body['days'][0]['date'], body['days'][-1]['date'], len(days)),
                         ('2026-09-12', '2026-10-12', 31))
        self.assertEqual(days['2026-10-09'], {
            'date': '2026-10-09', 'heating_h': None, 'cooling_h': None, 'heat_cycles': None,
            'cool_cycles': None, 'unobserved_h': 24.0, 'room_c': None, 'outdoor_c': None,
            'outdoor_min_c': None, 'outdoor_max_c': None, 'hdd': None})
        self.assertEqual((days['2026-10-10']['heating_h'], days['2026-10-10']['unobserved_h']), (0.0, 12.0))
        eleventh = days['2026-10-11']
        self.assertEqual((eleventh['heating_h'], eleventh['heat_cycles'], eleventh['unobserved_h']), (1.5, 2, 0.0))
        self.assertEqual((eleventh['outdoor_c'], eleventh['outdoor_min_c'], eleventh['outdoor_max_c'], eleventh['hdd']),
                         (9.5, 8.0, 11.0, 8.5))
        self.assertAlmostEqual(eleventh['room_c'], (5 * 21.0 + 1 * 18.5 + 11 * 21.0 + 0.5 * 20.5 + 6.5 * 21.0) / 24, places=1)
        self.assertEqual((days['2026-10-12']['heating_h'], days['2026-10-12']['unobserved_h']), (0.0, 0.01))

        # Gas: Sep 30 to Oct 31, 32 days, of which 12.5 have passed
        g = body['gas']
        self.assertEqual((g['period']['start'][:10], g['period']['next_start'][:10]), ('2026-09-30', '2026-11-01'))
        self.assertEqual((g['period']['days'], g['period']['cycle_days']), (13, 32))
        rate = 60_000 / 947_817
        self.assertEqual(g['model'], {'base_gj_per_day': gas.BASE_GJ_PER_DAY, 'furnace_btu_per_hour': 60000,
                                      'furnace_gj_per_hour': round(rate, 5), 'furnace_assumed': True})
        self.assertEqual(g['usage']['heating_h'], 1.5)
        self.assertEqual(g['usage']['furnace_gj'], round(1.5 * rate, 3))
        self.assertEqual(g['usage']['gj'], round(12.5 * gas.BASE_GJ_PER_DAY + 1.5 * rate, 3))
        self.assertEqual(g['usage']['unobserved_h'], 10 * 24 + 12.0)   # and 30 s of today
        self.assertEqual(g['cost'], gas.bill(12.5 * gas.BASE_GJ_PER_DAY + 1.5 * rate, 13))
        # $0, the 12 completed days, and now
        points = g['trend']['points']
        self.assertEqual((len(points), points[0], points[-1][0]), (14, [0.0, 0.0], 12.5))
        self.assertEqual(points[11], [11.0, gas.bill(gas.usage(11, 0), 11)['total_cost']])
        self.assertEqual(points[12], [12.0, gas.bill(gas.usage(12, 1.5), 12)['total_cost']])
        self.assertGreater(g['trend']['projected_total'], points[-1][1])
        # Logging began inside the previous period, so nothing seeds the trend
        self.assertEqual(g['trend']['estimates'][0][0], 2.0)

    def test_heating_payload_with_nothing_stored(self):
        with pinned_clock(self.NOW):
            body = self.client.get('/api/heating').get_json()
        self.assertEqual(body['thermostat']['state'], 'unobserved')
        self.assertIsNone(body['outdoor']['temp_c'])
        self.assertEqual(body['gas']['usage']['heating_h'], 0.0)
        self.assertIsNotNone(body['gas']['trend']['projected_total'])   # the base load still bills
        monitor_app.db = None
        self.assertEqual(self.client.get('/api/heating').status_code, 503)

    def test_previous_gas_bill_seeds_a_period_the_log_covers(self):
        with patch.object(gas, 'READ_DATES', '2026-09-29'), patch.object(gas, 'FURNACE_INPUT_BTUH', None):
            start = datetime(2026, 12, 1, tzinfo=TZ)
            self.assertIsNone(monitor_app._previous_gas_bill(start))
            monitor_app._heating_cache.clear()
            # Logged from Nov 1, the first day of the period before: 2 hours of heat in it
            monitor_app.db.add_thermostat_events([
                row('2026-11-01 08:00', 'start'), row('2026-11-10 06:00', active=1),
                row('2026-11-10 08:00'), row('2026-12-02 06:00', active=1)])
            self.assertEqual(monitor_app._previous_gas_bill(start),
                             gas.bill(gas.usage(30, 2.0), 30)['total_cost'])

    def test_refresh_weather_stores_the_hours_and_asks_for_less_next_time(self):
        now = datetime.now(timezone.utc)
        base = int(now.timestamp()) // 3600 * 3600
        hourly = [((base - 3600) * 1000, 11.0), (base * 1000, 12.0)]
        with patch.object(weather, 'fetch', return_value=(hourly, (base * 1000 + 900_000, 12.4))) as fetch:
            monitor_app.refresh_weather()
            monitor_app.refresh_weather()
        self.assertEqual([call.args[2] for call in fetch.call_args_list], [monitor_app.WEATHER_FIRST_DAYS, 2])
        self.assertEqual(monitor_app.db.latest('outdoor_temp_c', 0, base * 1000 + 1), (base * 1000, 12.0))
        self.assertEqual(monitor_app.weather_state['current'], (base * 1000 + 900_000, 12.4))

    def test_a_failed_weather_fetch_keeps_what_is_held(self):
        monitor_app.weather_state['current'] = (1, 9.0)
        with patch.object(weather, 'fetch', side_effect=weather.WeatherError('HTTP 500, ')), \
                patch.object(monitor_app, 'scheduler', MagicMock()) as scheduler:
            with self.assertLogs(monitor_app.logger, 'WARNING'):
                monitor_app.refresh_weather()
        self.assertEqual(monitor_app.weather_state['current'], (1, 9.0))
        # And it is tried again in a few minutes, not at the next half hour
        job, kwargs = scheduler.modify_job.call_args.args[0], scheduler.modify_job.call_args.kwargs
        self.assertEqual(job, 'weather')
        wait = kwargs['next_run_time'] - datetime.now(timezone.utc)
        self.assertLess(abs(wait - timedelta(minutes=monitor_app.WEATHER_RETRY_MINUTES)), timedelta(seconds=5))

    def test_a_good_weather_fetch_leaves_the_schedule_alone(self):
        with patch.object(weather, 'fetch', return_value=([], None)), \
                patch.object(monitor_app, 'scheduler', MagicMock()) as scheduler:
            monitor_app.refresh_weather()
        scheduler.modify_job.assert_not_called()


if __name__ == '__main__':
    unittest.main()
