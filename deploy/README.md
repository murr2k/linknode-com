# Deploying the Eagle-200 local-API bypass

`scripts/eagle_bypass.py` reads the Eagle's meter over the LAN and forwards it to
our Fly `/eagle` endpoint as synthetic Rainforest XML, every cycle. It is the only
uploader: the Eagle's own cloud upload was removed. (`--failover` restores the older
hot-standby mode, which ships only while the cloud path is stale; see Notes.)

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

# 3. Secrets: create the env file root-only, fill it in. First install only: the
#    guard keeps a re-run from emptying a file that already holds the credentials.
#    (To start from deploy/eagle-bypass.env.example instead, scp it to /tmp too and
#    install it in place of /dev/null. From a Windows checkout strip its CRLF line endings
#    first: sed -i 's/\r$//' /tmp/eagle-bypass.env.example. systemd accepts them; the
#    shell that reads the file under "Verify before trusting it" does not.)
#    One setting per line, nothing after the value: systemd keeps a trailing
#    "# comment" as part of it.
[ -e /etc/eagle-bypass.env ] || sudo install -m 0600 /dev/null /etc/eagle-bypass.env
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

A healthy log shows `shipped 3/3 messages` every cycle (about every 33 s).
`local read failed ...; nothing to ship` means the Eagle did not answer that cycle.
(In `--failover` mode the log instead alternates between `standby` and, during an
outage, `ACTIVATING` then `shipped 3/3 messages`.)

To update the script later, copy and install only the script (the first `scp` in step 1,
then step 2), then `sudo systemctl restart eagle-bypass.service`: a running service keeps
the old code until it is restarted. If `eagle-bypass.service` changed, copy and install
it too and run `sudo systemctl daemon-reload` before the restart. Leave
`/etc/eagle-bypass.env` alone.

## Verify before trusting it

Run one cycle by hand first. This reads the meter and prints the XML without
sending anything (`sudo`, because the env file is root-only):

```sh
sudo sh -c 'set -a; . /etc/eagle-bypass.env; python3 /opt/eagle-bypass/eagle_bypass.py --dry-run --once -v'
```

Then a single real send (`-v` shows HTTP 200 per message). It needs no outage: the
script ships every cycle. It also posts a heartbeat built from that one run's counters,
which replaces the service's on the dashboard until the service's next heartbeat (up to
15 minutes). Where the service is already running, its own log line
`shipped 3/3 messages` is the same proof without that side effect.

```sh
sudo sh -c 'set -a; . /etc/eagle-bypass.env; python3 /opt/eagle-bypass/eagle_bypass.py --once -v'
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

## Watchdog (alerts when Fly or the site is down)

`scripts/linknode_watchdog.py` is the outside half of the outage alerting. The ingest
service on Fly alerts when telemetry stops; it cannot alert when it is itself down, so
the Pi checks it, the site, and the stats API every 2 minutes and sends a Pushover
siren after three consecutive failures. Standard library only, like the bypass. How it
decides, and what it misses, is in [docs/ALERTING.md](../docs/ALERTING.md).

```sh
# From a machine with this repo:
scp scripts/linknode_watchdog.py deploy/linknode-watchdog.service \
    deploy/linknode-watchdog.timer deploy/linknode-watchdog.env.example pi@<pi-ip>:/tmp/

# --- the rest runs on the Pi ---
# From a Windows checkout the copies have CRLF line endings. systemd and Python accept
# them, but the shell does not when it reads the env file below, so strip them first.
sed -i 's/\r$//' /tmp/linknode_watchdog.py /tmp/linknode-watchdog.service \
    /tmp/linknode-watchdog.timer /tmp/linknode-watchdog.env.example

sudo install -D -m 0755 /tmp/linknode_watchdog.py /opt/linknode-watchdog/linknode_watchdog.py
# First install only: the guard keeps a re-run from replacing the real credentials
# with the example's placeholders.
[ -e /etc/linknode-watchdog.env ] || sudo install -m 0600 /tmp/linknode-watchdog.env.example /etc/linknode-watchdog.env
sudoedit /etc/linknode-watchdog.env    # PUSHOVER_API_TOKEN, PUSHOVER_USER_KEY
sudo install -m 0644 /tmp/linknode-watchdog.service /tmp/linknode-watchdog.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Prove it before enabling: the three checks, then a real (normal-priority) test message
python3 /opt/linknode-watchdog/linknode_watchdog.py --dry-run
sudo sh -c 'set -a; . /etc/linknode-watchdog.env; python3 /opt/linknode-watchdog/linknode_watchdog.py --test-alert'

sudo systemctl enable --now linknode-watchdog.timer
# While healthy this shows only systemd's start and finish lines for each pass; the script
# logs only failures. Add -v to ExecStart to make it log every check.
journalctl -u linknode-watchdog.service -f
```

State (failure counts, which checks have alerted) is in
`/run/linknode-watchdog/state.json`, written only when something changes. `/run` is RAM,
and the unit's temp directories are in RAM too (`PrivateTmp=disconnected`, which needs
systemd 257 or later), so a pass writes nothing to the SD card and a card that has gone
read-only or is full cannot stop the watchdog counting. A reboot clears the counts and
the alerted marks.

The env file also carries the backstop, `WATCH_BACKSTOP_SECS=86400`: the watchdog sends a
siren of its own only when the newest reading is over a day old. It has to stay well above
the Fly service's `STALE_THRESHOLD_MINUTES` (30 minutes), or that siren comes within
minutes of the Fly alarm's.

The test message goes at normal priority, as root, with the env file read by the shell.
It proves the credentials as the shell reads them and the path to the phone. It does not
exercise the siren request, or the env file as systemd reads it: systemd keeps a trailing
`# comment` as part of the value, where the shell drops it. After one of the three
`WATCH_` numbers that makes every pass crash at start. After a `PUSHOVER_` value nothing
crashes, but the siren request carries the comment inside the credential. Pushover answers
an invalid credential with a 4xx, so no siren reaches the phone: the watchdog logs
`pushover send failed` and tries again on each failing pass. So put nothing
after a value in `/etc/linknode-watchdog.env`, and after any edit run one real pass,
check that both credential lines are bare values (the second command must print 2), and
read the backstop back as systemd reads it (the third must print 86400; a line left
commented out prints nothing, and the watchdog then runs on the script's default of 900):

```sh
sudo systemctl start linknode-watchdog.service && echo ok
sudo grep -cE '^PUSHOVER_(API_TOKEN|USER_KEY)=[A-Za-z0-9]{30}$' /etc/linknode-watchdog.env
sudo systemd-run --quiet --wait --pipe -p EnvironmentFile=/etc/linknode-watchdog.env /usr/bin/printenv WATCH_BACKSTOP_SECS
```

To update the watchdog later, copy, strip and install only the script. The next timer
pass runs the new one; nothing needs restarting. If a unit file changed, install it too,
then `sudo systemctl daemon-reload` and `sudo systemctl restart linknode-watchdog.timer`.
After a change to `linknode-watchdog.service`, `systemctl show linknode-watchdog.service -p
PrivateTmpEx` should print `PrivateTmpEx=disconnected`.
Leave `/etc/linknode-watchdog.env` alone.

The watchdog changes only when someone installs it, while a push to `main` deploys the
ingest service and the site within minutes. It judges three replies by their shape:
`/health/data` (a JSON body and, when the reply is not a 200, its `status` and
`reading_age_seconds`), `/api/stats` (a 200, the CORS header, `current_power`) and the
page (the marker `id="power-chart"`). Adding fields is safe. Before a push that renames
or removes any of these, install a watchdog that accepts both the old and the new reply,
or the old one sends a siren for a healthy service.

## Notes

- **Always-on (default) vs. failover:** always-on is now the script's **default**
  (no flag needed), because Rainforest removed the Eagle's own cloud uploader (at our
  request, to cut device load), so the Pi is the sole source. If the device ever
  uploads on its own again, add `--failover` (optionally with `--stale-secs 90
  --probe-secs 300`) to return to failover, else you'll get near-duplicate points.
  (`--force` is still accepted as a redundant no-op for backward compatibility.)
- **What "device health" means now:** with the cloud uploader gone, the meaningful
  reliability signal is local-API read success (`read_failures` per cycle), i.e.
  whether the Eagle answers the Pi. In always-on (force) mode the outage log (which keyed
  off cloud staleness) no longer accrues. The other half of the picture is
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
