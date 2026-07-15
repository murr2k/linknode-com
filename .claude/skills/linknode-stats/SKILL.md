---
name: linknode-stats
description: >-
  Query and interpret linknode.com energy-monitor health from its two stat sources: the Raspberry
  Pi bypass uploader (pi@10.0.0.139) and the Fly ingest service's /api/stats endpoint. Use when
  checking whether data is flowing, reading uptime/outage/meter-link counters, or diagnosing
  staleness, so a session does not re-derive the commands or guess JSON field names.
---

# Linknode stats: querying and interpreting

Two independent sources report health. Check both; they answer different questions.

| Source | Answers | Where |
|---|---|---|
| **Pi bypass** (`pi@10.0.0.139`) | Is the Pi reading the Eagle and shipping? Read/send failure rates, meter link, outages | `/run/eagle-bypass/stats.json`, or the `--report` / `--print-stats` CLI |
| **Fly `/api/stats`** | Is fresh data reaching the site? What the dashboard shows | `https://linknode-eagle-monitor.fly.dev/api/stats` |

## Golden rule: never guess field names

The single most common mistake here is probing a key that does not exist at the level you query and
reading the resulting `None` as a real null value. `dict.get('typo')` returns `None` silently, so a
wrong name is indistinguishable from a present-but-null field.

- **Dump the keys first**, then read specific ones:
  `curl -s .../api/stats | python -c "import sys,json; d=json.load(sys.stdin); print(list(d))"`
- **Prefer bracket access** (`d['last_update']`) which raises `KeyError` on a typo, over `.get()`
  which hides it.
- Two names that are easy to get wrong (see the key map below): the "last data received" timestamp is
  **`last_update`** at the root (not `last_data_received`, which only exists nested under
  `monitor_stats`); the heartbeat time is **`bypass_status.updated_at`** (there is no `received_at`).

---

## Source 1: the Pi bypass (`pi@10.0.0.139`)

`scripts/eagle_bypass.py` runs under systemd as `eagle-bypass.service` and keeps counters in RAM,
mirrored to a tmpfs live file every cycle and checkpointed to flash hourly. See `deploy/README.md`
for the deployment.

```bash
# Live counters (raw JSON, updated every cycle; tmpfs, zero SD wear)
ssh pi@10.0.0.139 cat /run/eagle-bypass/stats.json | python -m json.tool

# Human-readable reliability report (uptime %, outage histogram, meter link, service info)
ssh pi@10.0.0.139 python3 /opt/eagle-bypass/eagle_bypass.py --report

# JSON snapshot when the service is stopped (reads the newest valid flash checkpoint)
ssh pi@10.0.0.139 sudo -u pi python3 /opt/eagle-bypass/eagle_bypass.py --print-stats

# Service state / live logs
ssh pi@10.0.0.139 systemctl status eagle-bypass
ssh pi@10.0.0.139 journalctl -u eagle-bypass -f
```

Flash checkpoints (survive reboot): `/var/lib/eagle-bypass/stats.a.json` + `.b.json` (two CRC-tagged
copies; restore picks whichever CRC is valid).

### Pi field reference (from the live JSON)

| Field | Meaning |
|---|---|
| `mode` | `active` (shipping) or `standby` (failover mode, cloud healthy) |
| `cycles` / `ship_cycles` / `standby_cycles` | total poll cycles / cycles that shipped / cycles held in standby |
| `readings_rescued` | cycles whose data was shipped during an outage (in force mode, == `cycles`) |
| `messages_sent` / `messages_ok` / `messages_failed` | XML messages POSTed / accepted / rejected by the Fly endpoint. **`messages_failed` = how often the endpoint fails to accept.** ~3 messages per cycle |
| `read_failures` `{empty, http_503, http_other, timeout}` | **how often the Eagle fails to answer the Pi's local-API read**, by kind |
| `meter_status` / `meter_link_pct` / `meter_link_checks` / `meter_not_connected` | the meter (HAN) link: `Connected`, % Connected over N checks, count of non-Connected |
| `meter_last_contact` | Eagle's last meter-contact time (hex epoch, from the local API) |
| `activations` / `outage_count` / `total_outage_s` / `worst_outage_s` | failover activations and the outage log (does not accrue in force mode) |
| `outages_by_hour[24]` / `duration_buckets[5]` | outage histograms (hour-of-day; duration buckets) |
| `longest_clean_run_s` / `current_clean_run_s` / `clean_run_since` | longest and current uninterrupted-shipping streaks |
| `device_availability_pct` | Eagle-itself uptime: `(observed_s - total_outage_s)/observed_s` |
| `data_availability_pct` | fraction of cycles whose data reached the site |
| `observed_s` | derived watched wall time (`cycles x interval`), not an accumulator |
| `restarts` / `reboots` / `boot_id` | process restarts vs **real OS reboots** (distinguished by kernel boot id) |
| `flash_saves` / `approx_running_h` | hourly checkpoint count / rough downtime-excluded running hours |

### Healthy Pi baseline (force / always-on mode, the current default)

- `mode: active`, `standby_cycles: 0`, `activations: 0` (Pi is the sole uploader).
- `readings_rescued == cycles`.
- `read_failures` all `0` (the Eagle is answering) and `messages_ok == messages_sent`,
  `messages_failed: 0` (the endpoint is accepting).
- `meter_status: "Connected"`, `meter_link_pct: 100.0`.
- `device_availability_pct` and `data_availability_pct` near `100.0`; `reboots: 0`;
  `longest_clean_run_s` large and growing.

Force mode is the script default now; `--failover` opts back into the stale/probe behavior. In force
mode the outage log stops accruing, so the meaningful failure signals become `read_failures`
(Eagle answering the Pi) and `messages_failed` (endpoint accepting the Pi).

---

## Source 2: the Fly ingest service (`/api/stats`)

```bash
curl -s https://linknode-eagle-monitor.fly.dev/api/stats | python -m json.tool
curl -s https://linknode-eagle-monitor.fly.dev/health | python -m json.tool
# Ops: fly status -a linknode-eagle-monitor ; fly logs -a linknode-eagle-monitor   (region ord)
```

### Key map (what to read, and the aliases that trip people up)

| You want | Read this key | Note |
|---|---|---|
| Timestamp of last real meter data | **`last_update`** (root) | also at `monitor_stats.last_data_received`; there is **no** root `last_data_received` |
| Last bypass heartbeat time | **`bypass_status.updated_at`** | **not** `received_at` (that key does not exist) |
| Live uptime tile values | `bypass_status.data_uptime_pct` / `.device_uptime_pct` | shipped by the Pi heartbeat every 15 min |
| Dashboard "Samples Today" (received/expected, rolling 24h) | `samples_24h.received` / `.expected` | the completeness gauge the dashboard shows; `.interval_s` and `.window_hours` included. `null` if the DB is unreachable |
| Data points stored today (legacy counter) | `packets_today` (root) | successful InfluxDB writes since midnight UTC; still emitted but the dashboard now uses `samples_24h` |
| Current power (W) | `current_power` (root) | last power reading |
| Gap between last two points (ms) | `packet_interval_ms` (root) | |

Root keys: `active_viewers, avg_24h, billing_period, bypass_status, cost_24h, current_power,
last_update, max_24h, min_24h, monitor_stats, packet_interval_ms, packets_today, price_per_kwh,
samples_24h`.

`monitor_stats` (the ingest service's internal counters) keys: `bypass_status, failed_writes,
filtered_requests, last_data_received, last_power_reading, packet_interval_ms, packets_today,
packets_today_date, previous_data_received, start_time, successful_writes, total_requests`.

`bypass_status` keys (the Pi heartbeat, seconds spelled out): `data_uptime_pct, device_uptime_pct,
observed_seconds, outage_count, readings_rescued, total_outage_seconds, updated_at,
worst_outage_seconds, interval_s`. (The `*_seconds` names are the heartbeat XML's renames of the Pi's
internal `*_s` fields. `interval_s` is the Pi's report cadence, used to size `samples_24h.expected`.)

`/health`: `{influxdb_connected, status, uptime_seconds}`.

### Healthy Fly baseline

- `last_update` within ~1 minute of now (30s poll cadence; the dashboard flags data stale only after
  2 minutes, at which point the Pushover outage alert fires).
- `packets_today` climbing.
- `bypass_status.data_uptime_pct` / `.device_uptime_pct` near `100.0`, and
  `bypass_status.updated_at` within the last ~15 minutes (the heartbeat interval).
- `/health` -> `status: healthy`, `influxdb_connected: true`.

---

## Cross-checks and interpretation

- **`packets_today` < Pi `messages_sent`, and that is expected.** The Pi ships ~3 messages per cycle,
  but only data-bearing messages become InfluxDB writes; metadata-only messages (DeviceInfo,
  BillingPeriodList, etc.) are acknowledged without a write. So `packets_today` counts stored points,
  not raw messages.
- **`samples_24h` is the completeness gauge the dashboard shows ("Samples Today").** `received` counts
  stored `power_w` (InstantaneousDemand) points over a **rolling 24h** window (one per Pi cycle);
  `expected` is `window / interval_s` (2880 at the 30s rate). `interval_s` comes from the Pi's
  heartbeat, falling back to the `SAMPLE_INTERVAL_SEC` env then 30, so it auto-adjusts if the report
  rate changes. `received` is clamped to `expected`, so e.g. `2878/2880` means two readings were missed
  in the last 24h. Unlike `packets_today`, it is a sliding window, not a midnight-UTC reset.
- **The heartbeat is deliberately out-of-band.** The collector stashes `bypass_status` but does
  **not** touch `last_update` / `last_data_received`, so a heartbeat cannot masquerade as fresh meter
  data and suppress a real staleness alert. Judge freshness by `last_update`, judge the Pi's
  self-reported uptime by `bypass_status`.
- **Diagnosing "site looks stale":** if `last_update` is old but the Pi shows `messages_failed: 0`
  and low `read_failures`, suspect the Fly side (endpoint/InfluxDB). If the Pi shows rising
  `read_failures`, the Eagle stopped answering. If `messages_failed` is rising, the endpoint is
  rejecting. `bypass_status.updated_at` much older than 15 min means the Pi itself stopped shipping.
- **Meter/HAN health lives only on the Pi** (`meter_status`, `meter_link_pct`); the Fly side has no
  view of it. A `Connected` meter link with a failing host is the known Eagle failure signature.

## Related

- `deploy/README.md` - the bypass deployment and stats persistence design.
- `docs/eagle-200-hardware-notes.md`, `docs/eagle-200-transplant-plan.md` - the failing-Eagle context
  and the radio-transplant plan.
- `scripts/eagle_bypass.py` - the uploader; `--report`, `--print-stats`, `--failover` flags.
