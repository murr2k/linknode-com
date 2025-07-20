# Grafana Configuration for Linknode Energy Monitor

This directory contains the Grafana configuration for visualizing energy monitoring data from the Eagle-200 device.

## Quick Start

```bash
# Deploy Grafana
fly deploy

# Set the InfluxDB token (must match the token used by InfluxDB and Eagle monitor)
fly secrets set INFLUXDB_TOKEN="my-super-secret-auth-token" -a linknode-grafana

# Verify deployment
fly status -a linknode-grafana
```

## Configuration Files

- `grafana.ini` - Main Grafana configuration with embedding enabled
- `Dockerfile` - Container configuration (uses grafana.ini, NOT grafana-minimal.ini)
- `fly.toml` - Fly.io deployment configuration
- `provisioning/datasources/influxdb.yaml` - InfluxDB datasource configuration
- `provisioning/dashboards/power-monitoring.json` - Energy monitoring dashboard

## Important Configuration Details

### 1. Embedding Settings

The `grafana.ini` file must include these settings for iframe embedding to work:

```ini
[security]
allow_embedding = true
cookie_samesite = none
cookie_secure = true
content_security_policy = false
```

### 2. Datasource Configuration

The InfluxDB datasource must be configured for Flux queries:

```yaml
jsonData:
  version: Flux          # Required for InfluxDB 2.x
  organization: linknode # Must match InfluxDB organization
  defaultBucket: energy  # Must match InfluxDB bucket
  httpMode: POST         # Required for Flux queries
```

### 3. Dashboard Queries

All queries must use the correct measurement and field names:

- Measurement: `energy_monitor` (NOT `power_data`)
- Power field: `power_w` (NOT `power`)
- Energy field: `energy_delivered_kwh` (NOT `energy`)

Example query:
```flux
from(bucket: "energy")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "energy_monitor")
  |> filter(fn: (r) => r._field == "power_w")
```

## Troubleshooting

If you encounter issues, see [GRAFANA_TROUBLESHOOTING.md](../GRAFANA_TROUBLESHOOTING.md) for detailed solutions to common problems.

## Access Points

- **Direct Dashboard**: https://linknode-grafana.fly.dev/d/power-monitoring/eagle-energy-monitor
- **Embedded View**: https://linknode-web.fly.dev/ (iframe in web interface)
- **API Health Check**: https://linknode-grafana.fly.dev/api/health

## Environment Variables

Required secrets:
- `INFLUXDB_TOKEN` - Authentication token for InfluxDB (must match across all services)

Optional environment variables (set in fly.toml):
- `GF_LOG_LEVEL` - Logging level (default: "info")
- `GF_SERVER_ROOT_URL` - Public URL for Grafana