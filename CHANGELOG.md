# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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