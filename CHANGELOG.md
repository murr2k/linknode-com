# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Selectable skins** on the site: a Classic / Scope picker under the page title. Classic is
  the existing look, unchanged and still the default. Scope is a bench-instrument look (flat
  panels on a graticule, phosphor green readouts, amber chart trace, monospace type, CRT
  scanlines, edge vignette and phosphor bloom),
  written as an `html[data-skin="scope"]` override block in `web/public/index.html`. The
  choice is kept in `localStorage` (`linknode-skin`) and applied before first paint;
  `?skin=scope` selects it by URL. Colours the script sets (gauge needle, sample interval,
  chart canvas) now come from CSS variables so each skin can define them
- **Notch skin** (`?skin=notch`), a third choice in the picker, borrowing the visual language
  of Bklit UI (bklit.com): neutral near-black on a dot grid, hairline cards, a cyan chart
  ramp, a notched gauge track, hatched call-out boxes and mono numerals. No Bklit code or
  fonts are used; it is a CSS override block like Scope
- **Bill Forecast chart** on the site: the bill so far at each day of the billing cycle, with
  the least-squares trendline through it carried on to the last day and the projected bill
  written where it ends. The slope is the spend rate in $/day. `GET /api/stats`
  `billing_period` gains `trend` (`points`, `slope_per_day`, `intercept`, `projected_total`)
- `BILLING_NEXT_READ`: the next meter read date printed on the latest bill. The current
  period now ends on that day (Nov 26, 2026, making it 62 days) in place of the nominal
  boundary
- The Sep 29, 2026 bill (914 kWh over 59 days, $130.38) as a second test of the bill
  calculator; the rates were unchanged
- `GET /health/data`: telemetry freshness (200 fresh, 503 stale) by the age of the newest
  meter reading. `/health` is unchanged and stays Fly's service check (Fly stops routing to
  the machine while it fails; it does not restart it)
- **Pi watchdog** (`scripts/linknode_watchdog.py`, `deploy/linknode-watchdog.*`): a systemd
  timer on the Pi that sends a Pushover siren when the ingest service, linknode.com or the
  stats API stops answering, covering the outages the ingest service cannot report itself
- **Frozen-register rule** in the outage alarm: the feed is unhealthy when the meter's
  kWh register has not changed in 2 hours although readings keep arriving. It does not
  trust timestamps, so it catches a frozen reading that arrives stamped as new
- **Daily reminder**: while an outage lasts, a normal-priority Pushover message 24 hours
  after each accepted one
- **Watchdog-silent message**: the ingest service notes when the Pi watchdog last asked
  `/health/data` (published as `monitor_stats.watchdog_last_seen`) and sends a
  normal-priority message when it has been silent for 6 hours while readings keep
  arriving, and another when it calls again

### Changed
- **Alerting retuned for what it is for** (not mission critical: say that the system has
  stopped reporting, so it can be fixed within a day or two). The alarm's threshold goes
  from 5 to 30 minutes (`STALE_THRESHOLD_MINUTES` in `fly.toml`), so a stop shorter than
  that is no longer reported, and the watchdog's backstop from 15 minutes to 24 hours
  (`WATCH_BACKSTOP_SECS` in the Pi's env file), so its second siren comes only for an
  outage still open a day later
- The Pi watchdog keeps its state and its temp directories in RAM
  (`deploy/linknode-watchdog.service`), so a pass writes nothing to the SD card and a
  card gone read-only or full cannot stop it counting. A reboot clears its counts
- Fly connection limits raised from 20 and 25 to 150 and 200, clear of the number of
  pages likely to hold a live stream open; the two inert `restart_limit` lines removed

### Fixed
- The outage siren is sent again on every run until Pushover accepts it. Before, one
  failed request meant the outage was never announced. A 4xx reply holds it off for 24
  hours
- The deploy workflow's rollback can now run: its image capture read `.Tag` from an
  array and failed on every run. `--yes` is off the rollback's deploy line, and the job
  timeout is 30 minutes. The rollback step itself has still never run
- `/api/stats` reports `current_power` from the store when nothing has been posted since
  the process started, so a restart during a telemetry outage no longer makes the
  watchdog report the stats API as down
- A failed Slack send no longer writes the webhook URL to the log
- `test_stats_shape_and_values` runs on a fixed clock. It failed for the first 40
  minutes of each billing period, which would have blocked a CI deploy
- The outage alarm now goes by the newest reading's own time, not the arrival time of the
  last POST, so it fires when the Eagle loses the meter but keeps answering the Pi with a
  frozen reading, provided the Eagle's `LastContact` stays at the last real contact
  (assumed, not captured on the device; see `docs/ALERTING.md`)
- Alerting documentation corrected against the code and the live system (2026-10-03).
  The review found that Fly does not restart a machine that fails `/health`, that the
  watchdog's backstop (then 15 minutes) sent a second siren on any long telemetry outage
  with the Pi online, and that the deploy workflow's rollback did not arm; the last two
  are changed above. The docs now list what goes unreported, what each
  alert text means and what to do when one arrives (`docs/ALERTING.md`,
  `docs/THEORY_OF_OPERATION.md`, `docs/HEALTH_CHECKS.md`, `deploy/README.md`, the READMEs,
  the `linknode-stats` skill, and a dated Corrections section on the 2026-10-02 journal
  entry). The same corrections are made on the site's Technology Stack panel
  (`web/public/index.html`) and in two docstrings in `fly/eagle-monitor/app.py`.
  `deploy/linknode-watchdog.env.example` and `deploy/eagle-bypass.env.example` no longer
  put comments after values, which systemd would have read as part of them

## [2.0.0] - 2026-09-27

### Changed
- **Infrastructure consolidated from four Fly.io apps to one (2026-09-26/27)**, taking
  hosting from about $13.10 to about $2.09 a month
  - The one remaining machine and its volume moved from `ord` (1.25x regional price markup)
    to `iad` (1.0x), from $2.58 to $2.09 a month
  - Readings are stored in SQLite (`fly/eagle-monitor/store.py`) on the new `eagle_data`
    Fly volume (1GB, daily snapshots kept 14 days) instead of InfluxDB. Writing the same
    (field, timestamp) again overwrites, as InfluxDB did, so `reads_24h` still counts only
    fresh reads. 30 days of history were imported from InfluxDB and checked against it
    (count/min/max/mean and the energy integral: no differences); older history was retired
  - New `GET /api/dashboard?range=1h|6h|24h|7d|30d` serves the chart series and the
    retired Grafana dashboard's stat panels (trapezoid energy integral, cost estimate)
  - The site moved from nginx on Fly (`linknode-web`) to a Cloudflare Worker serving static
    assets (`web/`, `web/wrangler.jsonc`, deployed by `deploy-web.yml`); linknode.com and www
    are Worker routes
  - The Grafana iframe is replaced by a native uPlot chart and eight stat tiles with a
    1h/6h/24h/7d/30d range picker; `energy.linknode.com` redirects (301) to
    `https://linknode.com/#energy-dashboard`
  - The page's security headers, including a CSP, now come from `web/public/_headers`.
    nginx never applied its CSP to `/` (add_header does not inherit into location blocks),
    so this is the first CSP the page has actually carried
  - Cloudflare Rocket Loader turned off for the zone (it conflicts with the CSP)
  - `deploy-fly.yml` deploys only eagle-monitor and runs its unit tests first

### Removed
- Fly apps `linknode-web`, `linknode-grafana` and `linknode-influxdb`, with their volumes and
  Fly certificates; `fly/grafana/` and `fly/influxdb/`; the `influxdb-client` dependency and
  `INFLUXDB_*` configuration; the `influxdb_connected` field of `/health` (use `db_ok`)
- DNS records pointing at the retired Fly hostnames (now proxied `AAAA 100::`
  placeholders) and the Fly certificate-validation records

### Added
- **BC Hydro bill calculator.** The ingest service estimates the current bill from the stored
  readings, built line by line like BC Hydro's residential tiered bill (rate schedule 1101):
  basic charge, Tier 1/Tier 2 energy with the 22.1918 kWh/day threshold prorated over the
  period, deferral account rate rider, regional transit levy and GST, each rounded to the cent.
  Verified against the Jul 30, 2026 bill ($123.75), which `test_api.TestBilling` reproduces
  exactly
  - "This Bill So Far" tile on linknode.com: running total including GST, day of the period
    and kWh used, with the bill lines on hover
  - `GET /api/stats` `billing_period` gains `next_start` and `cycle_days`; its `tiered_cost`
    gains `rider`, `transit_levy`, `subtotal` and `gst`, and `total_cost` is now the amount due
  - Two-month billing cycle (periods start in odd months) counted in Vancouver time, using the
    pinned `tzdata` package (BC is on permanent UTC-7 from 2026); `BILLING_PERIOD_START` pins an
    exact start from a bill
  - Every rate and bill line is a setting with a current default; see README "Bill Calculator"
- Eagle-200 local-API bypass: a hot-standby failover uploader that keeps the data
  pipeline alive through the meter's hardware faults (`scripts/eagle_bypass.py`, `deploy/`)
  - Polls the Eagle's LAN REST API and forwards synthetic Rainforest XML to the Fly
    `/eagle` endpoint only while the real cloud path is stale, filling gaps without
    duplicating data
  - Runs as a systemd service on a Raspberry Pi on the home network (the one host that
    can reach the meter; Fly cannot). See `deploy/README.md`
  - Single standard-library-only file, so there is nothing to clone or `pip install`
    on the Pi
- Persistent reliability statistics for the bypass
  - Counters kept in RAM, mirrored to a tmpfs live file each cycle for querying
    (`/run/eagle-bypass/stats.json`, zero SD wear), and checkpointed hourly to two
    CRC-tagged flash copies that survive reboots (restores from whichever copy is valid)
  - Distinguishes real OS reboots from service restarts via the kernel boot id
- Outage log with reliability analytics for the bypass
  - Timestamps each device outage and records its duration, measured on the monotonic
    clock so an NTP step mid-outage cannot distort it
  - `--report` prints device uptime %, mean-time-between-outages, an outage-duration
    histogram, an hour-of-day sparkline of when the device stalls, and a table of
    recent outages with the readings the bypass rescued during each
- Live uptime on the dashboard, replacing the previously hardcoded "100%"
  - The bypass posts a small `BypassStatus` heartbeat every 15 minutes; the collector
    surfaces it under `/api/stats.bypass_status` and the site renders it
  - Shows **Data Uptime** (the availability a visitor actually experiences, kept high
    by the bypass) with a **device health** sublabel (the Eagle-200's own uptime)
  - The heartbeat is recorded out-of-band and never touches the data-freshness signal,
    so it cannot mask the staleness / Pushover alerting during a genuine total outage
- Pushover emergency-priority alerting for power-meter outages (`fly/eagle-monitor`)
  - Fires a siren push that repeats every 60s until acknowledged when data stops arriving
  - Triggers only on the healthy→unhealthy transition (exactly one alert per outage); recovery stays Slack-only
  - Credentials supplied via `PUSHOVER_API_TOKEN` / `PUSHOVER_USER_KEY` Fly secrets
  - Regression tests assert exactly one alert per outage and per recovery event
  - Advertised in the dashboard Technology Stack ("Monitoring & Alerting")
- Data staleness detection for power monitoring dashboard
  - Displays dashes (--) instead of stale values when data is older than 2 minutes
  - Shows age indicator: "Live" (<30s), "Updated Xs ago" (30-60s), "Updated Xm ago" (1-2m), "No data for Xh Xm" (>2m)
  - Prevents misleading display of outdated power consumption values
  - Automatically resumes showing real values when fresh data arrives
- Theory of Operation documentation (`docs/THEORY_OF_OPERATION.md`) with comprehensive Mermaid diagrams
- Public dashboard URL for Grafana: `https://linknode-grafana.fly.dev/public-dashboards/cbdf956d4ab84932bf6841531f6524d9`

### Security
- **CRITICAL FIX**: Grafana anonymous access changed from `Admin` to `Viewer` role
  - Previously, any anonymous user had full admin access to Grafana
  - Could edit/delete dashboards, modify datasources, access admin settings
  - Reported by Robbie G. (Cloud Security @ Accelerant) via LinkedIn
- Implemented proper authentication model:
  - Anonymous users: Viewer role (read-only dashboard access)
  - Authenticated admin: Full access via login
- Admin password now stored securely:
  - Fly.io secret: `GF_SECURITY_ADMIN_PASSWORD`
  - GitHub secret: `GRAFANA_ADMIN_PASSWORD`
- Disabled unnecessary Grafana features for anonymous users:
  - Explore, Alerting, Unified Alerting, News feed, Help, Profile
- Re-enabled Grafana login form for admin authentication
- Explicit dashboard permissions set for Viewer/Editor roles via API
- Updated Grafana security documentation in `fly/grafana/README.md`
- **Removed hardcoded credentials from scripts**:
  - `fly/influxdb/verify-influxdb.sh` - removed hardcoded InfluxDB token
  - `fly/eagle-monitor/deploy.sh` - removed hardcoded InfluxDB token
  - `clear-energy-data.sh` - removed hardcoded token, added validation
  - `monitoring/live-dashboard-update.sh` - removed hardcoded Grafana credentials
- **Rotated InfluxDB API token** (old tokens exposed in git history):
  - Created new secure token: "Production API Token - Jan 2026"
  - Updated Fly.io secrets: linknode-influxdb, linknode-eagle-monitor, linknode-grafana
  - Revoked old compromised token (`my-super-secret-auth-token`)
  - Added `INFLUXDB_TOKEN` to GitHub repository secrets

### Fixed
- The earlier billing estimate understated a bill by about 6.5% (no rate rider, transit levy
  or GST), reset every month instead of every two months, and counted days in UTC; replaced by
  the bill calculator (see Added)
- Cost figures use BC Hydro's rates effective 2026-04-01 (Step 1 11.87 cents/kWh, basic charge
  23.44 cents/day; Step 2 14.08 cents and the 22.1918 kWh/day threshold unchanged) and the
  configured rates now take precedence over the price the Eagle reports, which still read the
  April 2025 Step 1 of 11.72 cents. The Eagle's value stays visible as `meter_price_per_kwh`
- The Pi's uptime heartbeat is saved in the store and restored at startup, so a restart no
  longer blanks the Data Uptime and Sample Interval tiles for up to 15 minutes
- A failed database write no longer counts as fresh data for the staleness alarm; the
  freshness bookkeeping depends only on the primary store's write
- CORS now allows `https://www.linknode.com` (the page's API calls failed from www)
- `/api/stats?hours=` rejects non-integer or out-of-range values with 400 instead of a 500
- Restored GitHub Actions auto-deploy to Fly.io
  - `FLY_API_TOKEN` had an expired third-party discharge token, so every push-triggered deploy was failing authentication
  - Rotated to a fresh org deploy token; push-to-`main` now deploys changed services automatically again
- Updated remaining hardcoded paths to use relative paths in scripts
  - `monitoring/test-api-endpoints.sh`: Fixed cloudflare-setup path reference
  - `monitoring/fix-eagle-404.sh`: Changed rackspace-connect.sh to linknode-connect.sh
  - `websites/website-manager/create-website.sh`: Now uses SCRIPT_DIR pattern for dynamic paths
  - `websites/website-manager/scripts/git-integration.sh`: Replaced all hardcoded paths with dynamic resolution
- All scripts now work correctly regardless of project directory name (linknode-com vs rackspace)
- Cloudflare DNS configuration issues causing 522 errors
- Fly.io auto-stop settings preventing reliable uptime
- Cleaned up orphaned volumes in InfluxDB and Grafana deployments

## [1.1.0] - 2025-01-28

### Changed
- Renamed repository from `rackspace-k8s-demo` to `linknode-com`
- Updated all scripts to use relative paths instead of absolute paths
- Scripts now use standard bash pattern for dynamic path resolution

### Added
- Security enhancements with CSP headers, API authentication, and rate limiting
- Comprehensive E2E testing with Playwright (3 phases, 30+ test scenarios)
- Regression testing baseline established for quality assurance
- Security monitoring and automated vulnerability scanning

### Infrastructure
- Migrated from Kubernetes to Fly.io for simplified deployment
- Deployed services: web (nginx), eagle-monitor, grafana, influxdb
- Live at https://linknode.com