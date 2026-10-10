"""FortisBC gas bill estimate.

The house has no gas telemetry: FortisBC reads the meter once a month. Gas used is
modelled instead, as

    GJ = base load x days  +  furnace input rate x hours the thermostat called for heat

The base load is everything that is not the furnace (the range, pilot lights), taken
from the four summer bills of 2026 when the furnace did not run: 5.5 GJ over 119 days
(Jun 3 to Sep 29). The furnace input rate is its nameplate rating (FURNACE_INPUT_BTUH);
until that is set a typical 60,000 BTU/h is assumed and the API says so. Each bill is a
check on both numbers: the meter resolves about 0.13 GJ.

The bill is built line by line the way FortisBC's residential bill (rate schedule 1,
Lower Mainland) is, and reproduces the Jul 31, Aug 31 and Sep 29, 2026 bills exactly;
see test_heating.TestGasBill. The per-GJ rates change during the year (storage and
transport rose on Jul 1, 2026), so check them against each new bill.
"""

import os
from datetime import datetime, timedelta

BTU_PER_GJ = 947_817.0

BASIC_CHARGE_DAILY = float(os.getenv('GAS_BASIC_CHARGE_DAILY', '0.4216'))          # $/day
DELIVERY_PER_GJ = float(os.getenv('GAS_DELIVERY_PER_GJ', '8.469'))
STORAGE_TRANSPORT_PER_GJ = float(os.getenv('GAS_STORAGE_TRANSPORT_PER_GJ', '2.472'))
COMMODITY_PER_GJ = float(os.getenv('GAS_COMMODITY_PER_GJ', '1.660'))               # "Cost of gas"
MUNICIPAL_FEE_PCT = float(os.getenv('GAS_MUNICIPAL_FEE_PCT', '0.70'))              # of basic + delivery
CLEAN_ENERGY_LEVY_PCT = float(os.getenv('GAS_CLEAN_ENERGY_LEVY_PCT', '0.40'))      # of all the above
GST_PCT = float(os.getenv('GAS_GST_PCT', '5'))                                     # of all but the levy

BASE_GJ_PER_DAY = float(os.getenv('GAS_BASE_GJ_PER_DAY', '0.046'))
FURNACE_INPUT_BTUH = float(os.getenv('FURNACE_INPUT_BTUH', '0')) or None
FURNACE_INPUT_BTUH_ASSUMED = 60_000.0

# Meter read dates printed on the bills (YYYY-MM-DD, comma separated). A period starts
# the day after a read. FortisBC reads near the end of each month, so without a read
# date a period is taken to start on the 1st.
READ_DATES = os.getenv('GAS_READ_DATES', '2026-09-29')
READ_WINDOW_DAYS = 10  # how far a read may sit from the 1st it replaces


def _cents(amount):
    """Rounded to the cent, a half going up as on the bill (29.31 x 5% is $1.47)."""
    return round(amount + 1e-9, 2)


def bill(gj, days):
    """Bill for `gj` over `days` days: each line rounded to the cent. total_cost is the
    amount due including GST."""
    basic = _cents(days * BASIC_CHARGE_DAILY)
    delivery = _cents(gj * DELIVERY_PER_GJ)
    storage_transport = _cents(gj * STORAGE_TRANSPORT_PER_GJ)
    commodity = _cents(gj * COMMODITY_PER_GJ)
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
