#!/usr/bin/env python3
"""Print the heating degree-day normals that gas.py's forecast uses (NORMALS).

For each month: the mean degree-days per day below gas.BALANCE_POINT_C, and the standard
deviation of the month's total from year to year. Daily mean temperatures come from the
Open-Meteo historical weather API (ERA5, keyless, CC BY 4.0) for the same point the
ingest service fetches its outdoor temperature for. Run it again if the balance point or
the years change, and paste the result into gas.py.

    python scripts/gas_normals.py [--first 2011] [--last 2025]
"""

import argparse
import calendar
import statistics
import sys
from datetime import date

import requests

API = 'https://archive-api.open-meteo.com/v1/archive'
LATITUDE, LONGITUDE = 49.03, -122.80   # as WEATHER_LATITUDE / WEATHER_LONGITUDE in app.py
BALANCE_POINT_C = 12.5                 # as gas.BALANCE_POINT_C


def daily_means(first, last):
    r = requests.get(API, params={
        'latitude': LATITUDE, 'longitude': LONGITUDE,
        'start_date': f'{first}-01-01', 'end_date': f'{last}-12-31',
        'daily': 'temperature_2m_mean', 'timezone': 'America/Vancouver',
    }, timeout=(10, 120))
    r.raise_for_status()
    daily = r.json()['daily']
    return {date.fromisoformat(d): t for d, t in zip(daily['time'], daily['temperature_2m_mean'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--first', type=int, default=2011)
    parser.add_argument('--last', type=int, default=2025)
    args = parser.parse_args()
    temps = daily_means(args.first, args.last)
    missing = [d for d, t in temps.items() if t is None]
    if missing:
        sys.exit(f'{len(missing)} days have no temperature, the first {missing[0]}')

    print(f'# Degree-days below {BALANCE_POINT_C} C, {args.first} to {args.last}:'
          ' (mean per day, sd of the month total)')
    print('NORMALS = {')
    for month in range(1, 13):
        per_day, totals = [], []
        for year in range(args.first, args.last + 1):
            days = calendar.monthrange(year, month)[1]
            total = sum(max(0.0, BALANCE_POINT_C - temps[date(year, month, day)]) for day in range(1, days + 1))
            per_day.append(total / days)
            totals.append(total)
        print(f'    {month}: ({statistics.mean(per_day):.2f}, {statistics.stdev(totals):.1f}),')
    print('}')


if __name__ == '__main__':
    main()
