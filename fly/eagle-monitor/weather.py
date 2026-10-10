"""Outdoor temperature for the heating charts, from Open-Meteo's forecast API.

Hourly air temperature at 2 m for a point near the house, as modelled (so there are no
station outages to fill). Free and keyless for non-commercial use; the data is CC BY 4.0
and the page credits it. The ingest service fetches it and keeps it in the store as
`outdoor_temp_c`, because the page's CSP lets it talk to this service only.
"""

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

API = 'https://api.open-meteo.com/v1/forecast'
SOURCE = 'Open-Meteo'
MAX_PAST_DAYS = 92
TIMEOUT = (10, 60)  # seconds to connect, then to wait for the reply


class WeatherError(Exception):
    """A request that was refused, did not complete, or came back in another shape."""


def fetch(latitude, longitude, past_days, now=None):
    """(hourly, current): hourly is [(ts_ms, degrees C)] for the last `past_days` days up
    to now, current is the newest (ts_ms, degrees C) or None. Forecast hours are dropped."""
    now = now or datetime.now(timezone.utc)
    params = {
        'latitude': latitude, 'longitude': longitude,
        'hourly': 'temperature_2m', 'current': 'temperature_2m',
        'past_days': min(past_days, MAX_PAST_DAYS), 'forecast_days': 1,
        'timeformat': 'unixtime', 'timezone': 'GMT',
    }
    try:
        response = requests.get(API, params=params, timeout=TIMEOUT)
        body = response.json()
    except Exception as e:
        raise WeatherError(type(e).__name__) from None
    if response.status_code != 200:
        raise WeatherError(f'HTTP {response.status_code}, {str(body.get("reason", ""))[:120]}')
    try:
        limit = now.timestamp()
        hourly = [(int(t) * 1000, float(value))
                  for t, value in zip(body['hourly']['time'], body['hourly']['temperature_2m'])
                  if value is not None and t <= limit]
        now_block = body.get('current') or {}
        current = None
        if now_block.get('temperature_2m') is not None:
            current = (int(now_block['time']) * 1000, float(now_block['temperature_2m']))
    except (KeyError, TypeError, ValueError) as e:
        raise WeatherError(f'unexpected reply: {type(e).__name__}') from None
    return hourly, current
