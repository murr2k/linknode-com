#!/usr/bin/env python3
"""
Payload for GET /api/dashboard: the ten panels of the retired Grafana dashboard
(uid power-monitoring, live version 44), computed from the SQLite store.

Panel math mirrors the Flux queries it replaces:
  current power   last power_w within 5 minutes
  min/max/mean    power_w over the selected range
  energy_wh       integral(power_w, unit: 1h), gaps bridged
  meter_kwh       last energy_delivered_kwh within 5 minutes
  price_per_kwh   last price_per_kwh within 24 hours (newest by time)
  cost_per_hour   current power / 1000 * price
  estimated_cost  energy_wh / 1000 * price * 1.1
"""

# range key -> (span in seconds, bucket in seconds; None = raw points)
RANGES = {
    '1h': (3600, None),
    '6h': (6 * 3600, 60),
    '24h': (24 * 3600, 120),
    '7d': (7 * 86400, 900),
    '30d': (30 * 86400, 3600),
}
DEFAULT_RANGE = '24h'

LIVE_WINDOW_MS = 5 * 60_000
PRICE_WINDOW_MS = 24 * 3_600_000
ESTIMATE_RATE_FACTOR = 1.1  # the Grafana panel's blended-rate markup

# Raw points arrive every ~35s from the Pi; a gap longer than this is an outage.
RAW_GAP_MS = 180_000
# Bucketed series break after this many missing buckets.
GAP_BUCKETS = 3


def break_gaps(points, max_gap_ms):
    """Insert a [t, None] marker inside any gap longer than max_gap_ms so the chart
    shows outages instead of drawing a straight line across them. Chart-only: the
    energy integral deliberately bridges gaps, as Grafana's did."""
    out = []
    prev_t = None
    for t, v in points:
        if prev_t is not None and t - prev_t > max_gap_ms:
            out.append([prev_t + 1, None])
        out.append([t, round(v, 1)])
        prev_t = t
    return out


def build(store, range_key, now_ms):
    span_s, bucket_s = RANGES[range_key]
    end = now_ms
    start = end - span_s * 1000
    bucket_ms = bucket_s * 1000 if bucket_s else None

    power = store.agg('power_w', start, end)
    current = store.latest('power_w', end - LIVE_WINDOW_MS, end)
    meter = store.latest('energy_delivered_kwh', end - LIVE_WINDOW_MS, end)
    price = store.latest('price_per_kwh', end - PRICE_WINDOW_MS, end)
    energy_wh = store.integral_wh(start, end)

    current_w = current[1] if current else None
    rate = price[1] if price else None
    cost_per_hour = (current_w / 1000.0 * rate
                     if current_w is not None and rate is not None else None)
    estimated_cost = (energy_wh / 1000.0 * rate * ESTIMATE_RATE_FACTOR
                      if energy_wh is not None and rate is not None else None)

    series = store.series('power_w', start, end, bucket_ms)
    max_gap = bucket_ms * GAP_BUCKETS if bucket_ms else RAW_GAP_MS

    return {
        'range': range_key,
        'start': start,
        'end': end,
        'bucket_s': bucket_s,
        'series': break_gaps(series, max_gap),
        'power': {
            'current': current_w,
            'current_ts': current[0] if current else None,
            'min': power['min'],
            'max': power['max'],
            'mean': power['mean'],
            'count': power['count'],
        },
        'energy_wh': energy_wh,
        'meter_kwh': meter[1] if meter else None,
        'meter_ts': meter[0] if meter else None,
        'price_per_kwh': rate,
        'cost_per_hour': cost_per_hour,
        'estimated_cost': estimated_cost,
    }
