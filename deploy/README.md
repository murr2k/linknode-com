# Deploying the Eagle-200 local-API bypass

`scripts/eagle_bypass.py` reads the Eagle's meter over the LAN and forwards it to
our Fly `/eagle` endpoint as synthetic Rainforest XML, but only while the real
cloud path is stale — a hot standby that fills gaps without duplicating data.

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
#    (start from deploy/eagle-bypass.env.example — copy it over too if you like)
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

Run one cycle by hand first — this reads the meter and prints the XML without
sending anything:

```sh
set -a; . /etc/eagle-bypass.env; set +a
python3 /opt/eagle-bypass/eagle_bypass.py --dry-run --once -v
```

Then a single real send while the cloud is down (`-v` shows HTTP 200 per message):

```sh
python3 /opt/eagle-bypass/eagle_bypass.py --once -v
```

## Notes

- **Failover vs. always-on:** default is failover. Add `--force` to the
  `ExecStart` line to ship every cycle regardless (only if you've disabled
  Rainforest's uploader, else you'll get near-duplicate points).
- **The device flaps.** Its local data-CGI intermittently returns 503; the script
  logs `nothing to ship` and continues. That is expected, not a failure.
- **Secrets:** `/etc/eagle-bypass.env` holds the Install Code (which also exposes
  the Wi-Fi PSK via the local API) and the upload password. Keep it `600`.
