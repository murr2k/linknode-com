# Deploying the Eagle-200 local-API bypass

`scripts/eagle_bypass.py` reads the Eagle's meter over the LAN and forwards it to
our Fly `/eagle` endpoint as synthetic Rainforest XML, but only while the real
cloud path is stale — a hot standby that fills gaps without duplicating data.

It must run on a host that can reach the Eagle (`10.0.0.222`); Fly cannot. The
always-on home is the Raspberry Pi, run under systemd.

## Install on the Pi

```sh
# 1. Get the code onto the Pi (adjust the path to taste; the unit assumes /opt).
sudo git clone https://github.com/<you>/linknode-com /opt/linknode-com
# (python3 stdlib only — no pip install needed.)

# 2. Secrets: copy the template, fill it in, lock it down.
sudo cp /opt/linknode-com/deploy/eagle-bypass.env.example /etc/eagle-bypass.env
sudo nano /etc/eagle-bypass.env        # set EAGLE_INSTALL_CODE + EAGLE_UPLOAD_PASSWORD
sudo chmod 600 /etc/eagle-bypass.env

# 3. Install and start the service.
sudo cp /opt/linknode-com/deploy/eagle-bypass.service /etc/systemd/system/
#    Edit the User / WorkingDirectory / python3 path in the unit if they differ.
sudo systemctl daemon-reload
sudo systemctl enable --now eagle-bypass.service

# 4. Watch it.
journalctl -u eagle-bypass.service -f
```

A healthy log alternates between `standby` (cloud fine) and, during an outage,
`ACTIVATING` then `shipped 3/3 messages`. Every `--probe-secs` while active it
pauses one cycle to check whether Rainforest recovered.

## Verify before trusting it

Run one cycle by hand first — this reads the meter and prints the XML without
sending anything:

```sh
cd /opt/linknode-com
set -a; . /etc/eagle-bypass.env; set +a
python3 scripts/eagle_bypass.py --dry-run --once -v
```

Then a single real send while the cloud is down (`-v` shows HTTP 200 per message):

```sh
python3 scripts/eagle_bypass.py --once -v
```

## Notes

- **Failover vs. always-on:** default is failover. Add `--force` to the
  `ExecStart` line to ship every cycle regardless (only if you've disabled
  Rainforest's uploader, else you'll get near-duplicate points).
- **The device flaps.** Its local data-CGI intermittently returns 503; the script
  logs `nothing to ship` and continues. That is expected, not a failure.
- **Secrets:** `/etc/eagle-bypass.env` holds the Install Code (which also exposes
  the Wi-Fi PSK via the local API) and the upload password. Keep it `600`.
