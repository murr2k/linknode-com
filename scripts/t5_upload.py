#!/usr/bin/env python3
"""Ship the thermostat logger's rows to the ingest service.

WHY THIS EXISTS
    The t5-runtime logger on this Pi (kept in the 1344-network repo) records the
    Honeywell T5 thermostat over HomeKit: one CSV row per change of state in
    /var/lib/t5-runtime/events.csv, and the time of its last good read in
    /run/t5-runtime/last_seen. linknode.com charts heating time and estimates the gas
    bill from those rows, so they have to reach the ingest service on Fly. This reads
    the two files and POSTs to /thermostat. It never writes to them, and it does not
    talk to the thermostat.

HOW IT KEEPS IN STEP
    Nothing is kept on the Pi. Every reply from /thermostat carries the time of the
    newest row the service holds; rows newer than that are the ones to send. A batch
    that may or may not have arrived is simply sent again (the service ignores rows it
    has). The reply also says what the newest row was before the batch: if that is
    older than the last reply's newest, the service's store was restored from a
    backup, and the file is read again from the top to fill the hole.

    The logger stamps a `lost` row with the time of its last good read, which can be
    earlier than the row before it. Rows are sent with strictly increasing times, a
    millisecond apart where needed, so file order is kept.

    With nothing new it still posts the logger's last-read time every minute: that is
    how the service knows the last state still holds, and that it stopped holding when
    the logger went quiet.

CREDENTIALS (from the environment; never logged)
    EAGLE_UPLOAD_USER, EAGLE_UPLOAD_PASSWORD   the same Basic Auth eagle_bypass.py uses

Usage:  python3 t5_upload.py [--once] [--dry-run] [-v]
"""

import argparse
import base64
import csv
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request

EVENTS = os.environ.get("T5_EVENTS", "/var/lib/t5-runtime/events.csv")
LAST_SEEN = os.environ.get("T5_LAST_SEEN", "/run/t5-runtime/last_seen")
UPLOAD_URL = os.environ.get("T5_UPLOAD_URL", "https://linknode-eagle-monitor.fly.dev/thermostat")
UPLOAD_USER = os.environ.get("EAGLE_UPLOAD_USER", "eagle")
UPLOAD_PASS = os.environ.get("EAGLE_UPLOAD_PASSWORD", "")
POLL_SECS = int(os.environ.get("T5_UPLOAD_POLL_SECS", "20"))
HEARTBEAT_SECS = int(os.environ.get("T5_UPLOAD_HEARTBEAT_SECS", "60"))
RETRY_SECS = int(os.environ.get("T5_UPLOAD_RETRY_SECS", "60"))
BATCH = 500
TIMEOUT = 20
USER_AGENT = "t5-upload/1.0"

log = logging.getLogger("t5-upload")


def _value(text, cast):
    if text is None or text == "":
        return None
    return cast(float(text))


class EventFile:
    """Reads events.csv a piece at a time: each call to read() returns the rows added
    since the last one, as dicts ready to post, with strictly increasing times."""

    def __init__(self, path):
        self.path = path
        self.rewind()

    def rewind(self):
        self.offset = 0
        self.header = None
        self.last_ms = 0

    def read(self):
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return []
        if size < self.offset:  # replaced by a shorter file: start again
            self.rewind()
        with open(self.path, "rb") as fp:
            fp.seek(self.offset)
            data = fp.read()
        end = data.rfind(b"\n") + 1  # a row still being written waits for its newline
        self.offset += end
        rows = []
        for fields in csv.reader(data[:end].decode("utf-8", "replace").splitlines()):
            if self.header is None:
                self.header = fields
                continue
            raw = dict(zip(self.header, fields))
            try:
                ms = max(round(float(raw["epoch"]) * 1000), self.last_ms + 1)
                row = {
                    "epoch": ms / 1000,
                    "event": raw["event"],
                    "active": _value(raw.get("active"), int),
                    "mode": _value(raw.get("mode"), int),
                    "temp": _value(raw.get("temp"), float),
                    "target": _value(raw.get("target"), float),
                }
            except (KeyError, ValueError):
                log.warning("skipping a row that does not parse: %r", fields)
                continue
            self.last_ms = ms
            rows.append(row)
        return rows


def last_seen():
    """Epoch seconds of the logger's last good read, or None."""
    try:
        with open(LAST_SEEN, encoding="utf-8") as fp:
            return float(fp.read())
    except (OSError, ValueError):
        return None


def post(events, seen):
    """POST a batch. Returns (status, reply): the HTTP status (0 when the request did
    not complete) and the decoded JSON reply, or {} when there was none."""
    token = base64.b64encode(f"{UPLOAD_USER}:{UPLOAD_PASS}".encode()).decode()
    req = urllib.request.Request(
        UPLOAD_URL,
        data=json.dumps({"last_seen": seen, "events": events}).encode(),
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json",
                 "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.debug("post failed: %s", type(e).__name__)
        return 0, {}


class Uploader:
    def __init__(self, path=None):
        self.file = EventFile(path or EVENTS)
        self.pending = []
        self.mark = None       # epoch of the newest row the service holds; None until asked
        self.failing = False
        self.last_post = 0.0   # monotonic time of the last post that was answered

    def _answered(self, status, reply, sent):
        """Take a reply into account. True when the post was accepted."""
        if status == 200:
            latest = reply.get("latest_epoch") or 0.0
            before = reply.get("previous_epoch") or 0.0
            if self.mark is not None and before < self.mark - 0.0005:
                log.warning("the service holds older rows than before; reading the file again")
                self.file.rewind()
                self.pending = []
                latest = before  # everything after what it held is sent, this batch included
            self.mark = latest
            self.pending = [row for row in self.pending if row["epoch"] > latest + 0.0005]
            if self.failing:
                log.info("the service is answering again")
            self.failing = False
            self.last_post = time.monotonic()
            return True
        if status == 400 and sent:
            # The service will never take this batch: drop it and carry on
            log.error("the service refused %d rows (%s); dropped", len(sent), reply.get("error"))
            self.pending = self.pending[len(sent):]
            return False
        if not self.failing:
            log.warning("upload failed (HTTP %s); will keep trying", status or "none")
        self.failing = True
        return False

    def cycle(self):
        """Read what is new and post it. Returns the number of rows the service took."""
        if self.mark is None:
            status, reply = post([], last_seen())
            if not self._answered(status, reply, []):
                return 0
        self.pending += [row for row in self.file.read() if row["epoch"] > self.mark + 0.0005]
        taken = 0
        while self.pending or time.monotonic() - self.last_post >= HEARTBEAT_SECS:
            batch = self.pending[:BATCH]
            status, reply = post(batch, last_seen())
            if not self._answered(status, reply, batch):
                break
            taken += len(batch)
            if batch:
                log.info("shipped %d rows", len(batch))
            else:
                log.debug("posted the last-read time")
        return taken


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--dry-run", action="store_true", help="read the files and say what is there; send nothing")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")

    if args.dry_run:
        rows = EventFile(EVENTS).read()
        print(f"{len(rows)} rows in {EVENTS}; last read {last_seen()}")
        if rows:
            print("newest:", json.dumps(rows[-1]))
        return 0
    if not UPLOAD_PASS:
        log.error("EAGLE_UPLOAD_PASSWORD is not set")
        return 2

    uploader = Uploader()
    if args.once:
        uploader.cycle()
        return 1 if uploader.failing or uploader.mark is None else 0
    log.info("watching %s, posting to %s", EVENTS, UPLOAD_URL)
    while True:
        uploader.cycle()
        time.sleep(RETRY_SECS if uploader.failing else POLL_SECS)


if __name__ == "__main__":
    sys.exit(main())
