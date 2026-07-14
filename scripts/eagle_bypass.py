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
import json
import os
import re
import signal
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zlib
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

# ---- stats persistence -----------------------------------------------------
# Counters live in RAM, are mirrored to a RAM-backed live file every cycle (systemd
# RuntimeDirectory, /run/eagle-bypass) for zero-wear querying, and are checkpointed
# once an hour to TWO CRC-protected copies on flash (systemd StateDirectory,
# /var/lib/eagle-bypass). On start we restore from whichever copy has a valid CRC.
# systemd supplies both dirs; if unset (e.g. a manual run) persistence is disabled.
FLUSH_INTERVAL_S = 3600  # checkpoint cadence to flash


def _cfg_dir(*env_names):
    for n in env_names:
        p = os.environ.get(n)
        if p:
            try:
                os.makedirs(p, exist_ok=True)
                return p if os.access(p, os.W_OK) else None
            except OSError:
                return None
    return None


RUNTIME_DIR = _cfg_dir("RUNTIME_DIRECTORY", "EAGLE_RUNTIME_DIR")
STATE_DIR = _cfg_dir("STATE_DIRECTORY", "EAGLE_STATE_DIR")


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


def _utc_day():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _boot_id():
    # Changes on every OS boot; lets us tell a real Pi reboot from a service restart.
    try:
        with open("/proc/sys/kernel/random/boot_id", "r") as f:
            return f.read().strip()
    except OSError:
        return None


def _classify_read_error(err):
    e = (err or "").lower()
    if "503" in e:
        return "http_503"
    if "timeout" in e or "timed out" in e:
        return "timeout"
    return "http_other"


class Stats:
    """In-RAM counters, mirrored to a live RAM file each cycle and checkpointed to
    two CRC-protected flash copies hourly. On start, restore from a valid copy."""

    SCHEMA = 1

    def __init__(self, runtime_dir, state_dir):
        self.live_path = os.path.join(runtime_dir, "stats.json") if runtime_dir else None
        self.copies = ([os.path.join(state_dir, "stats.a.json"),
                        os.path.join(state_dir, "stats.b.json")] if state_dir else [])
        self._last_flush = time.monotonic()
        self.d = self._fresh()
        self._restore()

    def _fresh(self):
        n = now_iso()
        return {
            "schema": self.SCHEMA,
            "first_started_at": n, "process_started_at": n,
            "last_saved_at": None, "save_seq": 0,
            "restarts": 0, "reboots": 0, "boot_id": _boot_id(),
            "mode": "starting", "last_cloud_age_s": None,
            "cycles": 0, "standby_cycles": 0, "active_cycles": 0, "activations": 0,
            "ship_cycles": 0, "messages_sent": 0, "messages_ok": 0, "messages_failed": 0,
            "read_failures": {"timeout": 0, "http_503": 0, "http_other": 0, "empty": 0},
            "last_activation": None, "last_ship": None,
            "longest_clean_run_s": 0, "clean_run_since": n,
            "utc_day": _utc_day(), "activations_today": 0, "ships_today": 0,
        }

    # ---- restore / persist -------------------------------------------------
    def _read_copy(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                outer = json.load(f)
            body = outer["stats_json"]
            if zlib.crc32(body.encode("utf-8")) != outer["crc32"]:
                log(f"stats: CRC mismatch on {os.path.basename(path)}; ignoring")
                return None
            return json.loads(body)
        except FileNotFoundError:
            return None
        except Exception as e:
            log(f"stats: unreadable {os.path.basename(path)} ({type(e).__name__}); ignoring")
            return None

    def _restore(self):
        best = None
        for p in self.copies:
            data = self._read_copy(p)
            if data is not None and (best is None or
                                     data.get("save_seq", -1) > best.get("save_seq", -1)):
                best = data
        if best is None:
            if self.copies:
                log("stats: no valid flash copy; starting fresh counters")
            return
        first = best.get("first_started_at") or self.d["first_started_at"]
        self.d.update(best)
        self.d["first_started_at"] = first
        self.d["process_started_at"] = now_iso()
        self.d["restarts"] = best.get("restarts", 0) + 1
        # A changed kernel boot id means the Pi actually rebooted (vs a service restart).
        cur_boot, prev_boot = _boot_id(), best.get("boot_id")
        rebooted = cur_boot is not None and prev_boot is not None and cur_boot != prev_boot
        self.d["reboots"] = best.get("reboots", 0) + (1 if rebooted else 0)
        self.d["boot_id"] = cur_boot or prev_boot
        self.d["mode"] = "starting"
        self.d["clean_run_since"] = now_iso()   # the downtime interrupted any streak
        self._roll_day()
        log(f"stats: restored from flash (seq={best.get('save_seq')}, "
            f"restart #{self.d['restarts']}, reboots={self.d['reboots']}, rebooted={rebooted})")

    def _atomic_write(self, path, text, fsync=False):
        d = os.path.dirname(path)
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                if fsync:
                    os.fsync(f.fileno())
            os.replace(tmp, path)
            if fsync:
                try:
                    dfd = os.open(d, os.O_RDONLY)
                    try:
                        os.fsync(dfd)
                    finally:
                        os.close(dfd)
                except OSError:
                    pass
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def flush(self):
        """Checkpoint to both flash copies, each atomic and CRC-tagged. Cheap, rare."""
        if not self.copies:
            return
        try:
            self.d["save_seq"] += 1
            self.d["last_saved_at"] = now_iso()
            body = json.dumps(self.d, sort_keys=True, separators=(",", ":"))
            outer = json.dumps({"crc32": zlib.crc32(body.encode("utf-8")), "stats_json": body})
            for p in self.copies:           # copy A then B; at least one stays valid
                self._atomic_write(p, outer, fsync=True)
            self._last_flush = time.monotonic()
            log(f"stats: checkpointed to flash (seq={self.d['save_seq']}, 2 copies)")
        except Exception as e:
            log(f"stats: flash checkpoint failed ({type(e).__name__}: {e})")

    def maybe_flush(self):
        if self.copies and (time.monotonic() - self._last_flush) >= FLUSH_INTERVAL_S:
            self.flush()

    def _snapshot(self):
        d = dict(self.d)
        now = datetime.now(timezone.utc)

        def age(iso):
            try:
                return round((now - datetime.fromisoformat(iso)).total_seconds())
            except Exception:
                return None

        d["snapshot_at"] = now.isoformat()
        d["process_uptime_s"] = age(d["process_started_at"])
        d["total_uptime_s"] = age(d["first_started_at"])
        cur = age(d["clean_run_since"]) if d.get("clean_run_since") else None
        d["current_clean_run_s"] = cur
        if cur and cur > d["longest_clean_run_s"]:
            d["longest_clean_run_s"] = cur
        # Each flash checkpoint is ~hourly, so the save count is a downtime-excluded
        # estimate of accumulated running hours (survives reboots; total_uptime_s does not).
        d["flash_saves"] = d.get("save_seq", 0)
        d["approx_running_h"] = d.get("save_seq", 0)
        return d

    def write_live(self):
        if not self.live_path:
            return
        try:
            self._atomic_write(self.live_path, json.dumps(self._snapshot(), indent=2))
        except Exception:
            pass   # stats bookkeeping must never break the failover loop

    # ---- counter updates ---------------------------------------------------
    def _roll_day(self):
        today = _utc_day()
        if self.d.get("utc_day") != today:
            self.d["utc_day"] = today
            self.d["activations_today"] = 0
            self.d["ships_today"] = 0

    def note_cycle(self, mode, cloud_age):
        self._roll_day()
        self.d["cycles"] += 1
        self.d["mode"] = mode
        self.d["last_cloud_age_s"] = None if cloud_age is None else round(cloud_age)
        if mode == "standby":
            self.d["standby_cycles"] += 1
        else:
            self.d["active_cycles"] += 1

    def note_activation(self):
        since = self.d.get("clean_run_since")
        if since:
            try:
                dur = (datetime.now(timezone.utc) - datetime.fromisoformat(since)).total_seconds()
                if dur > self.d["longest_clean_run_s"]:
                    self.d["longest_clean_run_s"] = round(dur)
            except Exception:
                pass
        self.d["activations"] += 1
        self.d["activations_today"] += 1
        self.d["last_activation"] = now_iso()
        self.d["clean_run_since"] = now_iso()

    def note_ship(self, sent, ok):
        self.d["ship_cycles"] += 1
        self.d["ships_today"] += 1
        self.d["messages_sent"] += sent
        self.d["messages_ok"] += ok
        self.d["messages_failed"] += max(0, sent - ok)
        self.d["last_ship"] = now_iso()

    def note_read_failure(self, kind):
        self.d["read_failures"][kind] = self.d["read_failures"].get(kind, 0) + 1


def print_stats():
    """Print the running service's live snapshot, or the newest valid flash copy."""
    for path in [p for p in [RUNTIME_DIR and os.path.join(RUNTIME_DIR, "stats.json"),
                             "/run/eagle-bypass/stats.json"] if p]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                print(f.read())
            return
        except OSError:
            continue
    print(json.dumps(Stats(None, STATE_DIR or "/var/lib/eagle-bypass")._snapshot(), indent=2))


def ship(stats, dry_run=False, verbose=False):
    """Read the meter and push whatever telemetry it has. Returns True if we sent
    (or would have) at least one message."""
    readings, meter_mac, err = read_meter()
    if err:
        stats.note_read_failure(_classify_read_error(err))
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
        stats.note_read_failure("empty")
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
    stats.note_ship(len(outbox), ok)
    log(f"shipped {ok}/{len(outbox)} messages  [{summary}]")
    return ok > 0


def run_loop(args, stats):
    active = args.force            # force => always active
    probing = False               # currently in a one-cycle upload pause?
    last_probe = time.monotonic()

    while True:
        age = fly_age_seconds()
        age_str = "unknown" if age is None else f"{round(age)}s"
        mode = "active"           # refined below for the standby/probing cases

        if args.force:
            ship(stats, dry_run=args.dry_run, verbose=args.verbose)
        elif not active:
            # Standby: activate only when the cloud path has gone stale.
            if age is None or age > args.stale_secs:
                active = True
                last_probe = time.monotonic()
                log(f"cloud stale (age={age_str} > {args.stale_secs}s) -> ACTIVATING bypass")
                stats.note_activation()
                ship(stats, dry_run=args.dry_run, verbose=args.verbose)
            else:
                mode = "standby"
                log(f"cloud healthy (age={age_str}) -> standby")
        else:
            # Active. Our own ships keep `age` fresh, so we can't read recovery off
            # the clock directly -- periodically go silent for one cycle and look.
            if probing:
                probing = False
                if age is not None and age <= args.stale_secs:
                    active = False
                    mode = "standby"
                    log(f"probe: cloud fresh while we were silent (age={age_str}) "
                        f"-> Rainforest recovered, RETURNING TO STANDBY")
                else:
                    log(f"probe: still stale (age={age_str}) -> resuming shipping")
                    ship(stats, dry_run=args.dry_run, verbose=args.verbose)
            elif (time.monotonic() - last_probe) >= args.probe_secs:
                probing = True
                last_probe = time.monotonic()
                mode = "probing"
                log("probe: pausing uploads one cycle to test whether Rainforest recovered")
            else:
                ship(stats, dry_run=args.dry_run, verbose=args.verbose)

        stats.note_cycle(mode, age)
        stats.write_live()
        stats.maybe_flush()

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
    ap.add_argument("--print-stats", action="store_true",
                    help="print the current stats snapshot (JSON) and exit")
    args = ap.parse_args()

    if args.print_stats:
        print_stats()
        return

    if not CLOUD_ID or not INSTALL_CODE:
        log("FATAL: set EAGLE_CLOUD_ID and EAGLE_INSTALL_CODE (local API auth)")
        sys.exit(2)
    if not UPLOAD_PASS and not args.dry_run:
        log("FATAL: set EAGLE_UPLOAD_PASSWORD (the EAGLE_PASSWORD secret on the Fly app)")
        sys.exit(2)

    stats = Stats(RUNTIME_DIR, STATE_DIR)
    log("stats: live=%s, flash=%s" % (
        RUNTIME_DIR or "off (in-RAM only)",
        ("2 CRC copies in " + STATE_DIR) if STATE_DIR else "off (no StateDirectory)"))

    def _flush_and_exit(signum, _frame):
        stats.flush()
        log(f"stats: checkpointed on signal {signum}; exiting")
        sys.exit(0)
    try:
        signal.signal(signal.SIGTERM, _flush_and_exit)   # systemd stop / reboot
    except (ValueError, AttributeError, OSError):
        pass   # e.g. not the main thread, or unsupported platform

    mode = "FORCE (always-on)" if args.force else f"FAILOVER (stale>{args.stale_secs}s)"
    log(f"eagle_bypass starting: {mode}, every {args.interval}s, Eagle={EAGLE_IP} -> {UPLOAD_URL}")
    try:
        run_loop(args, stats)
    except KeyboardInterrupt:
        stats.flush()
        log("stopped")


if __name__ == "__main__":
    main()
