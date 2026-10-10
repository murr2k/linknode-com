#!/usr/bin/env python3
"""
SQLite time-series store for the Eagle monitor (replaces InfluxDB).

One row per (field, timestamp). Writing the same key again overwrites it, which is
InfluxDB's point identity: the Pi re-stamps a stale meter reading with the meter's
LastContact time, so a stale read lands on an existing key instead of adding a row.
reads_24h counts rows and depends on that.

Every field comes from exactly one Eagle message type (power_w from
InstantaneousDemand, energy_* from CurrentSummation, price from PriceCluster), so the
InfluxDB tags (device_mac, meter_mac, message_type) add nothing to the key for the
single meter this service stores; the second radio (ef68) is filtered upstream.

Two things that are not meter readings share the file: the outdoor temperature (a
numeric field like the others, hourly, from weather.py) and the thermostat's event log
(its own table, one row per change of state, from the Pi's t5 uploader).

Connections are short-lived: one per operation. Werkzeug starts a thread per request,
so a thread-local connection would effectively be per-request anyway and would only
close when the thread is collected, holding WAL read snapshots open meanwhile.
"""

import os
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone, timedelta

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# Numeric fields share one narrow table keyed by a small integer id.
FIELD_IDS = {
    'power_w': 1,
    'energy_delivered_kwh': 2,
    'energy_received_kwh': 3,
    'price_per_kwh': 4,
    'outdoor_temp_c': 5,
}
# String fields (LinkStrength arrives as text like "0x64").
TEXT_FIELDS = ('link_strength', 'message_text')

# Busy timeout stays under the 2s Fly HTTP health-check timeout.
BUSY_TIMEOUT_S = 1.5

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    field_id INTEGER NOT NULL,
    ts_ms    INTEGER NOT NULL,
    value    REAL    NOT NULL,
    PRIMARY KEY (field_id, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS text_readings (
    field TEXT    NOT NULL,
    ts_ms INTEGER NOT NULL,
    value TEXT    NOT NULL,
    PRIMARY KEY (field, ts_ms)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS thermostat_events (
    ts_ms  INTEGER PRIMARY KEY,
    event  TEXT    NOT NULL,
    active INTEGER,
    mode   INTEGER,
    temp   REAL,
    target REAL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

UPSERT_NUM = """
INSERT INTO readings (field_id, ts_ms, value) VALUES (?, ?, ?)
ON CONFLICT (field_id, ts_ms) DO UPDATE SET value = excluded.value
"""
UPSERT_TEXT = """
INSERT INTO text_readings (field, ts_ms, value) VALUES (?, ?, ?)
ON CONFLICT (field, ts_ms) DO UPDATE SET value = excluded.value
"""
INSERT_NUM_IGNORE = "INSERT OR IGNORE INTO readings (field_id, ts_ms, value) VALUES (?, ?, ?)"
INSERT_TEXT_IGNORE = "INSERT OR IGNORE INTO text_readings (field, ts_ms, value) VALUES (?, ?, ?)"
INSERT_THERMOSTAT_IGNORE = ("INSERT OR IGNORE INTO thermostat_events (ts_ms, event, active, mode, temp, target) "
                            "VALUES (?, ?, ?, ?, ?, ?)")
THERMOSTAT_COLUMNS = 'ts_ms, event, active, mode, temp, target'


def to_ms(dt):
    """Epoch milliseconds for an aware datetime. Integer floor, so the same instant
    always maps to the same key (float math can differ by 1)."""
    return (dt - EPOCH) // timedelta(milliseconds=1)


def now_ms():
    return to_ms(datetime.now(timezone.utc))


class Store:
    def __init__(self, path):
        self.path = path
        self._write_lock = threading.Lock()
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with closing(self._connect()) as conn:
            # WAL is persistent in the file; set once here, not per connection.
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript(SCHEMA)
            # First-open time marks when this store started receiving live writes.
            conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('created_ms', ?)",
                         (str(now_ms()),))
            conn.commit()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=BUSY_TIMEOUT_S)
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn

    def _query(self, sql, params=()):
        with closing(self._connect()) as conn:
            return conn.execute(sql, params).fetchall()

    def _write(self, statements):
        """Run [(sql, rows)] executemany batches in one transaction."""
        with self._write_lock, closing(self._connect()) as conn:
            with conn:
                for sql, rows in statements:
                    if rows:
                        conn.executemany(sql, rows)

    # -- writes -------------------------------------------------------------

    def write(self, ts_ms, values):
        """Upsert one reading's fields at ts_ms. Returns the number of fields stored."""
        num = [(FIELD_IDS[k], ts_ms, float(v)) for k, v in values.items()
               if k in FIELD_IDS and v is not None]
        text = [(k, ts_ms, str(v)) for k, v in values.items()
                if k in TEXT_FIELDS and v is not None]
        if num or text:
            self._write([(UPSERT_NUM, num), (UPSERT_TEXT, text)])
        return len(num) + len(text)

    def insert_ignore(self, num_rows=(), text_rows=()):
        """Backfill rows without overwriting anything already stored.
        num_rows: (field_id, ts_ms, value); text_rows: (field, ts_ms, value)."""
        self._write([(INSERT_NUM_IGNORE, list(num_rows)), (INSERT_TEXT_IGNORE, list(text_rows))])

    def write_many(self, field, points):
        """Upsert [(ts_ms, value)] of one numeric field in a single transaction."""
        fid = FIELD_IDS[field]
        self._write([(UPSERT_NUM, [(fid, ts_ms, float(value)) for ts_ms, value in points])])

    def add_thermostat_events(self, rows):
        """Store thermostat rows (ts_ms, event, active, mode, temp, target). A row
        already held is left as it is, so a batch sent twice changes nothing."""
        self._write([(INSERT_THERMOSTAT_IGNORE, list(rows))])

    # -- reads (all bounded by end_ms, which callers pass as now: InfluxDB range()
    #    stops at now, so future-stamped points never count) -------------------

    def latest(self, field, start_ms, end_ms):
        """(ts_ms, value) of the newest reading in [start_ms, end_ms), or None."""
        rows = self._query(
            'SELECT ts_ms, value FROM readings WHERE field_id = ? AND ts_ms >= ? AND ts_ms < ? '
            'ORDER BY ts_ms DESC LIMIT 1',
            (FIELD_IDS[field], start_ms, end_ms))
        return rows[0] if rows else None

    def agg(self, field, start_ms, end_ms):
        """min/max/mean/count over [start_ms, end_ms). Values are None when count is 0."""
        mn, mx, mean, count = self._query(
            'SELECT MIN(value), MAX(value), AVG(value), COUNT(*) FROM readings '
            'WHERE field_id = ? AND ts_ms >= ? AND ts_ms < ?',
            (FIELD_IDS[field], start_ms, end_ms))[0]
        return {'min': mn, 'max': mx, 'mean': mean, 'count': count}

    def integral_wh(self, start_ms, end_ms):
        """Trapezoidal integral of power_w over [start_ms, end_ms), in Wh.

        Matches Flux integral(unit: 1h): only in-range points, no interpolation to the
        range edges, and straight lines across gaps (outages are bridged, not zeroed).
        None with no points, 0.0 with one point."""
        count, total = self._query(
            'SELECT COUNT(*), SUM(CASE WHEN prev_ts IS NULL THEN NULL '
            '                          ELSE (ts_ms - prev_ts) * (value + prev_v) / 2.0 END) '
            'FROM (SELECT ts_ms, value, '
            '             LAG(ts_ms) OVER (ORDER BY ts_ms) AS prev_ts, '
            '             LAG(value) OVER (ORDER BY ts_ms) AS prev_v '
            '      FROM readings WHERE field_id = ? AND ts_ms >= ? AND ts_ms < ?)',
            (FIELD_IDS['power_w'], start_ms, end_ms))[0]
        if not count:
            return None
        return (total or 0.0) / 3_600_000.0  # W*ms -> Wh

    def integral_wh_buckets(self, start_ms, end_ms, bucket_ms):
        """integral_wh split into bucket_ms buckets counted from start_ms: {index: Wh}.

        Each straight-line segment goes to the bucket its later point falls in, so the
        buckets add up to integral_wh(start_ms, end_ms). One pass, like integral_wh."""
        rows = self._query(
            'SELECT (ts_ms - ?) / ? AS bucket, SUM((ts_ms - prev_ts) * (value + prev_v) / 2.0) '
            'FROM (SELECT ts_ms, value, '
            '             LAG(ts_ms) OVER (ORDER BY ts_ms) AS prev_ts, '
            '             LAG(value) OVER (ORDER BY ts_ms) AS prev_v '
            '      FROM readings WHERE field_id = ? AND ts_ms >= ? AND ts_ms < ?) '
            'WHERE prev_ts IS NOT NULL GROUP BY bucket',
            (start_ms, bucket_ms, FIELD_IDS['power_w'], start_ms, end_ms))
        return {bucket: total / 3_600_000.0 for bucket, total in rows}

    def series(self, field, start_ms, end_ms, bucket_ms=None):
        """[(t_ms, mean, min, max)] over [start_ms, end_ms). With bucket_ms, epoch-aligned
        buckets stamped at the bucket's end, clipped to end_ms (aggregateWindow semantics).
        Min and max keep short peaks that the mean averages away; raw points repeat
        the value for both."""
        fid = FIELD_IDS[field]
        if not bucket_ms:
            rows = self._query(
                'SELECT ts_ms, value FROM readings WHERE field_id = ? AND ts_ms >= ? AND ts_ms < ? '
                'ORDER BY ts_ms', (fid, start_ms, end_ms))
            return [(ts, value, value, value) for ts, value in rows]
        rows = self._query(
            'SELECT (ts_ms / ?) * ? AS bucket, AVG(value), MIN(value), MAX(value) FROM readings '
            'WHERE field_id = ? AND ts_ms >= ? AND ts_ms < ? GROUP BY bucket ORDER BY bucket',
            (bucket_ms, bucket_ms, fid, start_ms, end_ms))
        return [(min(bucket + bucket_ms, end_ms), mean, lo, hi) for bucket, mean, lo, hi in rows]

    def thermostat_events(self, start_ms, end_ms):
        """Thermostat rows in [start_ms, end_ms), oldest first, led by the newest row
        before start_ms when there is one: it carries the state at start_ms."""
        before = self._query(
            f'SELECT {THERMOSTAT_COLUMNS} FROM thermostat_events WHERE ts_ms < ? '
            'ORDER BY ts_ms DESC LIMIT 1', (start_ms,))
        return before + self._query(
            f'SELECT {THERMOSTAT_COLUMNS} FROM thermostat_events WHERE ts_ms >= ? AND ts_ms < ? '
            'ORDER BY ts_ms', (start_ms, end_ms))

    def latest_thermostat_ms(self):
        """Time of the newest thermostat row, or None."""
        return self._query('SELECT MAX(ts_ms) FROM thermostat_events')[0][0]

    def created_ms(self):
        value = self.get_meta('created_ms')
        return int(value) if value is not None else None

    def get_meta(self, key):
        rows = self._query('SELECT value FROM meta WHERE key = ?', (key,))
        return rows[0][0] if rows else None

    def set_meta(self, key, value):
        with self._write_lock, closing(self._connect()) as conn:
            with conn:
                conn.execute('INSERT INTO meta (key, value) VALUES (?, ?) '
                             'ON CONFLICT (key) DO UPDATE SET value = excluded.value', (key, value))

    def ping(self):
        try:
            return self._query('SELECT 1')[0][0] == 1
        except sqlite3.Error:
            return False

    # -- maintenance --------------------------------------------------------

    def prune(self, before_ms, chunk_ms=7 * 86_400_000):
        """Delete readings older than before_ms in short per-field, per-chunk
        transactions, then truncate the WAL. Returns rows deleted."""
        deleted = 0
        for fid in FIELD_IDS.values():
            deleted += self._prune_table('readings', 'field_id', fid, before_ms, chunk_ms)
        for field in TEXT_FIELDS:
            deleted += self._prune_table('text_readings', 'field', field, before_ms, chunk_ms)
        with self._write_lock, closing(self._connect()) as conn:
            with conn:
                deleted += conn.execute('DELETE FROM thermostat_events WHERE ts_ms < ?',
                                        (before_ms,)).rowcount
        if deleted:
            with self._write_lock, closing(self._connect()) as conn:
                conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        return deleted

    def _prune_table(self, table, key_col, key, before_ms, chunk_ms):
        oldest = self._query(f'SELECT MIN(ts_ms) FROM {table} WHERE {key_col} = ?', (key,))[0][0]
        deleted = 0
        lo = oldest
        while lo is not None and lo < before_ms:
            hi = min(lo + chunk_ms, before_ms)
            with self._write_lock, closing(self._connect()) as conn:
                with conn:
                    deleted += conn.execute(
                        f'DELETE FROM {table} WHERE {key_col} = ? AND ts_ms >= ? AND ts_ms < ?',
                        (key, lo, hi)).rowcount
            lo = hi
        return deleted
