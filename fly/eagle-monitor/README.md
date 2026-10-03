# Eagle-200 XML Monitor for Fly.io

This service receives Eagle-200 XML readings (posted by the Raspberry Pi uploader) and
stores them in SQLite on the Fly volume. It also serves the API behind the linknode.com
gauge and dashboard, and raises outage alerts.

## Features

- Accepts XML POST requests at `/eagle` endpoint (HTTP Basic auth)
- Parses Eagle-200 XML format for power, energy and price data
- Stores readings in SQLite (`/data/energy.db`, `store.py`) with the meter's timestamps
- Statistics endpoint at `/api/stats` and dashboard endpoint at `/api/dashboard`
- Live power stream (Server-Sent Events) at `/api/stream`
- Health check endpoint at `/health`, telemetry freshness at `/health/data`
- Data staleness monitor with Slack and Pushover alerts
- Minimal resource usage (one shared-cpu-1x machine, 256MB RAM)

## Configuration

The Pi uploader (`scripts/eagle_bypass.py`, see `deploy/README.md`) posts to:
```
https://linknode-eagle-monitor.fly.dev/eagle
```
with Basic auth user `eagle` and the `EAGLE_PASSWORD` secret as the password
(`EAGLE_UPLOAD_PASSWORD` on the Pi).

## Deployment

1. Run the unit tests:
   ```bash
   python -m unittest discover -s fly/eagle-monitor -p "test_*.py"
   ```

2. Deploy the monitor (CI does both steps on pushes to `main` touching
   `fly/eagle-monitor/**`):
   ```bash
   cd fly/eagle-monitor
   flyctl deploy --remote-only
   ```

Run exactly one machine: the database is on the machine's `eagle_data` volume, so a
second machine would have its own separate database.

## API Endpoints

- `POST /eagle` - Receives XML data (readings and the Pi's `BypassStatus` heartbeat)
- `GET /` - Service information
- `GET /api/stats` - Current power, 24h min/max/avg and cost, `reads_24h`,
  `bypass_status`, billing period with BC Hydro tiered cost (`?hours=1` to `720`)
- `GET /api/dashboard?range=24h` - Chart series and panel values; `range` is `1h`,
  `6h`, `24h`, `7d` or `30d` (15 s cache)
- `GET /api/stream` - Server-Sent Events, one event per stored power reading
- `GET /health` - `{status, db_ok, uptime_seconds}`; 503 if the database is unavailable
- `GET /health/data` - Telemetry freshness by the age of the newest power reading: 200
  `fresh`; 503 `stale`, `no_data` or `unavailable` (see `docs/ALERTING.md`)
- `GET /api/security/stats` - Security stats (needs `ADMIN_API_KEY`)

## Environment Variables

- `DB_PATH` - SQLite file (default: `/data/energy.db`)
- `MONITOR_STATE_FILE` - Alert state (set to `/data/monitor_state.json` in `fly.toml`)
- `RETENTION_DAYS` - Readings older than this are pruned daily (default: 1825, 5 years)
- `EAGLE_USERNAME` - Basic auth user (default: `eagle`)
- `EAGLE_PASSWORD` - Basic auth password (set as secret)
- `SLACK_WEBHOOK_URL` - Outage and recovery alerts (set as secret)
- `PUSHOVER_API_TOKEN`, `PUSHOVER_USER_KEY` - Emergency siren on outage (set as secrets)
- `STALE_THRESHOLD_MINUTES` - Age in minutes of the newest power reading, by its own
  timestamp, past which the feed is stale (default: 5). Must be an integer: on `2.5` or
  `5.0` the service does not start. Used by both `/health/data` and the alarm (see
  `docs/ALERTING.md`)
- `EAGLE_API_KEY` - Optional API key for the read endpoints (not set: they are public)
- `ADMIN_API_KEY` - Optional key for `/api/security/stats` (not set)

## Data Format

The monitor handles several types of Eagle-200 messages:

1. **InstantaneousDemand** - Current power consumption in watts
2. **CurrentSummationDelivered** - Total energy consumed (and exported) in kWh
3. **PriceCluster** - Current electricity rate from utility
4. **MessageCluster** - Text messages from utility
5. **TimeCluster** - Time synchronization (not stored)
6. **NetworkInfo** - Network status (link strength)
7. **BypassStatus** - The Pi uploader's reliability heartbeat (not Eagle telemetry)

The Pi sends the first three every cycle (~33 s) and `BypassStatus` every 15 minutes.

Data is stored in SQLite (`store.py`):
- `readings(field_id, ts_ms, value)`, primary key `(field_id, ts_ms)`, `WITHOUT ROWID`.
  Field ids: 1 `power_w`, 2 `energy_delivered_kwh`, 3 `energy_received_kwh`,
  4 `price_per_kwh`
- `text_readings(field, ts_ms, value)` for `link_strength` and `message_text`
- `meta(key, value)`: `created_ms` (go-live) and `bypass_status` (last Pi heartbeat,
  restored on restart)

Writes are upserts: the same (field, ts) written again overwrites the value. The Pi
stamps each demand and summation reading with the meter's `LastContact` time, so a stale
re-read lands on the existing row, and `reads_24h` counts only fresh reads. The price
reading always carries the Pi's clock, so it adds a row every cycle. A reading with no
usable `LastContact` falls back to the Pi's or the server's clock and counts as fresh
(see `docs/ALERTING.md`). WAL mode, one short-lived connection per operation.

The store holds 30 days backfilled from InfluxDB (from 2026-08-27 23:50 UTC) plus
everything written live since go-live (2026-09-26 23:50:02 UTC). Older InfluxDB history
was intentionally discarded.

## Data Flow

The Eagle no longer uploads anything itself; Rainforest removed its cloud uploader.
The Pi reads the Eagle's local API and posts Rainforest-style XML directly:

```
Eagle-200 (local API, home LAN)
    → Raspberry Pi (eagle-bypass.service, every ~33 s)
        → Linknode /eagle endpoint (Fly.io)
            → SQLite /data/energy.db
```

### Historical: Rainforest Cloud Repackaging

Until the cloud uploader was removed, data came through Rainforest's cloud, which
repackaged the XML before forwarding it to upload destinations:

```
Eagle-200 (Cloud ID: 00a046)
    → Rainforest Cloud (rainforestautomation.com)
        → Repackaged XML forwarded to configured upload destinations
            → Linknode /eagle endpoint
```

**Important:** Rainforest's cloud repackaged the XML data before forwarding it. The
`DeviceMacId` in the forwarded XML was NOT the Eagle's Cloud ID, but rather identifiers
assigned by Rainforest's internal systems.

### Observed Device MAC Schema

Rainforest forwarded data using two different DeviceMacId values, but **only one
reported meter data**:

| Device MAC | Message Types | Activity |
|------------|---------------|----------|
| `d8d5b9000000ef68` | message_cluster | **Dormant** - Only forwards utility text messages (~450/day) |
| `d8d5b9000000ef69` | instantaneous_demand, current_summation_delivered, message_cluster, price_cluster | **Active** - Primary data source |

**Observed report rates (ef69, Rainforest path):**

| Message Type | Rate | Count/24h |
|--------------|------|-----------|
| instantaneous_demand (power_w) | ~1 every 9 seconds | ~9,700 |
| current_summation_delivered (energy_kwh) | ~1 every 27 seconds | ~3,200 |
| price_cluster (price_per_kwh) | ~1 every 65 seconds | ~1,300 |

Both device MACs read from the same utility meter (`meter_mac: 0007810000a4505c`).
The service drops `ef68` messages outright (`IGNORED_DEVICE_MACS` in `app.py`), and the
Pi tags everything it sends with `ef69`.

### Why Two Device MACs?

Per the [EAGLE-200 Local API Manual](https://rainforestautomation.com), the Eagle-200 contains
**two independent Zigbee radios** (see page 10):

1. **Utility HAN Radio** - Connects to the smart meter via Zigbee SEP protocol
2. **Control Network Radio** - Acts as coordinator for subdevices (smart plugs, thermostats)

Each radio has its own MAC address. When Rainforest's cloud forwarded XML data, the
`<DeviceMacId>` field reflected which internal radio handled the data:

| Identifier | MAC Address | Purpose | Status |
|------------|-------------|---------|--------|
| Cloud ID (Ethernet) | `d8d5b9000000a046` | Device identification, Local API auth | - |
| Zigbee Radio 1 (HAN) | `d8d5b9000000ef68` | Utility HAN - meter communication | Dormant (messages only) |
| Zigbee Radio 2 (Control) | `d8d5b9000000ef69` | Control Network - subdevice control | **Active** (all meter data) |

In practice, `ef69` (Control Network radio) handled all meter data forwarding, while
`ef68` (HAN radio) only forwarded utility text messages. Because of the filter, all
stored power/energy data comes from a single source and needs no aggregation.

### Query Considerations

Each field has exactly one source, so queries need no device filtering:

```sql
-- Current power
SELECT ts_ms, value FROM readings
WHERE field_id = 1 ORDER BY ts_ms DESC LIMIT 1;

-- Current electricity rate
SELECT value FROM readings
WHERE field_id = 4 ORDER BY ts_ms DESC LIMIT 1;
```

Energy over a range is the trapezoidal integral of `power_w` (`Store.integral_wh` in
`store.py`), which bridges gaps the way Flux `integral(unit: 1h)` did.
