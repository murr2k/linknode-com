#!/usr/bin/env python3
"""
One-off backfill: copy InfluxDB history into the SQLite store.

Runs INSIDE the eagle-monitor machine, which has the InfluxDB token and the volume.
Not part of the image; upload it for the run:

  fly ssh sftp shell -a linknode-eagle-monitor
    put fly/eagle-monitor/migrate_influx.py /tmp/migrate_influx.py
  fly ssh console -a linknode-eagle-monitor -C "python /tmp/migrate_influx.py"

Safe to re-run: rows go in with INSERT OR IGNORE, so a backfilled row never
overwrites a live write, and an interrupted run can simply be repeated (--start
skips days already copied). Memory stays bounded: records are streamed one day at a
time with only _time and _value kept, and committed every BATCH rows, so the 256MB
machine's app keeps running (scale to 512MB anyway for headroom).
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, '/app')
import store  # noqa: E402
from influxdb_client import InfluxDBClient  # noqa: E402

INFLUXDB_URL = os.getenv('INFLUXDB_URL', 'http://linknode-influxdb.internal:8086')
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN')
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG', 'linknode')
INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET', 'energy')
DB_PATH = os.getenv('DB_PATH', '/data/energy.db')

BATCH = 5000
CHUNK = timedelta(days=1)
FAR_FUTURE = datetime(2100, 1, 1, tzinfo=timezone.utc)
FIELDS = list(store.FIELD_IDS) + list(store.TEXT_FIELDS)


def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def field_filter(field):
    return (f'|> filter(fn: (r) => r["_measurement"] == "energy_monitor" '
            f'and r["_field"] == "{field}")')


def earliest(query_api, field):
    """Oldest timestamp of a field across all series (first() per series is cheap)."""
    q = (f'from(bucket: "{INFLUXDB_BUCKET}") |> range(start: 0, stop: {iso(FAR_FUTURE)}) '
         f'{field_filter(field)} |> first() |> keep(columns: ["_time"])')
    times = [rec.get_time() for rec in query_api.query_stream(q, org=INFLUXDB_ORG)]
    return min(times) if times else None


def copy_chunk(query_api, db, field, start, stop, counts):
    q = (f'from(bucket: "{INFLUXDB_BUCKET}") |> range(start: {iso(start)}, stop: {iso(stop)}) '
         f'{field_filter(field)} |> keep(columns: ["_time", "_value"])')
    num, text = [], []
    for rec in query_api.query_stream(q, org=INFLUXDB_ORG):
        ts = store.to_ms(rec.get_time())
        value = rec.get_value()
        # InfluxDB cannot store a null, and the client reads an empty string field back
        # as None; the ef68 radio's message_text was always empty.
        if value is None and field in store.TEXT_FIELDS:
            value = ''
        # Route by the value's type, not the field name: link_strength is a string.
        if isinstance(value, str):
            text.append((field, ts, value))
        elif value is not None and field in store.FIELD_IDS:
            num.append((store.FIELD_IDS[field], ts, float(value)))
        else:
            counts['skipped'] += 1
            continue
        if len(num) + len(text) >= BATCH:
            db.insert_ignore(num, text)
            counts['rows'] += len(num) + len(text)
            num, text = [], []
    if num or text:
        db.insert_ignore(num, text)
        counts['rows'] += len(num) + len(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--start', help='resume from this UTC date (YYYY-MM-DD)')
    parser.add_argument('--fields', nargs='+', default=FIELDS, choices=FIELDS)
    args = parser.parse_args()

    if not INFLUXDB_TOKEN:
        sys.exit('INFLUXDB_TOKEN is not set (run this inside the eagle-monitor machine)')

    db = store.Store(DB_PATH)
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG,
                            timeout=120_000)
    query_api = client.query_api()
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    resume = (datetime.strptime(args.start, '%Y-%m-%d').replace(tzinfo=timezone.utc)
              if args.start else None)

    print(f'SQLite store {DB_PATH}, live writes since {store.EPOCH + timedelta(milliseconds=db.created_ms())}')
    for field in args.fields:
        first = earliest(query_api, field)
        if first is None:
            print(f'{field}: no data')
            continue
        start = resume or first.replace(hour=0, minute=0, second=0, microsecond=0)
        counts = {'rows': 0, 'skipped': 0}
        t0 = time.monotonic()
        day = start
        while day < now:
            copy_chunk(query_api, db, field, day, min(day + CHUNK, now), counts)
            day += CHUNK
            if day.day == 1:
                print(f'  {field}: through {day:%Y-%m-%d}, {counts["rows"]} rows', flush=True)
        # Future-stamped points (the parser accepts clocks up to a year ahead)
        copy_chunk(query_api, db, field, now, FAR_FUTURE, counts)
        print(f'{field}: {counts["rows"]} rows offered from {first:%Y-%m-%d} '
              f'({counts["skipped"]} skipped) in {time.monotonic() - t0:.0f}s', flush=True)

    client.close()


if __name__ == '__main__':
    main()
