#!/usr/bin/env python3
"""Outside watcher for linknode.com: Pushover alert when the ingest service or the
site stops answering.

WHY THIS EXISTS
    The ingest service on Fly already raises the alarm when telemetry stops arriving
    (monitor_data_staleness.py: meter link, Eagle, Pi, home network). It cannot report
    its own death, and nothing watched the site. This runs somewhere that is not Fly
    (the Pi) and covers that half, so the two watch each other.

WHAT IT CHECKS (one pass per run; systemd timer, every 2 minutes)
    ingest  GET <ingest>/health/data answers with its JSON. A 503 "stale" is the
            ingester alive and raising that alarm itself, so it only fails here once
            the reading is older than WATCH_BACKSTOP_SECS (the ingester's alarm should
            have fired long before: this is the backstop for a dead alarm thread).
    site    GET <site>/ is a 200 carrying the dashboard markup.
    api     GET <ingest>/api/stats as the page calls it: a 200 with the CORS header
            for the site's origin and a current_power value. Without that the page
            loads but shows no usage.

ALERTS
    A check alerts after WATCH_FAIL_THRESHOLD consecutive failures (default 3, about
    five minutes, so a deploy restart or a blip stays quiet): one emergency (siren)
    Pushover naming every check that just crossed the line. One normal-priority message
    when everything that had alerted is back. State is kept in $STATE_DIRECTORY and is
    only written when something changes, so a healthy system writes nothing to flash.

CREDENTIALS (from the environment; never logged)
    PUSHOVER_API_TOKEN, PUSHOVER_USER_KEY   the same application the ingester uses

Usage:  python3 linknode_watchdog.py [--dry-run] [--test-alert] [-v]
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

INGEST_URL = os.environ.get("WATCH_INGEST_URL", "https://linknode-eagle-monitor.fly.dev").rstrip("/")
SITE_URL = os.environ.get("WATCH_SITE_URL", "https://linknode.com").rstrip("/")
SITE_MARKER = os.environ.get("WATCH_SITE_MARKER", 'id="power-chart"')
FAIL_THRESHOLD = int(os.environ.get("WATCH_FAIL_THRESHOLD", "3"))
BACKSTOP_SECS = int(os.environ.get("WATCH_BACKSTOP_SECS", "900"))
PRIORITY = int(os.environ.get("WATCH_PRIORITY", "2"))  # 2 = emergency: repeats until acknowledged
TIMEOUT = 20

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_API_TOKEN", "")
PUSHOVER_USER = os.environ.get("PUSHOVER_USER_KEY", "")

STATE_DIR = os.environ.get("STATE_DIRECTORY") or os.environ.get("WATCH_STATE_DIR")
STATE_FILE = os.path.join(STATE_DIR, "state.json") if STATE_DIR else None

USER_AGENT = "linknode-watchdog/1.0"


def log(msg):
    print(f"{datetime.now(timezone.utc).isoformat()}  {msg}", file=sys.stderr, flush=True)


def fetch(url, headers=None):
    """(status, headers, body) for a GET; status is None when nothing answered, with the
    reason as the body. An HTTP error status is an answer, not an exception."""
    req = urllib.request.Request(url, headers=dict({"User-Agent": USER_AGENT}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.headers, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, {}, f"{type(e).__name__}: {e}"


# ---- checks: each returns None when healthy, else a one-line reason ----------
def check_ingest():
    status, _, body = fetch(INGEST_URL + "/health/data")
    if status is None:
        return f"no answer ({body})"
    try:
        data = json.loads(body)
    except ValueError:
        return f"HTTP {status}, not the health JSON"
    if status == 200:
        return None
    age = data.get("reading_age_seconds")
    if data.get("status") == "stale" and age is not None and age <= BACKSTOP_SECS:
        return None  # alive, and inside the window where its own alarm speaks for it
    if age is not None:
        return f"newest reading is {age / 60:.0f} min old"
    return f"HTTP {status}, status {data.get('status')!r}"


def check_site():
    status, _, body = fetch(SITE_URL + "/")
    if status is None:
        return f"no answer ({body})"
    if status != 200:
        return f"HTTP {status}"
    if SITE_MARKER not in body:
        return "page served without the dashboard markup"
    return None


def check_api():
    status, headers, body = fetch(INGEST_URL + "/api/stats", {"Origin": SITE_URL})
    if status is None:
        return f"no answer ({body})"
    if status != 200:
        return f"HTTP {status}"
    if headers.get("Access-Control-Allow-Origin") != SITE_URL:
        return "no CORS header for the site, so the page cannot read it"
    try:
        if json.loads(body).get("current_power") is None:
            return "no current_power in the reply"
    except ValueError:
        return "reply is not JSON"
    return None


CHECKS = (("ingest", check_ingest), ("site", check_site), ("api", check_api))
LABELS = {"ingest": "Ingest service", "site": "linknode.com", "api": "Stats API (what the page reads)"}


# ---- state and alerts --------------------------------------------------------
def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (TypeError, OSError, ValueError):
        return {}


def save_state(state):
    if not STATE_FILE:
        return
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)


def pushover(title, message, priority):
    """True once Pushover accepts the message."""
    if not (PUSHOVER_TOKEN and PUSHOVER_USER):
        log("pushover not configured (PUSHOVER_API_TOKEN / PUSHOVER_USER_KEY)")
        return False
    fields = {"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "title": title,
              "message": message, "priority": priority}
    if priority == 2:
        fields.update({"retry": 60, "expire": 3600, "sound": "siren"})
    req = urllib.request.Request(PUSHOVER_URL, data=urllib.parse.urlencode(fields).encode(),
                                 headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status == 200
    except Exception as e:
        log(f"pushover send failed: {type(e).__name__}: {e}")
        return False


def step(state, results, send):
    """Advance `state` by one pass of `results` ({check: reason or None}) and send what is
    due through `send(title, message, priority)`. Returns the new state.

    A check's `alerted` flag only flips once the message is accepted, so an alert that
    could not be sent (the home network is down too) is tried again on the next pass.
    """
    new = {}
    for name, reason in results.items():
        old = state.get(name, {})
        entry = {"fails": 0 if reason is None else old.get("fails", 0) + 1,
                 "alerted": bool(old.get("alerted"))}
        if reason is not None:
            entry["reason"] = reason
        new[name] = entry

    due = [n for n, e in new.items() if e["fails"] >= FAIL_THRESHOLD and not e["alerted"]]
    if due:
        lines = [f"{LABELS[n]}: {new[n]['reason']}" for n in due]
        if send("Linknode watchdog: DOWN", "\n".join(lines), PRIORITY):
            for n in due:
                new[n]["alerted"] = True

    back = [n for n, e in new.items() if e["alerted"] and e["fails"] == 0]
    still_down = [n for n, e in new.items() if e["alerted"] and e["fails"] > 0]
    if back and not still_down:
        if send("Linknode watchdog: recovered", ", ".join(LABELS[n] for n in back) + " answering again.", 0):
            for n in back:
                new[n]["alerted"] = False
    return new


def main():
    ap = argparse.ArgumentParser(description="Alert when linknode.com's ingest service or site stops answering.")
    ap.add_argument("--dry-run", action="store_true", help="run the checks and print them; no alert, no state")
    ap.add_argument("--test-alert", action="store_true", help="send one normal-priority test message and exit")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.test_alert:
        ok = pushover("Linknode watchdog: test", "Test message from the Pi watcher. Alerts are wired up.", 0)
        log("test alert " + ("sent" if ok else "FAILED"))
        return 0 if ok else 1

    results = {name: check() for name, check in CHECKS}
    for name, reason in results.items():
        if reason is not None or args.verbose or args.dry_run:
            log(f"{name}: {'ok' if reason is None else 'FAIL ' + reason}")
    if args.dry_run:
        return 0

    state = load_state()
    new = step(state, results, pushover)
    if new != state:
        save_state(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
