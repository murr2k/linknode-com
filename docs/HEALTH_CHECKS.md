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

### Fly.io Machine Checks
Defined in `fly/eagle-monitor/fly.toml` and run by Fly against the single machine:

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
`/health` can be green while no readings arrive. Freshness is watched inside the app
by an APScheduler job every 5 minutes (`monitor_data_staleness.py`):

- **Unhealthy** when no reading has been stored for more than `STALE_THRESHOLD_MINUTES`
  (default 5) or the last power reading is zero or missing
- **On healthy to unhealthy**: Slack alert plus a Pushover emergency siren
- **On recovery**: Slack alert only
- State persists in `/data/monitor_state.json`, so a restart does not repeat an alert

To check freshness by hand, read `last_update` and `reads_24h` from `/api/stats`:

```bash
curl -s https://linknode-eagle-monitor.fly.dev/api/stats | python -m json.tool
```

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

If the Fly deploy itself fails after its retries, `deploy-fly.yml` redeploys the image
it captured before the deploy.

## Health Check Standards

1. **Response Time**: All health endpoints MUST respond within 10 seconds
2. **Authentication**: Health endpoints SHOULD NOT require authentication
3. **Status Codes**:
   - 200 OK - Service is healthy
   - 503 Service Unavailable - Service is up but its store is not
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

2. **503 with `db_ok: false`**
   - Check logs for `/data is not a mounted volume` or SQLite errors:
     `flyctl logs -a linknode-eagle-monitor`
   - Confirm the `eagle_data` volume is attached: `flyctl volumes list -a linknode-eagle-monitor`

3. **Healthy but stale data**
   - The ingest service is fine; the Pi or the Eagle is not delivering
   - Check the Pi: `journalctl -u eagle-bypass` and `/run/eagle-bypass/stats.json`

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
- [Pi Bypass Deployment](../deploy/README.md)
