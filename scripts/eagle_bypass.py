#!/usr/bin/env python3
"""Local-API bypass: ship the Eagle's meter data straight to our Fly endpoint,
formatted as if Rainforest's cloud had forwarded it.

WHY THIS EXISTS
    Normal path:  Eagle --> Rainforest cloud --> POST /eagle --> InfluxDB --> Grafana
    When Rainforest's cloud upload wedges (the device's data-CGI backend dies while
    the rest of the box stays healthy), nothing reaches us even though the meter is
    fine and readable on the Eagle's *local* API. This script reads the local API
    directly and POSTs the same three telemetry messages the cloud would have sent,
    so the dashboard keeps flowing. Fly can't reach the Eagle (it's on the LAN), so
    this runs here on the LAN, not on Fly. Nothing on Fly changes.

FAILOVER, NOT REPLACEMENT (default)
    We don't want duplicate InfluxDB points when Rainforest is working. So by default
    the script is a hot standby: it watches /api/stats and only ships when the cloud
    path has gone stale (no data for --stale-secs). Because our own successful uploads
    reset that same staleness clock, we can't tell "Rainforest recovered" from "our
    last ship landed" by the clock alone -- so every --probe-secs we pause uploads for
    one cycle and watch: if the clock stays fresh while we're silent, Rainforest is
    back and we return to standby; if it goes stale again, we resume shipping.

    --force        ship every cycle regardless (always-on / replace mode)
    --once         run a single cycle and exit (for cron/systemd timer)
    --dry-run      build and print the XML; do not POST

CREDENTIALS (from the environment; never logged)
    Local API (read from the Eagle):
        EAGLE_IP            default 192.168.68.63
        EAGLE_CLOUD_ID      Cloud ID  (Basic-auth user for the local API)
        EAGLE_INSTALL_CODE  Install Code (Basic-auth pass for the local API)
    Upload (write to our Fly /eagle, same Basic auth the Rainforest uploader uses):
        EAGLE_UPLOAD_URL       default https://linknode-eagle-monitor.fly.dev/eagle
        EAGLE_UPLOAD_USER      default 'eagle'  (matches EAGLE_USERNAME on Fly)
        EAGLE_UPLOAD_PASSWORD  the EAGLE_PASSWORD secret set on the Fly app

Usage:  python eagle_bypass.py [--interval 30] [--stale-secs 90] [--probe-secs 300]
                               [--force] [--once] [--dry-run] [-v]
"""

import argparse
import base64
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# ---- local API (read side) -------------------------------------------------
EAGLE_IP = os.environ.get("EAGLE_IP", "192.168.68.63")
CLOUD_ID = os.environ.get("EAGLE_CLOUD_ID", "")
INSTALL_CODE = os.environ.get("EAGLE_INSTALL_CODE", "")
LOCAL_API = f"http://{EAGLE_IP}/cgi-bin/post_manager"

# ---- upload API (write side) -----------------------------------------------
UPLOAD_URL = os.environ.get("EAGLE_UPLOAD_URL", "https://linknode-eagle-monitor.fly.dev/eagle")
UPLOAD_USER = os.environ.get("EAGLE_UPLOAD_USER", "eagle")
UPLOAD_PASS = os.environ.get("EAGLE_UPLOAD_PASSWORD", "")
FLY_STATS = "https://linknode-eagle-monitor.fly.dev/api/stats"

# ---- Zigbee / device constants ---------------------------------------------
# The Eagle carries two Zigbee radios. Data must be tagged with the Control radio
# (...ef69); the collector filters ...ef68 outright (it only ever sent empty msgs).
DEVICE_MAC = os.environ.get("EAGLE_DEVICE_MAC", "0xd8d5b9000000ef69")
# Fallback meter MAC if the local device_list doesn't yield one.
METER_MAC_FALLBACK = os.environ.get("EAGLE_METER_MAC", "0x0007810000a4505c")
ZIGBEE_EPOCH_OFFSET = 946684800  # 2000-01-01 UTC; collector adds this back

DEVICE_LIST = "<Command><Name>device_list</Name></Command>"
DEVICE_QUERY = (
    "<Command><Name>device_query</Name>"
    "<DeviceDetails><HardwareAddress>{mac}</HardwareAddress></DeviceDetails>"
    "<Components><All>Y</All></Components></Command>"
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def log(msg):
    print(f"{now_iso()}  {msg}", file=sys.stderr, flush=True)


# ---- Eagle local API (lifted from eagle_probe.py; proven working) ----------
def local_api(body, timeout=20):
    if not CLOUD_ID or not INSTALL_CODE:
        return None, "no credentials (set EAGLE_CLOUD_ID / EAGLE_INSTALL_CODE)"
    token = base64.b64encode(f"{CLOUD_ID}:{INSTALL_CODE}".encode()).decode()
    req = urllib.request.Request(
        LOCAL_API,
        data=body.encode(),
        headers={"Authorization": f"Basic {token}", "Content-Type": "text/xml"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace"), None
    except urllib.error.HTTPError as e:
        return None, f"http {e.code}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def find_meter_mac(xml):
    macs = re.findall(r"<HardwareAddress>(0x[0-9a-fA-F]+)</HardwareAddress>", xml or "")
    return macs[-1] if macs else None


def scrape(xml, name):
    m = re.search(rf"<Name>zigbee:{name}</Name>\s*<Value>([^<]*)</Value>", xml or "", re.I)
    return m.group(1).strip() if m else None


def fly_age_seconds(timeout=15):
    """Seconds since the Fly endpoint last stored data, or None if unknown/unreachable."""
    import json
    try:
        with urllib.request.urlopen(FLY_STATS, timeout=timeout) as r:
            stats = json.loads(r.read().decode())
    except Exception as e:
        log(f"fly stats unreachable: {type(e).__name__}: {e}")
        return None
    last = stats.get("monitor_stats", {}).get("last_data_received")
    if not last:
        return None
    try:
        dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds()


# ---- read current meter state ----------------------------------------------
def read_meter():
    """Return (readings, meter_mac, error). readings has float kW / kWh / price when
    the local API yields them; any field may be absent."""
    xml, err = local_api(DEVICE_LIST)
    if err:
        return {}, None, f"device_list: {err}"
    meter_mac = find_meter_mac(xml) or METER_MAC_FALLBACK

    xml, err = local_api(DEVICE_QUERY.format(mac=meter_mac))
    if err:
        return {}, meter_mac, f"device_query: {err}"

    readings = {}
    demand = scrape(xml, "InstantaneousDemand")          # kW
    summ = scrape(xml, "CurrentSummationDelivered")       # kWh
    price = scrape(xml, "Price") or scrape(xml, "price:PricePerKWh")  # $/kWh (may be absent)
    try:
        if demand is not None:
            readings["demand_kw"] = float(demand)
    except ValueError:
        pass
    try:
        if summ is not None:
            readings["summation_kwh"] = float(summ)
    except ValueError:
        pass
    try:
        if price is not None:
            readings["price"] = float(price)
    except ValueError:
        pass
    return readings, meter_mac, None


# ---- build the synthetic Rainforest messages -------------------------------
# We reconstruct the raw Zigbee wire form (hex value + multiplier/divisor) so the
# collector's existing decimal math reproduces exactly these readings. One message
# per document: the collector parses the first matching type and ignores the rest.
def _hexts():
    return f"0x{int(time.time()) - ZIGBEE_EPOCH_OFFSET:x}"


def msg_demand(kw, meter_mac):
    raw = max(0, round(kw * 1000))  # watts; mult=1 div=1000 -> collector power_w = raw
    return (
        "<rainforest><InstantaneousDemand>"
        f"<DeviceMacId>{DEVICE_MAC}</DeviceMacId>"
        f"<MeterMacId>{meter_mac}</MeterMacId>"
        f"<TimeStamp>{_hexts()}</TimeStamp>"
        f"<Demand>0x{raw:08x}</Demand>"
        "<Multiplier>0x00000001</Multiplier>"
        "<Divisor>0x000003e8</Divisor>"
        "</InstantaneousDemand></rainforest>"
    )


def msg_summation(kwh, meter_mac):
    raw = max(0, round(kwh * 1000))  # Wh; mult=1 div=1000 -> collector kWh = raw/1000
    return (
        "<rainforest><CurrentSummationDelivered>"
        f"<DeviceMacId>{DEVICE_MAC}</DeviceMacId>"
        f"<MeterMacId>{meter_mac}</MeterMacId>"
        f"<TimeStamp>{_hexts()}</TimeStamp>"
        f"<SummationDelivered>0x{raw:012x}</SummationDelivered>"
        "<Multiplier>0x00000001</Multiplier>"
        "<Divisor>0x000003e8</Divisor>"
        "</CurrentSummationDelivered></rainforest>"
    )


def msg_price(price, meter_mac):
    raw = max(0, round(price * 10000))  # digits=4 -> collector price = raw/1e4
    return (
        "<rainforest><PriceCluster>"
        f"<DeviceMacId>{DEVICE_MAC}</DeviceMacId>"
        f"<MeterMacId>{meter_mac}</MeterMacId>"
        f"<TimeStamp>{_hexts()}</TimeStamp>"
        f"<Price>0x{raw:08x}</Price>"
        "<TrailingDigits>0x04</TrailingDigits>"
        "</PriceCluster></rainforest>"
    )


def post_eagle(xml, timeout=15):
    token = base64.b64encode(f"{UPLOAD_USER}:{UPLOAD_PASS}".encode()).decode()
    req = urllib.request.Request(
        UPLOAD_URL,
        data=xml.encode(),
        headers={"Authorization": f"Basic {token}", "Content-Type": "text/xml"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200]
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def ship(dry_run=False, verbose=False):
    """Read the meter and push whatever telemetry it has. Returns True if we sent
    (or would have) at least one message."""
    readings, meter_mac, err = read_meter()
    if err:
        log(f"local read failed ({err}); nothing to ship")
        return False
    meter_mac = meter_mac or METER_MAC_FALLBACK

    outbox = []
    if "demand_kw" in readings:
        outbox.append(("demand", msg_demand(readings["demand_kw"], meter_mac)))
    if "summation_kwh" in readings:
        outbox.append(("summation", msg_summation(readings["summation_kwh"], meter_mac)))
    if "price" in readings:
        outbox.append(("price", msg_price(readings["price"], meter_mac)))

    if not outbox:
        log("local API returned no demand/summation/price; nothing to ship")
        return False

    summary = (
        f"demand={readings.get('demand_kw')}kW "
        f"summation={readings.get('summation_kwh')}kWh "
        f"price={readings.get('price')}"
    )
    if dry_run:
        log(f"DRY-RUN would ship: {summary}")
        for name, xml in outbox:
            print(f"--- {name} ---\n{xml}\n", file=sys.stderr)
        return True

    ok = 0
    for name, xml in outbox:
        status, body = post_eagle(xml)
        if verbose:
            log(f"  {name}: HTTP {status} {body}")
        if status == 200:
            ok += 1
        else:
            log(f"  {name}: upload FAILED HTTP {status} {body}")
    log(f"shipped {ok}/{len(outbox)} messages  [{summary}]")
    return ok > 0


def run_loop(args):
    active = args.force            # force => always active
    probing = False               # currently in a one-cycle upload pause?
    last_probe = time.monotonic()

    while True:
        age = fly_age_seconds()
        age_str = "unknown" if age is None else f"{round(age)}s"

        if args.force:
            ship(dry_run=args.dry_run, verbose=args.verbose)
        elif not active:
            # Standby: activate only when the cloud path has gone stale.
            if age is None or age > args.stale_secs:
                active = True
                last_probe = time.monotonic()
                log(f"cloud stale (age={age_str} > {args.stale_secs}s) -> ACTIVATING bypass")
                ship(dry_run=args.dry_run, verbose=args.verbose)
            else:
                log(f"cloud healthy (age={age_str}) -> standby")
        else:
            # Active. Our own ships keep `age` fresh, so we can't read recovery off
            # the clock directly -- periodically go silent for one cycle and look.
            if probing:
                probing = False
                if age is not None and age <= args.stale_secs:
                    active = False
                    log(f"probe: cloud fresh while we were silent (age={age_str}) "
                        f"-> Rainforest recovered, RETURNING TO STANDBY")
                else:
                    log(f"probe: still stale (age={age_str}) -> resuming shipping")
                    ship(dry_run=args.dry_run, verbose=args.verbose)
            elif (time.monotonic() - last_probe) >= args.probe_secs:
                probing = True
                last_probe = time.monotonic()
                log("probe: pausing uploads one cycle to test whether Rainforest recovered")
            else:
                ship(dry_run=args.dry_run, verbose=args.verbose)

        if args.once:
            return
        time.sleep(args.interval)


def main():
    ap = argparse.ArgumentParser(description="Ship Eagle local-API data to Fly /eagle as synthetic Rainforest XML.")
    ap.add_argument("--interval", type=int, default=30, help="seconds between cycles (default 30)")
    ap.add_argument("--stale-secs", type=int, default=90,
                    help="consider the cloud path down after this many seconds of no data (default 90)")
    ap.add_argument("--probe-secs", type=int, default=300,
                    help="while active, pause uploads one cycle this often to test cloud recovery (default 300)")
    ap.add_argument("--force", action="store_true", help="ship every cycle regardless of cloud health (always-on)")
    ap.add_argument("--once", action="store_true", help="run a single cycle and exit")
    ap.add_argument("--dry-run", action="store_true", help="build and print XML; do not POST")
    ap.add_argument("-v", "--verbose", action="store_true", help="log each upload's HTTP result")
    args = ap.parse_args()

    if not CLOUD_ID or not INSTALL_CODE:
        log("FATAL: set EAGLE_CLOUD_ID and EAGLE_INSTALL_CODE (local API auth)")
        sys.exit(2)
    if not UPLOAD_PASS and not args.dry_run:
        log("FATAL: set EAGLE_UPLOAD_PASSWORD (the EAGLE_PASSWORD secret on the Fly app)")
        sys.exit(2)

    mode = "FORCE (always-on)" if args.force else f"FAILOVER (stale>{args.stale_secs}s)"
    log(f"eagle_bypass starting: {mode}, every {args.interval}s, Eagle={EAGLE_IP} -> {UPLOAD_URL}")
    try:
        run_loop(args)
    except KeyboardInterrupt:
        log("stopped")


if __name__ == "__main__":
    main()
