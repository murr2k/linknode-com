"""Heating and cooling run time, from the thermostat's event log.

The Pi logs the Honeywell T5 thermostat over HomeKit (the t5-runtime logger, kept in the
1344-network repo) as one row per change, and scripts/t5_upload.py posts the rows to
/thermostat. A row is (ts_ms, event, active, mode, temp, target):

    event   start      the logger began observing; the row carries the first state read
            change     a value changed
            heartbeat  hourly, nothing changed
            lost       the thermostat stopped answering; state unknown from this time
            resume     the thermostat is answering again
            stop       the logger shut down cleanly
    active  0 idle, 1 heating, 2 cooling: the thermostat's call, not proof the burner lit
    mode    0 off, 1 heat, 2 cool, 3 auto
    temp    room temperature, degrees C
    target  setpoint, degrees C

A row's state holds until the next row. Time the logger was not watching is unobserved
and is never counted as idle or running: after a `lost` or `stop` row, before a `start`
row, and past the last time the logger read the thermostat.
"""

from datetime import datetime, time, timedelta, timezone

EVENTS = ('start', 'change', 'heartbeat', 'lost', 'resume', 'stop')
LABELS = {0: 'idle', 1: 'heating', 2: 'cooling'}
MODES = {0: 'off', 1: 'heat', 2: 'cool', 3: 'auto'}
UNOBSERVED = 'unobserved'
MAX_BATCH = 5000

TS, EVENT, ACTIVE, MODE, TEMP, TARGET = range(6)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _to_ms(dt):
    return (dt - EPOCH) // timedelta(milliseconds=1)


def _number(value, cast, low, high):
    """`value` as cast(value) when it lies in [low, high], None when absent."""
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise ValueError(f'not a number: {value!r}')
    number = cast(value)
    if not low <= number <= high:
        raise ValueError(f'out of range: {value!r}')
    return number


def parse_events(items, now_ms):
    """Uploaded rows as store tuples. ValueError names the first row that is not one.

    Each item is {epoch, event, active, mode, temp, target}; epoch is in seconds and
    the rest may be absent (a `lost` row carries no state)."""
    if not isinstance(items, list) or len(items) > MAX_BATCH:
        raise ValueError(f'events must be a list of at most {MAX_BATCH} rows')
    rows = []
    for index, item in enumerate(items):
        try:
            if not isinstance(item, dict) or item.get('event') not in EVENTS:
                raise ValueError('unknown event')
            ts_ms = round(float(item['epoch']) * 1000)
            if not 0 < ts_ms <= now_ms + 3_600_000:
                raise ValueError('time out of range')
            rows.append((ts_ms, item['event'],
                         _number(item.get('active'), int, 0, 2),
                         _number(item.get('mode'), int, 0, 3),
                         _number(item.get('temp'), float, -50, 80),
                         _number(item.get('target'), float, -50, 80)))
        except (KeyError, TypeError, ValueError, OverflowError) as e:
            raise ValueError(f'row {index}: {e}') from None
    return rows


def label_of(row):
    if row[EVENT] in ('lost', 'stop') or row[ACTIVE] is None:
        return UNOBSERVED
    return LABELS.get(row[ACTIVE], UNOBSERVED)


def spans(rows, end_ms):
    """(start_ms, end_ms, label, room temp) for each row, oldest first: the row's state
    from its own time to the next row's, and the last row's to `end_ms`, the last time
    the logger is known to have read the thermostat."""
    for a, b in zip(rows, rows[1:]):
        if b[TS] > a[TS]:
            yield a[TS], b[TS], UNOBSERVED if b[EVENT] == 'start' else label_of(a), a[TEMP]
    if rows and end_ms and end_ms > rows[-1][TS]:
        yield rows[-1][TS], end_ms, label_of(rows[-1]), rows[-1][TEMP]


def _split_by_day(start_ms, end_ms, tz):
    """(date, milliseconds) pieces of [start_ms, end_ms) cut at local midnight."""
    cur = start_ms
    while cur < end_ms:
        day = datetime.fromtimestamp(cur / 1000, tz).date()
        midnight = _to_ms(datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz))
        nxt = min(end_ms, midnight)
        yield day, nxt - cur
        cur = nxt


def daily(rows, end_ms, tz):
    """{date: totals} per local day: seconds heating, cooling and idle, the number of
    heating and cooling cycles that began that day, and the room temperature averaged
    over the time observed (None when none was). A day with no observed time is absent."""
    days = {}
    previous = None
    for start, end, label, temp in spans(rows, end_ms):
        if label == UNOBSERVED:
            previous = None
            continue
        for i, (day, ms) in enumerate(_split_by_day(start, end, tz)):
            d = days.setdefault(day, {'heating_s': 0.0, 'cooling_s': 0.0, 'idle_s': 0.0,
                                      'heat_cycles': 0, 'cool_cycles': 0,
                                      'temp_ms': 0.0, 'temp_weight': 0.0})
            d[label + '_s'] += ms / 1000.0
            if temp is not None:
                d['temp_ms'] += temp * ms
                d['temp_weight'] += ms
            # A run is one cycle however many rows it spans, counted on the day it began
            if i == 0 and label != previous and label != 'idle':
                d['heat_cycles' if label == 'heating' else 'cool_cycles'] += 1
        previous = label
    for d in days.values():
        weight = d.pop('temp_weight')
        d['room_c'] = d.pop('temp_ms') / weight if weight else None
    return days


def current(rows, observed_ms, now_ms, fresh_ms):
    """What the thermostat is doing now: {state, since_ms, mode, room_c, target_c}.

    The state is `unobserved` once the logger's last read (`observed_ms`) is older than
    `fresh_ms`; the temperatures are then the last ones seen. `since_ms` is when the
    state began, as far back as `rows` reach."""
    if not rows:
        return {'state': UNOBSERVED, 'since_ms': None, 'mode': None, 'room_c': None, 'target_c': None}
    last = rows[-1]
    state, since = label_of(last), last[TS]
    if state == UNOBSERVED or now_ms - max(observed_ms or 0, last[TS]) > fresh_ms:
        state = UNOBSERVED
        since = max(observed_ms or 0, last[TS]) if label_of(last) != UNOBSERVED else last[TS]
    else:
        for start, _, label, _ in reversed(list(spans(rows, None))):
            if label != state:
                break
            since = start
    # The newest row that carries each value (a `lost` row carries none)
    held = {}
    for index in (MODE, TEMP, TARGET):
        held[index] = next((row[index] for row in reversed(rows) if row[index] is not None), None)
    return {'state': state, 'since_ms': since, 'mode': MODES.get(held[MODE]),
            'room_c': held[TEMP], 'target_c': held[TARGET]}
