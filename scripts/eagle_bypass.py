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

    Force (always-on) is the DEFAULT: the Pi is the sole uploader, so it ships every
    cycle. The failover behaviour above is opt-in via --failover, for the day the Eagle
    uploads on its own again (else you'd get near-duplicate points).

    --failover     ship only while the real cloud path is stale (the old default)
    --once         run a single cycle and exit (for cron/systemd timer)
    --dry-run      build and print the XML; do not POST

POLLING CADENCE (--interval, default 30s)
    The Eagle natively reports InstantaneousDemand every ~8-10s. We deliberately poll
    slower, at 30s, for two reasons: the device is failing under CPU/storage load, so
    we avoid roughly 4x the query pressure its native rate would add; and the dashboard
    treats data as stale only after 2 minutes, so 30s is ample resolution. The failover
    margins assumed it too (stale-secs 90 = 3 cycles, probe-secs 300 = 10 cycles). Kept
    at 30s even now that the Pi is the primary uploader (decided 2026-07-14): the goal
    is to nurse the aging hardware, not to stress it.

CREDENTIALS (from the environment; never logged)
    Local API (read from the Eagle):
        EAGLE_IP            default 192.168.68.63
        EAGLE_CLOUD_ID      Cloud ID  (Basic-auth user for the local API)
        EAGLE_INSTALL_CODE  Install Code (Basic-auth pass for the local API)
    Upload (write to our Fly /eagle, same Basic auth the Rainforest uploader uses):
        EAGLE_UPLOAD_URL       default https://linknode-eagle-monitor.fly.dev/eagle
        EAGLE_UPLOAD_USER      default 'eagle'  (matches EAGLE_USERNAME on Fly)
        EAGLE_UPLOAD_PASSWORD  the EAGLE_PASSWORD secret set on the Fly app

Usage:  python eagle_bypass.py [--interval 30] [--failover [--stale-secs 90]
                               [--probe-secs 300]] [--once] [--dry-run] [-v]
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
from datetime import datetime, timedelta, timezone

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


def _meter_link(xml):
    """The Zigbee link to the meter, from device_list: (ConnectionStatus, LastContact).
    This is the Eagle<->meter side, which stays healthy even as the cloud path rots;
    it's our best on-device signal for how much life the pairing has left."""
    st = re.search(r"<ConnectionStatus>([^<]*)</ConnectionStatus>", xml or "")
    lc = re.search(r"<LastContact>([^<]*)</LastContact>", xml or "")
    return (st.group(1).strip() if st else None, lc.group(1).strip() if lc else None)


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
        return {}, None, f"device_list: {err}", None
    link = _meter_link(xml)
    meter_mac = find_meter_mac(xml) or METER_MAC_FALLBACK

    xml, err = local_api(DEVICE_QUERY.format(mac=meter_mac))
    if err:
        return {}, meter_mac, f"device_query: {err}", link

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
    return readings, meter_mac, None, link


# ---- build the synthetic Rainforest messages -------------------------------
# We reconstruct the raw Zigbee wire form (hex value + multiplier/divisor) so the
# collector's existing decimal math reproduces exactly these readings. One message
# per document: the collector parses the first matching type and ignores the rest.
def _hexts():
    return f"0x{int(time.time()) - ZIGBEE_EPOCH_OFFSET:x}"


def _reading_ts(link):
    """Reading timestamp (Zigbee-epoch hex) from the meter's LastContact, i.e. when the
    Eagle actually last heard from the meter, NOT wall-clock now. This is what makes a
    reading count as *fresh*: if the Eagle's daemon hangs it keeps returning the same
    LastContact, so successive ships collapse onto the same time-series point instead of
    looking like new readings. LastContact is raw Unix; the collector re-adds the epoch
    offset, so subtract it here (same convention as _hexts). Falls back to now if the
    Eagle gave us no usable LastContact."""
    lc = link[1] if link else None
    if lc:
        try:
            unix = int(lc, 16) if str(lc).startswith("0x") else int(lc)
            return f"0x{unix - ZIGBEE_EPOCH_OFFSET:x}"
        except (ValueError, TypeError):
            pass
    return _hexts()


def msg_demand(kw, meter_mac, ts=None):
    raw = max(0, round(kw * 1000))  # watts; mult=1 div=1000 -> collector power_w = raw
    return (
        "<rainforest><InstantaneousDemand>"
        f"<DeviceMacId>{DEVICE_MAC}</DeviceMacId>"
        f"<MeterMacId>{meter_mac}</MeterMacId>"
        f"<TimeStamp>{ts or _hexts()}</TimeStamp>"
        f"<Demand>0x{raw:08x}</Demand>"
        "<Multiplier>0x00000001</Multiplier>"
        "<Divisor>0x000003e8</Divisor>"
        "</InstantaneousDemand></rainforest>"
    )


def msg_summation(kwh, meter_mac, ts=None):
    raw = max(0, round(kwh * 1000))  # Wh; mult=1 div=1000 -> collector kWh = raw/1000
    return (
        "<rainforest><CurrentSummationDelivered>"
        f"<DeviceMacId>{DEVICE_MAC}</DeviceMacId>"
        f"<MeterMacId>{meter_mac}</MeterMacId>"
        f"<TimeStamp>{ts or _hexts()}</TimeStamp>"
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


def msg_bypass_status(snap):
    """A side-channel heartbeat carrying the bypass's own reliability numbers, so the
    dashboard can show real uptime instead of a hardcoded value. Not a Rainforest
    telemetry type: the collector stashes it in its stats and never writes it to the
    time-series or touches the data-freshness signal with it."""
    def num(v):
        return "" if v is None else repr(v) if isinstance(v, float) else str(v)
    return (
        "<rainforest><BypassStatus>"
        f"<DeviceMacId>{DEVICE_MAC}</DeviceMacId>"
        f"<TimeStamp>{_hexts()}</TimeStamp>"
        f"<DataUptimePct>{num(snap.get('data_availability_pct'))}</DataUptimePct>"
        f"<DeviceUptimePct>{num(snap.get('device_availability_pct'))}</DeviceUptimePct>"
        f"<ObservedSeconds>{num(snap.get('observed_s'))}</ObservedSeconds>"
        f"<OutageCount>{num(snap.get('outage_count'))}</OutageCount>"
        f"<TotalOutageSeconds>{num(snap.get('total_outage_s'))}</TotalOutageSeconds>"
        f"<WorstOutageSeconds>{num(snap.get('worst_outage_s'))}</WorstOutageSeconds>"
        f"<ReadingsRescued>{num(snap.get('readings_rescued'))}</ReadingsRescued>"
        f"<IntervalSeconds>{num(snap.get('interval_s'))}</IntervalSeconds>"
        "</BypassStatus></rainforest>"
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


# ---- outage-log helpers ----------------------------------------------------
OUTAGE_LOG_CAP = 100                 # retain this many recent outage records
_DUR_EDGES = [60, 300, 900, 3600]    # bucket boundaries; 5 buckets incl. the tail
_DUR_LABELS = ["<1m", "1-5m", "5-15m", "15-60m", ">60m"]


def _local_hour():
    return datetime.now(timezone.utc).astimezone().hour   # Pi's tz, via timesyncd


def _dur_bucket(s):
    for i, edge in enumerate(_DUR_EDGES):
        if s < edge:
            return i
    return len(_DUR_EDGES)


def _parse_iso(iso):
    try:
        return datetime.fromisoformat(iso)
    except Exception:
        return None


def _fmt_dur(s):
    if s is None:
        return "?"
    s = int(s)
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{sec:02d}s"
    return f"{sec}s"


def _bar(v, vmax, width=22):
    if not vmax or vmax <= 0:
        return ""
    return "█" * max(0, int(round(width * v / vmax)))


class Stats:
    """In-RAM counters, mirrored to a live RAM file each cycle and checkpointed to
    two CRC-protected flash copies hourly. On start, restore from a valid copy."""

    SCHEMA = 3

    def __init__(self, runtime_dir, state_dir):
        self.live_path = os.path.join(runtime_dir, "stats.json") if runtime_dir else None
        self.copies = ([os.path.join(state_dir, "stats.a.json"),
                        os.path.join(state_dir, "stats.b.json")] if state_dir else [])
        self._last_flush = time.monotonic()
        self._cur_start_mono = None   # monotonic start of the open outage (RAM only)
        self.interval = 30            # set by run_loop; used to accrue observed time
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
            # ---- outage log + reliability analytics ----
            "outages": [], "current_outage": None,
            "outage_count": 0, "total_outage_s": 0, "worst_outage_s": 0,
            "first_outage_at": None, "last_outage_end": None,
            "outages_by_hour": [0] * 24, "duration_buckets": [0] * 5,
            "observed_s": 0, "readings_rescued": 0,
            # ---- meter (Zigbee) link health, from device_list ----
            "meter_status": None, "meter_last_contact": None,
            "meter_link_checks": 0, "meter_not_connected": 0,
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
        # Backfill any keys added since this checkpoint was written (schema upgrade).
        for k, v in self._fresh().items():
            self.d.setdefault(k, v)
        # An outage open at shutdown can't get a real duration (monotonic is gone);
        # record it as incomplete rather than inventing one.
        co = self.d.get("current_outage")
        if co:
            self.d["outages"].append({"n": co.get("n"), "start": co.get("start"),
                                      "end": None, "duration_s": None,
                                      "ships": co.get("ships", 0),
                                      "read_fails": co.get("read_fails", 0),
                                      "incomplete": True})
            self.d["outages"] = self.d["outages"][-OUTAGE_LOG_CAP:]
            self.d["outage_count"] += 1
            self.d["current_outage"] = None
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

        # Derived reliability metrics. observed_s is the wall time we watched the
        # device: cycles run one per `interval`, and interval is fixed, so
        # cycles * interval is the exact watched time and needs no separate
        # accumulator (which would restart at zero on a schema upgrade). It is the
        # denominator for availability and MTBF; a reboot gap is time we were NOT
        # watching (no cycles ran), so it correctly does not count.
        obs = d.get("cycles", 0) * self.interval
        d["observed_s"] = obs
        d["interval_s"] = self.interval   # report our cadence so the site can size "expected"
        n = d.get("outage_count", 0)
        completed = sum(d.get("duration_buckets", []))   # outages with a real duration
        d["mean_outage_s"] = round(d["total_outage_s"] / completed) if completed else None
        d["mtbf_s"] = round(obs / n) if n else None
        d["device_availability_pct"] = (
            round(max(0.0, min(100.0, 100.0 * (obs - d["total_outage_s"]) / obs)), 2)
            if obs else None)
        # Data availability: the uptime a dashboard viewer actually experiences.
        # Fresh data reached the site on any cycle we sat in standby (the real Eagle
        # was fine) or successfully shipped a reading (we covered an outage). Probe
        # cycles and failed ships are the only gaps. This is the number the bypass
        # exists to keep high.
        cyc = d.get("cycles", 0)
        available_cycles = d.get("standby_cycles", 0) + d.get("readings_rescued", 0)
        d["data_availability_pct"] = (
            round(max(0.0, min(100.0, 100.0 * available_cycles / cyc)), 2) if cyc else None)
        if d.get("current_outage") and self._cur_start_mono is not None:
            d["current_outage_s"] = int(round(time.monotonic() - self._cur_start_mono))
        # Meter (Zigbee) link: how often device_list reported the meter Connected.
        checks = d.get("meter_link_checks", 0)
        d["meter_link_pct"] = (
            round(100.0 * (checks - d.get("meter_not_connected", 0)) / checks, 2)
            if checks else None)
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
        # Open an outage record. Duration is measured on the monotonic clock so an
        # NTP step mid-outage can't distort it; the wall-clock start is for display.
        self._cur_start_mono = time.monotonic()
        hour = _local_hour()
        self.d["outages_by_hour"][hour] += 1
        if not self.d.get("first_outage_at"):
            self.d["first_outage_at"] = now_iso()
        self.d["current_outage"] = {"n": self.d["outage_count"] + 1, "start": now_iso(),
                                    "hour": hour, "ships": 0, "read_fails": 0}

    def note_recovery(self):
        """Close the open outage: Rainforest's own cloud path came back."""
        co = self.d.get("current_outage")
        if not co:
            return
        if self._cur_start_mono is not None:
            dur = int(round(time.monotonic() - self._cur_start_mono))
        else:
            dur = None   # started before this process; fall back to wall clock below
            start = _parse_iso(co.get("start"))
            if start:
                dur = int(round((datetime.now(timezone.utc) - start).total_seconds()))
        rec = {"n": co.get("n"), "start": co.get("start"), "end": now_iso(),
               "duration_s": dur, "hour": co.get("hour"),
               "ships": co.get("ships", 0), "read_fails": co.get("read_fails", 0)}
        self.d["outages"].append(rec)
        self.d["outages"] = self.d["outages"][-OUTAGE_LOG_CAP:]
        self.d["outage_count"] += 1
        self.d["last_outage_end"] = rec["end"]
        if dur is not None:
            self.d["total_outage_s"] += dur
            if dur > self.d["worst_outage_s"]:
                self.d["worst_outage_s"] = dur
            self.d["duration_buckets"][_dur_bucket(dur)] += 1
        self.d["current_outage"] = None
        self._cur_start_mono = None
        log(f"outage #{rec['n']} ended: down {_fmt_dur(dur)}, "
            f"rescued {rec['ships']} readings ({rec['read_fails']} read failures during it)")

    def note_ship(self, sent, ok):
        self.d["ship_cycles"] += 1
        self.d["ships_today"] += 1
        self.d["messages_sent"] += sent
        self.d["messages_ok"] += ok
        self.d["messages_failed"] += max(0, sent - ok)
        self.d["last_ship"] = now_iso()
        if ok > 0:
            self.d["readings_rescued"] += 1
        co = self.d.get("current_outage")
        if co:
            co["ships"] += 1

    def note_read_failure(self, kind):
        self.d["read_failures"][kind] = self.d["read_failures"].get(kind, 0) + 1
        co = self.d.get("current_outage")
        if co:
            co["read_fails"] += 1

    def note_meter_link(self, status, last_contact):
        """Record the Eagle<->meter Zigbee link state seen in device_list."""
        self.d["meter_link_checks"] += 1
        self.d["meter_status"] = status
        if last_contact:
            self.d["meter_last_contact"] = last_contact
        if status and status != "Connected":
            self.d["meter_not_connected"] += 1


def load_snapshot():
    """The live snapshot from tmpfs if the service is running, else a fresh snapshot
    rebuilt from the newest valid flash copy. Returns a dict either way."""
    for path in [p for p in [RUNTIME_DIR and os.path.join(RUNTIME_DIR, "stats.json"),
                             "/run/eagle-bypass/stats.json"] if p]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
    return Stats(None, STATE_DIR or "/var/lib/eagle-bypass")._snapshot()


def print_stats():
    """Print the running service's live snapshot, or the newest valid flash copy."""
    print(json.dumps(load_snapshot(), indent=2))


def render_report(d):
    """A human-readable outage report built from a snapshot dict. Pure text, so it
    renders the same in a terminal, `journalctl`, or an email."""
    L = []
    def line(s=""): L.append(s)

    avail = d.get("device_availability_pct")
    obs = d.get("observed_s") or 0
    n = d.get("outage_count", 0)
    rescued = d.get("readings_rescued", 0)

    line("=" * 56)
    line("  EAGLE-200 BYPASS  --  reliability report")
    line("=" * 56)
    line(f"  snapshot   {d.get('snapshot_at', '?')}")
    watched = _fmt_dur(obs)
    line(f"  watching   {watched} of wall time across {d.get('cycles', 0)} cycles")
    line("")

    # Headline: the uptime a viewer actually experiences (data reaching the site),
    # then the device's own uptime and what the bypass did about the gap.
    data_avail = d.get("data_availability_pct")
    if data_avail is not None:
        line(f"  DATA UPTIME        {data_avail:5.2f}%   (fresh data reaching the site)")
    if avail is not None:
        down = _fmt_dur(d.get("total_outage_s", 0))
        line(f"  DEVICE UPTIME      {avail:5.2f}%   (Eagle-200 itself; down {down} of that time)")
    line(f"  BYPASS COVERAGE   100.00%   ({rescued} readings rescued during outages)")
    line("")
    line(f"  outages seen ....... {n}")
    if d.get("mtbf_s"):
        line(f"  mean time between .. {_fmt_dur(d['mtbf_s'])}")
    if d.get("mean_outage_s") is not None:
        line(f"  mean outage ........ {_fmt_dur(d['mean_outage_s'])}")
    if d.get("worst_outage_s"):
        line(f"  worst outage ....... {_fmt_dur(d['worst_outage_s'])}")
    if d.get("current_outage"):
        line(f"  >> OUTAGE IN PROGRESS  ({_fmt_dur(d.get('current_outage_s'))} and counting)")
    line("")

    # How long outages last -- the shape of the flakiness.
    buckets = d.get("duration_buckets", [])
    if any(buckets):
        line("  outage duration")
        bmax = max(buckets)
        for label, v in zip(_DUR_LABELS, buckets):
            line(f"    {label:>7}  {_bar(v, bmax):<22} {v}")
        line("")

    # When they happen -- hour of day (local). Collapse to a compact 24-col strip.
    by_hour = d.get("outages_by_hour", [])
    if any(by_hour):
        hmax = max(by_hour)
        line("  outages by hour of day (local)")
        # sparkline-style using block heights
        blocks = " ▁▂▃▄▅▆▇█"
        strip = "".join(blocks[min(len(blocks) - 1, int(round((len(blocks) - 1) * v / hmax)))]
                        if hmax else " " for v in by_hour)
        line(f"    {strip}")
        line("    0   3   6   9   12  15  18  21")
        peak = by_hour.index(hmax)
        line(f"    busiest hour: {peak:02d}:00-{(peak + 1) % 24:02d}:00 ({hmax} outages)")
        line("")

    # Recent outages, newest first.
    outs = d.get("outages", [])
    if outs:
        line("  recent outages (newest first)")
        line(f"    {'when (start)':<20} {'lasted':>8}  {'rescued':>7}")
        for o in reversed(outs[-8:]):
            start = (o.get("start") or "?")[:19].replace("T", " ")
            if o.get("incomplete"):
                dur = "cut*"
            else:
                dur = _fmt_dur(o.get("duration_s"))
            line(f"    {start:<20} {dur:>8}  {o.get('ships', 0):>7}")
        if any(o.get("incomplete") for o in outs):
            line("    * outage was open when the service last stopped; duration unknown")
        line("")

    # Read-failure breakdown -- the device's symptom mix.
    rf = d.get("read_failures", {})
    if any(rf.values()):
        parts = ", ".join(f"{k}={v}" for k, v in sorted(rf.items()) if v)
        line(f"  device read failures: {parts}")
    # Meter (Zigbee) link -- the Eagle<->meter side, our best "life left" signal.
    if d.get("meter_link_checks"):
        mp = d.get("meter_link_pct")
        line(f"  meter link: {d.get('meter_status')} "
             f"({mp if mp is not None else '?'}% Connected over {d['meter_link_checks']} checks, "
             f"{d.get('meter_not_connected', 0)} not-connected)")
    line(f"  service: restart #{d.get('restarts', 0)}, "
         f"{d.get('reboots', 0)} OS reboots, "
         f"~{d.get('approx_running_h', 0)}h running (hourly flash saves)")
    line("=" * 56)
    return "\n".join(L)


def ship(stats, dry_run=False, verbose=False):
    """Read the meter and push whatever telemetry it has. Returns True if we sent
    (or would have) at least one message."""
    readings, meter_mac, err, link = read_meter()
    if link:
        stats.note_meter_link(*link)
    if err:
        stats.note_read_failure(_classify_read_error(err))
        log(f"local read failed ({err}); nothing to ship")
        return False
    meter_mac = meter_mac or METER_MAC_FALLBACK

    # Stamp readings with the meter's real last-contact time, so a frozen Eagle
    # (LastContact not advancing) does not masquerade as a stream of fresh readings.
    ts = _reading_ts(link)
    outbox = []
    if "demand_kw" in readings:
        outbox.append(("demand", msg_demand(readings["demand_kw"], meter_mac, ts)))
    if "summation_kwh" in readings:
        outbox.append(("summation", msg_summation(readings["summation_kwh"], meter_mac, ts)))
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


def ship_status(stats, dry_run=False, verbose=False):
    """POST the reliability heartbeat so the dashboard can show live uptime. Best
    effort: a failure here must never disturb the failover loop."""
    xml = msg_bypass_status(stats._snapshot())
    if dry_run:
        log("DRY-RUN would ship bypass status heartbeat")
        if verbose:
            print(f"--- bypass_status ---\n{xml}\n", file=sys.stderr)
        return
    status, body = post_eagle(xml)
    if verbose or status != 200:
        log(f"  bypass_status: HTTP {status} {body}")


def run_loop(args, stats):
    active = args.force            # force => always active
    probing = False               # currently in a one-cycle upload pause?
    last_probe = time.monotonic()
    stats.interval = args.interval   # so observed_s accrues real wall time per cycle
    last_heartbeat = None            # force one on the first cycle so the site populates fast

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
                    stats.note_recovery()
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

        # Reliability heartbeat: independent of standby/active so the dashboard's
        # uptime stays fresh even during long clean runs. Sent after note_cycle so
        # this cycle is already counted in the numbers we report.
        now_mono = time.monotonic()
        if last_heartbeat is None or (now_mono - last_heartbeat) >= args.heartbeat_secs:
            ship_status(stats, dry_run=args.dry_run, verbose=args.verbose)
            last_heartbeat = now_mono

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
    ap.add_argument("--heartbeat-secs", type=int, default=900,
                    help="ship a reliability/uptime heartbeat to the dashboard this often, any mode (default 900)")
    ap.add_argument("--failover", action="store_true",
                    help="failover mode: ship only while the real cloud path is stale. "
                         "Default is force / always-on (the Pi is the sole uploader).")
    # Force (always-on) is the default now; --force is accepted for backward compatibility
    # (the old systemd unit passed it explicitly) but is redundant. --failover opts out.
    ap.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--once", action="store_true", help="run a single cycle and exit")
    ap.add_argument("--dry-run", action="store_true", help="build and print XML; do not POST")
    ap.add_argument("-v", "--verbose", action="store_true", help="log each upload's HTTP result")
    ap.add_argument("--print-stats", action="store_true",
                    help="print the current stats snapshot (JSON) and exit")
    ap.add_argument("--report", action="store_true",
                    help="print a human-readable reliability/outage report and exit")
    args = ap.parse_args()

    # Force (always-on) is the default; --failover is the explicit opt-out. The rest of
    # the code keys off args.force, so derive it here. An explicit --force is a harmless
    # no-op (default is already force); --failover always wins.
    args.force = not args.failover

    if args.print_stats:
        print_stats()
        return
    if args.report:
        print(render_report(load_snapshot()))
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
