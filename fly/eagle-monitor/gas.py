"""FortisBC gas bill estimate.

The house has no gas telemetry: FortisBC reads the meter once a month. Gas used is
modelled instead, as

    GJ = base load x days  +  furnace rate x hours the thermostat called for heat

The base load is everything that is not the furnace: the water heater (a 40 US gallon
tank rated 38,000 BTU/h) and the range. It is taken from the four summer bills of 2026,
when the furnace did not run: 5.5 GJ over 119 days (Jun 3 to Sep 29). Expect it to run
somewhat higher in winter, when the water comes in colder; the model does not allow for
that, so a furnace rate fitted to winter bills will absorb the difference. The furnace
rate is FURNACE_INPUT_BTUH, the gas burned per hour of call for heat; until it is set a
typical 60,000 BTU/h is assumed and the API says so. Each bill is a check on both
numbers: the meter resolves about 0.13 GJ.

The rest of a period is forecast from the weather a normal year brings (forecast()):
the furnace's run time follows the degree-days below a balance point, and the normals
are the 2011 to 2025 temperatures (scripts/gas_normals.py).

The bill is built line by line the way FortisBC's residential bill (rate schedule 1,
Lower Mainland) is, and reproduces the Jul 31, Aug 31, Sep 29 and Oct 30, 2026 bills
exactly; see test_heating.TestGasBill. The per-GJ rates change during the year (storage
and transport rose on Jul 1, 2026), so check them against each new bill.
"""

import calendar
import math
import os
from datetime import date, datetime, time, timedelta

BTU_PER_GJ = 947_817.0

BASIC_CHARGE_DAILY = float(os.getenv('GAS_BASIC_CHARGE_DAILY', '0.4216'))          # $/day
DELIVERY_PER_GJ = float(os.getenv('GAS_DELIVERY_PER_GJ', '8.469'))
STORAGE_TRANSPORT_PER_GJ = float(os.getenv('GAS_STORAGE_TRANSPORT_PER_GJ', '2.472'))
COMMODITY_PER_GJ = float(os.getenv('GAS_COMMODITY_PER_GJ', '1.660'))               # "Cost of gas"
MUNICIPAL_FEE_PCT = float(os.getenv('GAS_MUNICIPAL_FEE_PCT', '0.70'))              # of basic + delivery
CLEAN_ENERGY_LEVY_PCT = float(os.getenv('GAS_CLEAN_ENERGY_LEVY_PCT', '0.40'))      # of all the above
GST_PCT = float(os.getenv('GAS_GST_PCT', '5'))                                     # of all but the levy
# The renewable natural gas in the supply is left out of the cost of gas line ("Including
# 0.1 GJ RNG" under storage and transport), rounded to 0.1 GJ like the bill: a 3% share
# fits every 2026 bill (0.1 GJ of 1.7 and of 4.2, none of 1.3 or 1.4).
RNG_SHARE = float(os.getenv('GAS_RNG_SHARE', '0.03'))

BASE_GJ_PER_DAY = float(os.getenv('GAS_BASE_GJ_PER_DAY', '0.046'))
FURNACE_INPUT_BTUH = float(os.getenv('FURNACE_INPUT_BTUH', '0')) or None
FURNACE_INPUT_BTUH_ASSUMED = 60_000.0

# Meter read dates printed on the bills (YYYY-MM-DD, comma separated). A period starts
# the day after a read. FortisBC reads near the end of each month, so without a read
# date a period is taken to start on the 1st.
READ_DATES = os.getenv('GAS_READ_DATES', '2026-09-29,2026-10-30')
READ_WINDOW_DAYS = 10  # how far a read may sit from the 1st it replaces

# Forecast. The furnace's hours of heating in a day are HEATING_HOURS_PER_DEGREE_DAY x the
# day's degree-days: how far its mean outdoor temperature falls short of BALANCE_POINT_C.
# Fitted on 2026-11-02 to the thermostat log of Oct 11 to Nov 1 (20 whole days, 4.8 to
# 12.7 C), with the balance point chosen so that the 2026 bills fit too: April to
# October, each within 0.25 GJ. The service refits the slope to the recent log
# (fit_heating) once it holds enough cold days; these are the fallback.
BALANCE_POINT_C = 12.5
HEATING_HOURS_PER_DEGREE_DAY = 0.794
HEATING_HOURS_SE = 0.056    # its standard error
HEATING_HOURS_SD = 1.03     # the scatter of a day's hours around the fit
FURNACE_RATE_SD = 0.06      # relative: the meter that measured it reads whole counts
INTERVAL_Z = 1.2816         # the forecast's range holds 8 bills in 10

# Degree-days below 12.5 C, 2011 to 2025: (mean per day, sd of the month total).
# From scripts/gas_normals.py, for the point the outdoor temperature is fetched for.
NORMALS = {
    1: (9.17, 33.5),
    2: (9.22, 48.5),
    3: (6.67, 28.1),
    4: (4.13, 34.0),
    5: (1.05, 24.3),
    6: (0.11, 4.9),
    7: (0.00, 0.4),
    8: (0.00, 0.0),
    9: (0.14, 4.2),
    10: (2.58, 26.4),
    11: (6.66, 38.2),
    12: (9.36, 57.6),
}


def _cents(amount):
    """Rounded to the cent, a half going up as on the bill (29.31 x 5% is $1.47)."""
    return round(amount + 1e-9, 2)


def bill(gj, days):
    """Bill for `gj` over `days` days: each line rounded to the cent. total_cost is the
    amount due including GST."""
    basic = _cents(days * BASIC_CHARGE_DAILY)
    delivery = _cents(gj * DELIVERY_PER_GJ)
    storage_transport = _cents(gj * STORAGE_TRANSPORT_PER_GJ)
    commodity = _cents((gj - round(gj * RNG_SHARE, 1)) * COMMODITY_PER_GJ)
    municipal_fee = _cents((basic + delivery) * MUNICIPAL_FEE_PCT / 100)
    subtotal = _cents(basic + delivery + storage_transport + commodity + municipal_fee)
    levy = _cents(subtotal * CLEAN_ENERGY_LEVY_PCT / 100)
    gst = _cents(subtotal * GST_PCT / 100)
    return {
        'gj': round(gj, 3),
        'basic_charge': basic,
        'delivery': delivery,
        'storage_transport': storage_transport,
        'commodity': commodity,
        'municipal_fee': municipal_fee,
        'clean_energy_levy': levy,
        'gst': gst,
        'total_cost': _cents(subtotal + levy + gst),
    }


def furnace_gj_per_hour():
    """(GJ burned per hour of heating, whether the rating is the assumed one)."""
    rating = FURNACE_INPUT_BTUH or FURNACE_INPUT_BTUH_ASSUMED
    return rating / BTU_PER_GJ, FURNACE_INPUT_BTUH is None


def usage(days, heating_hours):
    """Modelled GJ over `days` days with `heating_hours` of furnace run time."""
    return BASE_GJ_PER_DAY * days + furnace_gj_per_hour()[0] * heating_hours


def _first_of_month(dt, months):
    total = dt.year * 12 + dt.month - 1 + months
    return dt.replace(year=total // 12, month=total % 12 + 1, day=1,
                      hour=0, minute=0, second=0, microsecond=0)


def period(now):
    """(start, next_start) of the billing period containing `now` (an aware local time),
    as local midnights. Each known read date moves the 1st nearest to it to the day
    after the read."""
    bounds = [_first_of_month(now, k) for k in range(-2, 4)]
    for text in filter(None, (part.strip() for part in READ_DATES.split(','))):
        boundary = datetime.strptime(text, '%Y-%m-%d').replace(tzinfo=now.tzinfo) + timedelta(days=1)
        nearest = min(range(len(bounds)), key=lambda i: abs(bounds[i] - boundary))
        if abs(bounds[nearest] - boundary) <= timedelta(days=READ_WINDOW_DAYS):
            bounds[nearest] = boundary
    bounds.sort()
    for start, next_start in zip(bounds, bounds[1:]):
        if start <= now < next_start:
            return start, next_start
    return bounds[2], bounds[3]


def degree_days(mean_c):
    """A day's degree-days from its mean outdoor temperature."""
    return max(0.0, BALANCE_POINT_C - mean_c)


def fit_heating(days, min_days=7, min_degree_days=20.0):
    """(hours of heating per degree-day, its standard error, the scatter of a day's hours,
    days fitted) for whole logged days given as [(degree-days, heating hours)]: the least-
    squares line through the origin. While they hold too few cold days the fallback
    constants are returned, with 0 days fitted."""
    cold = [x for x, _ in days if x > 0]
    if len(cold) < min_days or sum(cold) < min_degree_days or len(days) < 2:
        return HEATING_HOURS_PER_DEGREE_DAY, HEATING_HOURS_SE, HEATING_HOURS_SD, 0
    sxx = sum(x * x for x, _ in days)
    slope = sum(x * y for x, y in days) / sxx
    scatter = math.sqrt(sum((y - slope * x) ** 2 for x, y in days) / (len(days) - 1))
    return slope, scatter / math.sqrt(sxx), scatter, len(days)


def _mid_month(year, month):
    year, month = year + (month - 1) // 12, (month - 1) % 12 + 1
    return date(year, month, 15)


def normal_degree_days(day):
    """A date's normal degree-days: each month's mean taken at the 15th, and a straight
    line between those."""
    mid = _mid_month(day.year, day.month)
    if day >= mid:
        a, b = mid, _mid_month(day.year, day.month + 1)
    else:
        a, b = _mid_month(day.year, day.month - 1), mid
    share = (day - a).days / (b - a).days
    return NORMALS[a.month][0] + (NORMALS[b.month][0] - NORMALS[a.month][0]) * share


def normal_window(start, end):
    """(normal degree-days, their year-to-year standard deviation) from `start` to `end`,
    aware local times; a part day counts in part. Each month adds its own deviation in
    proportion to the share of the month inside the window, months taken as independent."""
    total, shares, cur = 0.0, {}, start
    while cur < end:
        midnight = datetime.combine(cur.date() + timedelta(days=1), time(), tzinfo=cur.tzinfo)
        stop = min(midnight, end)
        part = (stop - cur) / (midnight - datetime.combine(cur.date(), time(), tzinfo=cur.tzinfo))
        total += part * normal_degree_days(cur.date())
        key = (cur.year, cur.month)
        shares[key] = shares.get(key, 0.0) + part
        cur = stop
    variance = sum((part / calendar.monthrange(year, month)[1] * NORMALS[month][1]) ** 2
                   for (year, month), part in shares.items())
    return total, math.sqrt(variance)


def forecast(gj_so_far, now, end, heating):
    """(GJ over the whole period, its standard deviation): the GJ so far, plus for the
    time from `now` to `end` the base load and the furnace's run time in a normal year's
    weather. `heating` is what fit_heating() returns. The deviation combines how much the
    weather of those days varies from year to year, the daily scatter of the run time,
    and the uncertainty of the furnace rate and of the hours per degree-day."""
    slope, slope_se, scatter, _ = heating
    rate = furnace_gj_per_hour()[0]
    days_left = max(0.0, (end - now) / timedelta(days=1))
    expected, spread = normal_window(now, end)
    hours = slope * expected
    relative = FURNACE_RATE_SD ** 2 + ((slope_se / slope) ** 2 if slope else 0.0)
    variance = ((rate * slope * spread) ** 2 + (rate * scatter) ** 2 * days_left
                + (rate * hours) ** 2 * relative)
    return gj_so_far + BASE_GJ_PER_DAY * days_left + rate * hours, math.sqrt(variance)
