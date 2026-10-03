# Service Health Check Endpoints

## Overview
This document lists the health checks for Linknode services and how to monitor them.

Since 2026-09-27 there are two services: the ingest/API app `linknode-eagle-monitor`
(the only Fly.io app, with SQLite on its `eagle_data` volume) and the static site on a
Cloudflare Worker. InfluxDB, Grafana and the nginx `linknode-web` app were retired and
have no health checks.

## Service Endpoints

### Eagle Monitor API
- **URL**: `https://linknode-eagle-monitor.fly.dev/health`
- **Expected Response**: 200 OK with JSON; 503 if the SQLite store is unavailable
- **Method**: GET
- **Timeout**: 10 seconds
- **What it checks**: runs `SELECT 1` against `/data/energy.db` (`db_ok`). It does not
  check data freshness; that is the staleness monitor's job (below).
- **Example**:
  ```bash
  curl -sf https://linknode-eagle-monitor.fly.dev/health
  # Expected: {"db_ok":true,"status":"healthy","uptime_seconds":373.3}
  ```

### Fly.io Service Checks
Defined in `fly/eagle-monitor/fly.toml` and run by Fly against the single machine. While
a check fails, Fly stops routing requests to the machine. It does not restart it.

| Check | Interval | Timeout | Grace | Target |
|-------|----------|---------|-------|--------|
| HTTP | 10s | 2s | 5s | `GET /health` on port 5000 |
| TCP | 15s | 2s | 5s | port 5000 |

The SQLite busy timeout (1.5s) is kept under the 2s HTTP check timeout.

```bash
flyctl status -a linknode-eagle-monitor
# Expect one machine, "2 total, 2 passing"
flyctl checks list -a linknode-eagle-monitor
```

### Data Freshness (Staleness Monitor)
`/health` can be green while no readings arrive. Freshness has its own endpoint and its
own alarm; the full account is in [ALERTING.md](ALERTING.md).

- **URL**: `https://linknode-eagle-monitor.fly.dev/health/data`
- **Expected Response**: 200 with `status: fresh` while the newest power reading is 30
  minutes old or less; 503 with `stale`, `no_data` or `unavailable` otherwise
- **What it measures**: the age of the newest power reading by the reading's own
  timestamp (the Eagle's last contact with the meter), not the time a POST last arrived

```bash
curl -s https://linknode-eagle-monitor.fly.dev/health/data
# Expected: {"last_reading":"...","power_w":383.0,"reading_age_seconds":29.8,"stale_after_seconds":1800,"status":"fresh"}
```

Inside the app an APScheduler job judges the same reading every 5 minutes
(`monitor_data_staleness.py`):

- **Unhealthy** when the newest power reading is more than `STALE_THRESHOLD_MINUTES`
  (30, set in `fly.toml`) old by its own timestamp, when it is zero or missing, or when
  the meter's kWh register has not changed in 2 hours although readings keep arriving
- **On healthy to unhealthy**: Slack alert plus a Pushover emergency siren. The siren is
  sent again on every run until Pushover accepts it
- **While unhealthy**: a normal-priority Pushover reminder every 24 hours
- **On recovery**: Slack alert only
- State persists in `/data/monitor_state.json` (created at the first change of state),
  so a restart does not repeat an alert
- The same job reports a Pi watchdog that has made no request to `/health/data` for 6
  hours (a normal-priority Pushover message)

Do not judge freshness by `last_update` in `/api/stats`. It is the arrival time of the
last stored POST, and it stays current while the Eagle keeps answering with a frozen
reading. `reads_24h` in the same reply counts only readings with a new timestamp.

The upstream side (the Raspberry Pi uploader) keeps its own counters in
`/run/eagle-bypass/stats.json`; see `deploy/README.md`.

### Web Interface
- **URL**: `https://linknode.com/` (Worker preview: `https://linknode-web.murr2k.workers.dev/`)
- **Expected Response**: 200 OK with HTML containing "Linknode"
- **Method**: GET
- **Timeout**: 10 seconds
- **Example**:
  ```bash
  curl -sf https://linknode.com/ | grep -q "Linknode"
  echo $?  # Should return 0 for success

  # Deployed build
  curl -sf https://linknode.com/build-info.json
  ```

### Energy Dashboard Redirect
- **URL**: `https://energy.linknode.com/`
- **Expected Response**: 301 to `https://linknode.com/#energy-dashboard`
- **Example**:
  ```bash
  curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" https://energy.linknode.com/
  ```

## Monitoring Script

A script to check all services:

```bash
#!/bin/bash
# health-check-all.sh - Monitor all Linknode services

check_service() {
  local name=$1
  local check_cmd=$2

  echo -n "Checking $name... "
  if eval "$check_cmd"; then
    echo "OK"
    return 0
  else
    echo "FAILED"
    return 1
  fi
}

check_service "Eagle Monitor" \
  "curl -sf -m 10 https://linknode-eagle-monitor.fly.dev/health | grep -q '\"db_ok\":true'"

check_service "Web Interface" \
  "curl -sf -m 10 https://linknode.com/ | grep -q Linknode"

check_service "Dashboard API" \
  "curl -sf -m 15 'https://linknode-eagle-monitor.fly.dev/api/dashboard?range=1h' >/dev/null"

check_service "Telemetry freshness" \
  "curl -sf -m 10 https://linknode-eagle-monitor.fly.dev/health/data >/dev/null"
```

## Deployment Workflow Integration

The deploy workflows run a health check after each deployment:

```yaml
# deploy-fly.yml (eagle-monitor): after flyctl deploy
if curl -sf https://linknode-eagle-monitor.fly.dev/health -m 10; then
  echo "Eagle Monitor health check passed"
fi

# deploy-web.yml (site): after wrangler deploy
curl -sf https://linknode-web.murr2k.workers.dev/ | grep -q "Linknode"
curl -sf https://linknode-web.murr2k.workers.dev/build-info.json | grep -q "${{ github.sha }}"
```

`deploy-fly.yml` captures the running image before it deploys (the run logs
`Current image: registry.fly.io/linknode-eagle-monitor:...`) and redeploys that image if
`flyctl deploy` fails on the last of its three attempts. The capture was broken until
2026-10-03, and the rollback step itself has never run, so its first real use is its
first test. It restores the image only: the failed commit's `fly.toml` is applied with
it. The other branch, a deploy that succeeds and then fails the `/health` curl, has no
rollback step: that release stays on the machine, unrouted while `/health` fails, until
a good one is deployed (revert the commit and push, or run `flyctl deploy --remote-only`
from `fly/eagle-monitor` at the last good commit).

## Health Check Standards

1. **Response Time**: `/health` MUST respond within 2 seconds, the timeout of Fly's own
   check on it: a slower reply fails the check, and while the check fails Fly stops routing
   to the machine. Every other health endpoint MUST respond within 10 seconds, the curl
   timeout used in this file
2. **Authentication**: Health endpoints SHOULD NOT require authentication
3. **Status Codes**:
   - 200 OK - Service is healthy
   - 503 Service Unavailable - Service is up but its store is not, or (`/health/data`)
     the telemetry is stale
   - Any other code - Service is unhealthy
4. **Content**: Health responses SHOULD include:
   - Service version (when applicable)
   - Uptime or timestamp
   - Basic status indicator

## Troubleshooting

### Common Issues

1. **Timeout Errors**
   - Increase timeout value (default is 10s)
   - Check network connectivity
   - Verify service is actually running (`flyctl status -a linknode-eagle-monitor`)

2. **503 with `db_ok: false`, or the API answers with an error page or not at all**
   - Check logs for SQLite errors: `flyctl logs -a linknode-eagle-monitor`
   - The app answers `/health` with 503 and `db_ok: false`. While that check fails Fly
     routes no requests to the machine, so the app's replies stop reaching callers: expect
     an error from Fly's proxy, or no answer (not exercised here).
     `flyctl checks list -a linknode-eagle-monitor` shows the check's own output
   - Fly does not restart the machine: fix the cause, then
     `flyctl machine restart <machine-id> -a linknode-eagle-monitor`
   - A machine that started without its volume is a different case. It logs
     `/data is not a mounted volume`, opens an empty store and answers `/health` with 200.
     Confirm the `eagle_data` volume is attached: `flyctl volumes list -a linknode-eagle-monitor`

3. **Healthy but stale data** (`/health` is 200, `/health/data` is 503 `stale`)
   - The ingest service is answering and no new reading is being stored. Usually the Pi
     or the Eagle is not delivering
   - Check the Pi: `journalctl -u eagle-bypass -n 20` and `/run/eagle-bypass/stats.json`.
     The steps for each case are in [ALERTING.md](ALERTING.md), "When an alert arrives"

4. **SSL/TLS Errors**
   - Use `-k` flag for self-signed certificates (not recommended for production)
   - Verify certificate validity

### Debug Commands

```bash
# Verbose curl for debugging
curl -v https://linknode-eagle-monitor.fly.dev/health

# Check DNS resolution
nslookup linknode.com

# Get response headers only (site security headers come from web/public/_headers)
curl -I https://linknode.com/
```

## Adding New Services

When adding a new service to Linknode:

1. Implement a health endpoint that follows the standards above
2. Document the endpoint in this file
3. Add health check to deployment workflow
4. Update monitoring scripts
5. Test the health check in all environments

## Related Documentation

- [GitHub Actions Workflows](../.github/workflows/README.md)
- [Theory of Operation](./THEORY_OF_OPERATION.md)
- [Outage Alerting](./ALERTING.md)
- [Pi Uploader and Watchdog Deployment](../deploy/README.md)
