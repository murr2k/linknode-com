# 2026-10-02: Installing the outside watchdog on the Pi

Written by Claude (Claude Code session on the Surrey desktop) at Murray's request, right
after the work. Times are Pacific; the Pi's clock read 22:50 to 22:57 PDT on Oct 2
(05:50 to 05:57 UTC on Oct 3).

## The task

Install the watchdog from commit `c125c9c` on the Raspberry Pi (`pi@10.0.0.139`, hostname
`eagle-bypass`, a Pi 3 Model B Rev 1.2) by following the "Watchdog" section of
`deploy/README.md`: run `--dry-run`, then `--test-alert`, then enable
`linknode-watchdog.timer`.

The watchdog (`scripts/linknode_watchdog.py`) is the outside half of the outage alerting.
The ingest service on Fly alerts when telemetry stops, but it cannot report its own death,
so the Pi checks it, the site and the stats API every two minutes and sends a Pushover
siren after three consecutive failures.

## What I did

1. Read the README section, both unit files, the env example and the whole script before
   running anything. These arrived in a `git pull` from outside my session, so I had not
   seen them. The script is standard library only: three GET requests per pass, a Pushover
   POST when an alert is due, and one small state file.
2. Preflight from the desktop: production answers `/health/data` (status `fresh`), the site
   carries the `id="power-chart"` marker the site check looks for, and `/api/stats` returns
   the CORS header for `https://linknode.com`. On the Pi: Python 3.13.5 at
   `/usr/bin/python3`, passwordless sudo, `eagle-bypass` active, no watchdog installed.
3. Copied the four files with `scp` and installed them with the README's `install`
   commands, then `systemctl daemon-reload`.
4. Found and fixed Windows line endings in all four installed files (see Observations).
5. `--dry-run`: `ingest: ok`, `site: ok`, `api: ok`, exit 0, no state written.
6. Filled in `/etc/linknode-watchdog.env` with the two Pushover values (see Observations).
7. `--test-alert`: `test alert sent`, exit 0.
8. `systemctl enable --now linknode-watchdog.timer`. The first pass ran at once (22:52:54),
   as user `pi`, `Result=success`, exit status 0. The second ran at 22:55:09, also clean.
9. Removed the copied files from the Pi's `/tmp`. Confirmed `eagle-bypass` was still active
   and shipping.

## Observations

**1. Files copied from this Windows checkout arrive with CRLF.** Git on this desktop
checks files out with `\r\n`. `scp` copies bytes, so on the Pi the script had 224 lines
ending in `\r`, the service 30, the timer 10 and the env file 14. I noticed only because I
compared checksums and then counted carriage returns; the install commands themselves
succeeded silently. I converted them in place (`sudo sed -i 's/\r$//' ...`) and then
checked each against the repo's canonical version (`git show HEAD:<path> | sha256sum`):
all four matched, and `systemd-analyze verify` passed. I did not test the broken state, so
I am inferring, not reporting, that systemd would have rejected `User=pi\r` and that a
credential ending in `\r` would have been refused by Pushover. The README's `scp` step
will reproduce this for anyone on a Windows checkout.

**2. The credentials came from Fly, not from typing.** The README says to `sudoedit` the
env file with the same Pushover application token and user key the Fly ingest service
holds as secrets. I read both from the Fly machine (`fly ssh console -C "printenv ..."`)
into shell variables and piped them over SSH into a short script on the Pi that rewrote
the two placeholder lines. The values were never printed; I checked only that each was 30
alphanumeric characters. The file stayed `0600 root:root`.

**3. The timer fires immediately when enabled.** `OnBootSec=3min` had long since elapsed
(the Pi had been up since July 12, almost twelve weeks), so enabling the timer started the
first pass straight away.
After that it follows `OnUnitActiveSec=2min`: passes at 22:52:54 and 22:55:09, the next
due 22:57:09.

**4. A healthy pass writes nothing to the SD card, as designed.** The first pass created
`/var/lib/linknode-watchdog/state.json` (121 bytes, all three checks at `fails: 0`,
`alerted: false`) because the state changed from empty. After the second pass the file's
modification time was still 22:52:56. The journal holds only systemd's start and finish
lines; the script itself logs nothing while everything is healthy.

**5. It is cheap on a Pi 3.** Each pass consumed about 1.18 s of CPU (two samples: 1.179 s
and 1.175 s), once every 120 s, so roughly 1% of one core.

**6. The unit's hardening did not get in the way.** With `ProtectSystem=strict`,
`ProtectHome=read-only`, `PrivateTmp=true` and `NoNewPrivileges=true`, the service still
reached the network and wrote its state through `StateDirectory=`.

**7. My own slip with the tests.** I first ran the unit tests as
`python -m unittest scripts/test_linknode_watchdog.py` from the repo root and got an
`ImportError` (the test imports `linknode_watchdog` as a sibling module). Run from
`scripts/`, or the documented way (`python -m unittest discover -s scripts -p
"test_*.py"`), all 9 tests pass. The first result said nothing about the code.

## How the two halves cover each other (my reading of the script, not a test)

| What fails | Who should notice |
|---|---|
| Meter, Eagle, Pi uploader or home internet | The Fly ingest service: telemetry stops arriving |
| Fly ingest service down | Pi watchdog, `ingest` check |
| linknode.com not serving the dashboard | Pi watchdog, `site` check |
| API up but the page cannot read it (CORS, no `current_power`) | Pi watchdog, `api` check |
| Ingest alive but its own stale-data alarm silent for 15 minutes | Pi watchdog, `ingest` backstop |
| The Pi itself down | The Fly side (it is also the uploader). While the Pi is down, nothing watches Fly or the site |
| Home internet down | The Fly side. The watchdog cannot reach Pushover, but it retries: a check is only marked alerted once Pushover accepts the message |
| Pushover unavailable | Nobody |

## What I did not verify

- **Delivery to the phone.** Pushover's API accepted the test message (HTTP 200). I have
  no way to see whether it arrived.
- **The failure path end to end.** Nothing was actually down, so no siren was sent and no
  "recovered" message. That logic is covered by the script's unit tests, not by anything I
  did on the Pi. A deliberate drill (for example, pointing `WATCH_SITE_URL` at a dead
  host in a manual run with a throwaway state directory) would close that gap.
- **Behaviour across a Pi reboot.** The timer is enabled and has `OnBootSec=3min`; I did
  not reboot the Pi to watch it come back.

## Follow-ups worth considering

- Add a `.gitattributes` rule forcing LF for `deploy/*` and `scripts/*.py`, and a one-line
  note in `deploy/README.md`, so the next install from a Windows checkout does not carry
  CRLF onto the Pi. The existing `eagle-bypass` files installed earlier may deserve the
  same check; I did not inspect them.
- Run the failure drill described above once, so the siren has been heard from this path
  before it is needed.

## Corrections (2026-10-03)

Added the next day, after a review of the alerting against the code and the live system.
The entry above is left as written.

- **Observation 1, the CRLF inference, was wrong.** Tested on the Pi (systemd 257): systemd
  strips the carriage return when it reads an `EnvironmentFile`, so a CRLF env file reaches
  the unit clean. The unit-file half (`User=pi\r`) was not tested on the Pi; systemd's
  parser treats `\r\n` as a line ending there too. What does break is the shell: `. /etc/linknode-watchdog.env` keeps the
  `\r` on each value, so the documented `--test-alert` command would have sent credentials
  with a trailing carriage return. Converting the files was still the right call, for that
  reason and not the one I gave.
- **The coverage table's backstop row is too narrow.** "Ingest alive but its own stale-data
  alarm silent for 15 minutes" describes the intent. The code fails the `ingest` check for
  any reading over 15 minutes old, alarm silent or not, so a long telemetry outage with the
  Pi online gets a second siren from the watchdog at about 19 to 22 minutes.
- **The table's home-internet row needs a caveat.** The retry holds only while the check is
  still failing. When the link returns, the watchdog can also send a DOWN for services that
  never went down.
- **The suggested drill trips two checks, not one.** `WATCH_SITE_URL` is also the `Origin`
  the `api` check sends, so pointing it at a dead host fails the `api` check as well.
  Setting `WATCH_SITE_MARKER` to a string the page does not contain fails only the `site`
  check.
- **Observation 4** holds for the script; it is not established for the pass as a whole.
  systemd still journals every pass; on this Pi the journal is kept in RAM
  (`Storage=volatile`). The unit's `PrivateTmp=true` also makes systemd create and remove
  a private directory under `/tmp` and under `/var/tmp` on every pass, and where those two
  are mounted on this Pi was not checked.

The corrected account is in [ALERTING.md](../ALERTING.md).
