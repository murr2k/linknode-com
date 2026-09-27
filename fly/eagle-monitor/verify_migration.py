#!/usr/bin/env python3
"""
Compare InfluxDB and the SQLite store, before and after the backfill.

Runs INSIDE the eagle-monitor machine (upload like migrate_influx.py):

  fly ssh console -a linknode-eagle-monitor -C "python /tmp/verify_migration.py --precheck"
  fly ssh console -a linknode-eagle-monitor -C "python /tmp/verify_migration.py"

--precheck (InfluxDB only; run before sizing the volume): bucket retention, and per
field the row count, time span and tag sets. Several tag sets on one field mean the
Grafana/Flux per-series integral differed from a merged one.

Default: for fixed windows (1h, 24h, 7d, then each ISO week of history)
compare count/min/max/mean and the power integral. Flux side uses merged-series
semantics (group() |> sort(_time)) because that is what SQLite computes; the
per-series Grafana integral is printed alongside for reference. All windows end at
a fixed stop one minute in the past, [start, stop) on both sides.

Expected, explainable differences: SQLite has more rows than InfluxDB for windows
after dual-write began (the InfluxDB copy is best-effort), and fewer where InfluxDB
held the same reading under two tag sets (cloud + Pi uploads, both radios).
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from influxdb_client import InfluxDBClient

sys.path.insert(0, '/app')
try:
    import store  # absent before the SQLite release: --precheck still works
except ImportError:
    store = None

INFLUXDB_URL = os.getenv('INFLUXDB_URL', 'http://linknode-influxdb.internal:8086')
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN')
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG', 'linknode')
INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET', 'energy')
DB_PATH = os.getenv('DB_PATH', '/data/energy.db')

REL_TOL = 1e-9
FAR_FUTURE = datetime(2100, 1, 1, tzinfo=timezone.utc)
TAGS = '["device_mac", "meter_mac", "message_type"]'
NUMERIC_FIELDS = ['power_w', 'energy_delivered_kwh', 'energy_received_kwh', 'price_per_kwh']
TEXT_FIELDS = ['link_strength', 'message_text']


def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


class Flux:
    def __init__(self):
        self.client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG,
                                     timeout=300_000)
        self.api = self.client.query_api()

    def base(self, field, start, stop):
        return (f'from(bucket: "{INFLUXDB_BUCKET}") |> range(start: {iso(start)}, stop: {iso(stop)}) '
                f'|> filter(fn: (r) => r["_measurement"] == "energy_monitor" and r["_field"] == "{field}")')

    def rows(self, q):
        return [rec for table in self.api.query(q, org=INFLUXDB_ORG) for rec in table.records]

    def scalar(self, q):
        recs = self.rows(q)
        return recs[0].get_value() if recs else None


def precheck(flux):
    bucket = flux.client.buckets_api().find_bucket_by_name(INFLUXDB_BUCKET)
    rules = bucket.retention_rules if bucket else []
    retention = rules[0].every_seconds if rules else None
    print(f'bucket {INFLUXDB_BUCKET}: retention '
          f'{"infinite" if not retention else f"{retention / 86400:.0f} days"}')
    for field in NUMERIC_FIELDS + TEXT_FIELDS:
        base = flux.base(field, datetime(1970, 1, 1, tzinfo=timezone.utc), FAR_FUTURE)
        counts = flux.rows(f'{base} |> group(columns: {TAGS}) |> count()')
        firsts = {tuple(r.values.get(t) for t in ('device_mac', 'meter_mac', 'message_type')): r.get_time()
                  for r in flux.rows(f'{base} |> group(columns: {TAGS}) |> first()')}
        lasts = {tuple(r.values.get(t) for t in ('device_mac', 'meter_mac', 'message_type')): r.get_time()
                 for r in flux.rows(f'{base} |> group(columns: {TAGS}) |> last()')}
        total = sum(r.get_value() for r in counts)
        print(f'\n{field}: {total} rows in {len(counts)} tag set(s)')
        for r in counts:
            key = tuple(r.values.get(t) for t in ('device_mac', 'meter_mac', 'message_type'))
            print(f'  {key}: {r.get_value():>9} rows  {firsts.get(key):%Y-%m-%d %H:%M} .. '
                  f'{lasts.get(key):%Y-%m-%d %H:%M}')


def windows(db, flux, stop):
    """1h, 24h, 7d back from stop, then every ISO week of history. Windows stay at a
    week or less because the merged integral sorts the window in InfluxDB's memory."""
    for label, span in (('1h', timedelta(hours=1)), ('24h', timedelta(days=1)),
                        ('7d', timedelta(days=7))):
        yield label, stop - span, stop
    first = flux.rows(f'{flux.base("power_w", datetime(1970, 1, 1, tzinfo=timezone.utc), stop)} '
                      f'|> first() |> keep(columns: ["_time"])')
    if not first:
        return
    day = min(r.get_time() for r in first).replace(hour=0, minute=0, second=0, microsecond=0)
    week = day - timedelta(days=day.weekday())
    while week < stop:
        nxt = week + timedelta(days=7)
        yield f'{week:%G-W%V}', week, min(nxt, stop)
        week = nxt


def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= REL_TOL * max(abs(a), abs(b), 1e-12)


def count_status(influx_rows, influx_distinct, sqlite_rows, live):
    """OK: equal. DUP: InfluxDB held some timestamps under two tag sets and SQLite
    stored each once (sqlite == distinct timestamps). LIVE: the window overlaps
    dual-write and SQLite has rows the best-effort InfluxDB copy missed. DIFF: neither."""
    if influx_rows == sqlite_rows:
        return 'OK'
    if influx_distinct == sqlite_rows:
        return 'DUP'
    if live and sqlite_rows > influx_distinct:
        return 'LIVE'
    return 'DIFF'


def compare(db, flux):
    stop = datetime.now(timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=1)
    created = store.EPOCH + timedelta(milliseconds=db.created_ms())
    print(f'window stop {iso(stop)}; SQLite live writes since {iso(created)}\n')
    print(f'{"window":8} {"metric":14} {"influx":>18} {"sqlite":>18}  status')
    failures = 0

    def report(label, metric, fv, sv, status):
        nonlocal failures
        failures += status == 'DIFF'
        print(f'{label:8} {metric:14} {fmt(fv):>18} {fmt(sv):>18}  {status}')

    def distinct(base):
        return flux.scalar(f'{base} |> group() |> unique(column: "_time") |> count()') or 0

    for label, start, end in windows(db, flux, stop):
        base = flux.base('power_w', start, end)
        s_ms, e_ms = store.to_ms(start), store.to_ms(end)
        agg = db.agg('power_w', s_ms, e_ms)
        rows = flux.scalar(f'{base} |> group() |> count()') or 0
        cstat = count_status(rows, distinct(base) if rows != agg['count'] else rows,
                             agg['count'], end > created)
        report(label, 'count', rows, agg['count'], cstat)
        # Values can only be expected to match exactly when the row sets match.
        explained = cstat if cstat in ('DUP', 'LIVE') else 'DIFF'
        for metric, fv, sv in (
            ('min', flux.scalar(f'{base} |> group() |> min()'), agg['min']),
            ('max', flux.scalar(f'{base} |> group() |> max()'), agg['max']),
            ('mean', flux.scalar(f'{base} |> group() |> mean()'), agg['mean']),
            ('energy_wh', flux.scalar(f'{base} |> group() |> sort(columns: ["_time"]) '
                                      f'|> integral(unit: 1h)'), db.integral_wh(s_ms, e_ms)),
        ):
            report(label, metric, fv, sv, 'OK' if close(fv, sv) else explained)
        grafana = flux.scalar(f'{base} |> integral(unit: 1h) |> group() |> sum()')
        print(f'{label:8} {"(per-series)":14} {fmt(grafana):>18} {"":>18}  info')

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    stop_ms = store.to_ms(stop)
    for field in NUMERIC_FIELDS[1:] + TEXT_FIELDS:
        base = flux.base(field, epoch, stop)
        rows = flux.scalar(f'{base} |> group() |> count()') or 0
        if field in TEXT_FIELDS:
            sv = db._query('SELECT COUNT(*) FROM text_readings WHERE field = ? AND ts_ms < ?',
                           (field, stop_ms))[0][0]
        else:
            sv = db.agg(field, 0, stop_ms)['count']
        report('all', field[:14], rows, sv,
               count_status(rows, distinct(base) if rows != sv else rows, sv, True))

    print(f'\n{failures} unexplained difference(s). '
          'DUP = same timestamp stored under two InfluxDB tag sets, kept once; '
          'LIVE = rows the best-effort InfluxDB copy missed.')
    return failures


def fmt(v):
    if v is None:
        return '-'
    return f'{v:.6f}' if isinstance(v, float) else str(v)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--precheck', action='store_true', help='InfluxDB inventory only')
    args = parser.parse_args()
    if not INFLUXDB_TOKEN:
        sys.exit('INFLUXDB_TOKEN is not set (run this inside the eagle-monitor machine)')
    flux = Flux()
    try:
        if args.precheck:
            precheck(flux)
            return 0
        if store is None:
            sys.exit('store.py not found in /app: deploy the SQLite release first')
        return 1 if compare(store.Store(DB_PATH), flux) else 0
    finally:
        flux.client.close()


if __name__ == '__main__':
    sys.exit(main())
