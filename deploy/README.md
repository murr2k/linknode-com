# Deploying the Eagle-200 local-API bypass

`scripts/eagle_bypass.py` reads the Eagle's meter over the LAN and forwards it to
our Fly `/eagle` endpoint as synthetic Rainforest XML, but only while the real
cloud path is stale: a hot standby that fills gaps without duplicating data.

It must run on a host that can reach the Eagle (`10.0.0.222`); Fly cannot. The
always-on home is the Raspberry Pi, run under systemd.

The script is a single, standard-library-only file, so there is no repo to clone
and nothing to `pip install` on the Pi. The live deployment is exactly the
single-file install below: the script at `/opt/eagle-bypass/eagle_bypass.py`,
secrets at `/etc/eagle-bypass.env`, and the unit from this directory.

## Install on the Pi

```sh
# 1. Copy the two files onto the Pi from a machine that has this repo checked out.
#    (git isn't required on the Pi.)
scp scripts/eagle_bypass.py       pi@<pi-ip>:/tmp/
scp deploy/eagle-bypass.service   pi@<pi-ip>:/tmp/

# --- the rest runs on the Pi (ssh pi@<pi-ip>) ---

# 2. Install the script (owned by root, world-readable, executable).
sudo install -D -m 0755 /tmp/eagle_bypass.py /opt/eagle-bypass/eagle_bypass.py

# 3. Secrets: create the env file root-only, fill it in.
#    (start from deploy/eagle-bypass.env.example, copy it over too if you like)
sudo install -m 0600 /dev/null /etc/eagle-bypass.env
sudoedit /etc/eagle-bypass.env         # set EAGLE_IP, EAGLE_CLOUD_ID,
                                       # EAGLE_INSTALL_CODE, EAGLE_UPLOAD_PASSWORD

# 4. Install and start the service.
sudo install -m 0644 /tmp/eagle-bypass.service /etc/systemd/system/
#    Confirm User / python3 path in the unit match this host.
sudo systemctl daemon-reload
sudo systemctl enable --now eagle-bypass.service

# 5. Watch it.
journalctl -u eagle-bypass.service -f
```

A healthy log alternates between `standby` (cloud fine) and, during an outage,
`ACTIVATING` then `shipped 3/3 messages`. Every `--probe-secs` while active it
pauses one cycle to check whether Rainforest recovered.

## Verify before trusting it

Run one cycle by hand first. This reads the meter and prints the XML without
sending anything:

```sh
set -a; . /etc/eagle-bypass.env; set +a
python3 /opt/eagle-bypass/eagle_bypass.py --dry-run --once -v
```

Then a single real send while the cloud is down (`-v` shows HTTP 200 per message):

```sh
python3 /opt/eagle-bypass/eagle_bypass.py --once -v
```

## Stats

The service keeps counters in RAM and mirrors them to a RAM-backed live file every
cycle, so you can query current state without parsing the journal:

```sh
ssh pi@<pi-ip> cat /run/eagle-bypass/stats.json | jq
```

For a human-readable outage report instead of raw JSON (works against the running
service's live file, or the newest flash copy if it is stopped):

```sh
ssh pi@<pi-ip> python3 /opt/eagle-bypass/eagle_bypass.py --report
```

It prints device uptime %, mean-time-between-outages, an outage-duration histogram,
an hour-of-day sparkline of when the device tends to stall, and a table of the most
recent outages with how many readings the bypass rescued during each.

Counters include cycles, standby vs active, `activations` (how often the device
stalled and the bypass stepped in), ships and per-type message success, `read_failures`
by kind (timeout / 503 / empty), `longest_clean_run_s`, daily buckets, and
`restarts` / `reboots` (the latter only counts real OS reboots, via the kernel boot
id). `flash_saves` counts the hourly checkpoints and is a rough downtime-excluded
running-hours estimate.

Each closed outage is timestamped (from the Pi's NTP-synced clock) with its duration
measured on the monotonic clock, so an NTP step mid-outage cannot distort it. The
log keeps the most recent 100 outages; totals (`outage_count`, `total_outage_s`,
histograms) are cumulative. An outage still open when the service stops is recorded
as `incomplete` on the next start rather than being given an invented duration.

Persistence is wear-conscious: the live file lives on tmpfs (`RuntimeDirectory`,
zero SD writes), while **two** CRC-tagged copies are checkpointed to flash
(`StateDirectory`) once an hour and on graceful stop. On start the service restores
from whichever copy has a valid CRC, so a corrupt write during a power loss can't
lose the counters. Nothing here holds secrets. To read the counters when the service
is stopped:

```sh
sudo -u pi python3 /opt/eagle-bypass/eagle_bypass.py --print-stats
```

## Notes

- **Always-on (current) vs. failover:** the Pi now runs `--force` (always-on),
  because Rainforest removed the Eagle's own cloud uploader (at our request, to cut
  device load), so the Pi is the sole source. If the device ever uploads on its own
  again, drop `--force` and use `--stale-secs 90 --probe-secs 300` to return to
  failover, else you'll get near-duplicate points.
- **What "device health" means now:** with the cloud uploader gone, the meaningful
  reliability signal is local-API read success (`read_failures` per cycle), i.e.
  whether the Eagle answers the Pi. In `--force` mode the outage log (which keyed off
  cloud staleness) no longer accrues. The other half of the picture is
  `messages_failed` / `messages_sent`: how often the Fly endpoint rejects or fails to
  receive a transmission.
- **Meter (Zigbee) link health.** Each cycle also records the meter's
  `ConnectionStatus` and `LastContact` from `device_list` (`meter_status`,
  `meter_link_pct`, `meter_not_connected`). This is the Eagle-to-meter side, which
  stays healthy even as the cloud/IPC subsystems rot, so it is our best on-device
  signal for how much life the pairing has left. `--report` shows it.
- **Report rate (`--interval`, 30s).** The Eagle natively reports every ~8-10s; we
  poll at 30s on purpose, to avoid roughly 4x the query load on the failing device and
  because the dashboard only flags data as stale after 2 minutes. Kept at 30s even now
  that the Pi is the primary uploader (decided 2026-07-14): nurse the hardware, do not
  stress it. Faster resolution is one `--interval` change away if the tradeoff ever
  shifts.
- **The device flaps.** Its local data-CGI intermittently returns 503; the script
  logs `nothing to ship` and continues. That is expected, not a failure.
- **Uptime heartbeat.** Every `--heartbeat-secs` (default 900s / 15 min), in *any*
  mode including standby, the script POSTs a small `BypassStatus` message carrying
  its own reliability numbers (data-uptime %, device-uptime %, outage counts). The
  collector stashes these for the dashboard's Uptime tile and never writes them to
  the time-series, so this is the one case where the bypass talks to `/eagle` while
  the real cloud path is healthy. It carries no secrets.
- **Secrets:** `/etc/eagle-bypass.env` holds the Install Code (which also exposes
  the Wi-Fi PSK via the local API) and the upload password. Keep it `600`.
