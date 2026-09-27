#!/usr/bin/env python3
"""
Backfill the SQLite store with the last N days (default 30) of InfluxDB history,
then check the result against InfluxDB.

Runs INSIDE the eagle-monitor machine, which has the InfluxDB token and the
volume. Not part of the image; upload it for the run:

  fly ssh sftp put -a linknode-eagle-monitor fly/eagle-monitor/backfill_recent.py /tmp/backfill_recent.py
  fly ssh console -a linknode-eagle-monitor -C "python /tmp/backfill_recent.py"

Imports [go-live - N days, go-live): from go-live on, the store was written live.
Rows go in with INSERT OR IGNORE, so a live row is never overwritten and the run
can be repeated.

Built for a throttled shared CPU: InfluxDB returns bare epoch-ns/value CSV with no
annotations, parsed with the csv module. The first full-history attempt parsed
into influxdb-client FluxRecords, and that per-row cost is what made it crawl.
"""

import argparse
import csv
import io
import os
import sys
import time
from datetime import timedelta

import requests

sys.path.insert(0, '/app')
import store  # noqa: E402

INFLUXDB_URL = os.getenv('INFLUXDB_URL', 'http://linknode-influxdb.internal:8086')
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN')
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG', 'linknode')
INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET', 'energy')
DB_PATH = os.getenv('DB_PATH', '/data/energy.db')

BATCH = 5000
REL_TOL = 1e-9
FIELDS = list(store.FIELD_IDS) + list(store.TEXT_FIELDS)


def iso(ms):
    return (store.EPOCH + timedelta(milliseconds=ms)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def base(field, start_ms, stop_ms):
    return (f'from(bucket: "{INFLUXDB_BUCKET}") |> range(start: {iso(start_ms)}, stop: {iso(stop_ms)}) '
            f'|> filter(fn: (r) => r["_measurement"] == "energy_monitor" and r["_field"] == "{field}")')


def flux_rows(query):
    """Stream a Flux result as plain CSV; yields (column index, row) per record."""
    resp = requests.post(
        f'{INFLUXDB_URL}/api/v2/query', params={'org': INFLUXDB_ORG},
        headers={'Authorization': f'Token {INFLUXDB_TOKEN}', 'Accept': 'application/csv'},
        json={'query': query, 'type': 'flux',
              'dialect': {'header': True, 'annotations': [], 'delimiter': ','}},
        stream=True, timeout=300)
    resp.raise_for_status()
    # Read the byte stream through csv rather than resp.iter_lines(): iter_lines
    # emits a spurious empty line when a chunk ends between \r and \n, which would
    # be mistaken for a table boundary.
    resp.raw.decode_content = True
    header = None
    for row in csv.reader(io.TextIOWrapper(resp.raw, encoding='utf-8', newline='')):
        if not any(row):
            header = None  # a blank line precedes a table with a new schema
            continue
        if header is None:
            header = {name: i for i, name in enumerate(row)}
            continue
        yield header, row


def flux_scalar(query):
    for header, row in flux_rows(query):
        value = row[header['_value']]
        return float(value) if value != '' else None
    return None


def import_field(db, field, start_ms, stop_ms):
    query = (base(field, start_ms, stop_ms)
             + ' |> map(fn: (r) => ({t: int(v: r._time), v: r._value})) |> keep(columns: ["t", "v"])')
    fid = store.FIELD_IDS.get(field)
    num, text, total = [], [], 0
    for header, row in flux_rows(query):
        ts_ms = int(row[header['t']]) // 1_000_000  # ns -> ms, floored like store.to_ms
        value = row[header['v']]
        if fid is None:
            text.append((field, ts_ms, value))
        elif value != '':
            num.append((fid, ts_ms, float(value)))
        if len(num) + len(text) >= BATCH:
            db.insert_ignore(num, text)
            total += len(num) + len(text)
            num, text = [], []
    if num or text:
        db.insert_ignore(num, text)
        total += len(num) + len(text)
    return total


def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= REL_TOL * max(abs(a), abs(b), 1e-12)


def check(db, start_ms, stop_ms):
    print(f'\n{"field":22} {"metric":10} {"influx":>18} {"sqlite":>18}  status')
    failures = 0
    for field in store.FIELD_IDS:
        q = base(field, start_ms, stop_ms) + ' |> group()'
        agg = db.agg(field, start_ms, stop_ms)
        checks = [
            ('count', flux_scalar(q + ' |> count()') or 0, agg['count']),
            ('min', flux_scalar(q + ' |> min()'), agg['min']),
            ('max', flux_scalar(q + ' |> max()'), agg['max']),
            ('mean', flux_scalar(q + ' |> mean()'), agg['mean']),
        ]
        if field == 'power_w':
            checks.append(('energy_wh', flux_scalar(q + ' |> sort(columns: ["_time"]) |> integral(unit: 1h)'),
                           db.integral_wh(start_ms, stop_ms)))
        for metric, fv, sv in checks:
            ok = close(float(fv) if fv is not None else None, float(sv) if sv is not None else None)
            failures += not ok
            print(f'{field:22} {metric:10} {fv!s:>18} {sv!s:>18}  {"OK" if ok else "DIFF"}')
    return failures


def main():
    parser = argparse.ArgumentParser(description='Backfill recent InfluxDB history into SQLite')
    parser.add_argument('--days', type=int, default=30)
    args = parser.parse_args()
    if not INFLUXDB_TOKEN:
        sys.exit('INFLUXDB_TOKEN is not set (run this inside the eagle-monitor machine)')

    db = store.Store(DB_PATH)
    stop_ms = db.created_ms()           # go-live: live writes own everything after this
    start_ms = stop_ms - args.days * 86_400_000
    print(f'backfilling [{iso(start_ms)}, {iso(stop_ms)}) into {DB_PATH}')
    for field in FIELDS:
        t = time.monotonic()
        rows = import_field(db, field, start_ms, stop_ms)
        print(f'  {field:22} {rows:>8} rows  {time.monotonic() - t:6.1f}s', flush=True)
    failures = check(db, start_ms, stop_ms)
    print(f'\n{failures} difference(s)')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
