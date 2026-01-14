# Grafana Configuration for Linknode Energy Monitor

This directory contains the Grafana configuration for visualizing energy monitoring data from the Eagle-200 device.

## Quick Start

```bash
# Deploy Grafana
fly deploy

# Set the InfluxDB token (must match the token used by InfluxDB and Eagle monitor)
fly secrets set INFLUXDB_TOKEN="your-influxdb-token" -a linknode-grafana

# Set the admin password
fly secrets set GF_SECURITY_ADMIN_PASSWORD="your-secure-password" -a linknode-grafana

# Verify deployment
fly status -a linknode-grafana
```

## Configuration Files

- `grafana.ini` - Main Grafana configuration with security and embedding settings
- `Dockerfile` - Container configuration (uses Grafana 11.4.0)
- `fly.toml` - Fly.io deployment configuration with environment variables
- `provisioning/datasources/influxdb.yaml` - InfluxDB datasource configuration
- `provisioning/dashboards/power-monitoring.json` - Energy monitoring dashboard

## Security Configuration

### Authentication Model

The Grafana instance uses a **public read-only** model:

| User Type | Role | Capabilities |
|-----------|------|--------------|
| Anonymous (public) | Viewer | View dashboards only |
| Authenticated admin | Admin | Full access |

### Secrets Storage

| Secret | Storage Location | Purpose |
|--------|------------------|---------|
| `GF_SECURITY_ADMIN_PASSWORD` | Fly.io secrets | Admin login password |
| `GRAFANA_ADMIN_PASSWORD` | GitHub repository secrets | Backup/CI reference |
| `INFLUXDB_TOKEN` | Fly.io secrets | InfluxDB authentication |

**Admin Credentials:**
- Username: `admin`
- Password: Stored in `GF_SECURITY_ADMIN_PASSWORD` Fly secret
- Login URL: https://linknode-grafana.fly.dev/login

### Access Control Settings

```ini
# Anonymous access (Viewer role - read-only)
[auth.anonymous]
enabled = true
org_role = Viewer

# Features disabled for security
[explore]
enabled = false

[alerting]
enabled = false

[unified_alerting]
enabled = false
```

### Dashboard Permissions

The power-monitoring dashboard has explicit permissions set:
- **Viewer role**: Can view (permission level 1)
- **Editor role**: Can view (permission level 1)
- **Admin role**: Full access

Permissions were set via API:
```bash
curl -u "admin:PASSWORD" -X POST \
  "https://linknode-grafana.fly.dev/api/dashboards/id/1/permissions" \
  -H "Content-Type: application/json" \
  -d '{"items":[{"role":"Editor","permission":1},{"role":"Viewer","permission":1}]}'
```

### Public Dashboard

A public dashboard share is also available (no authentication required):
```
https://linknode-grafana.fly.dev/public-dashboards/cbdf956d4ab84932bf6841531f6524d9
```

## Embedding Settings

The `grafana.ini` file includes these settings for iframe embedding:

```ini
[security]
allow_embedding = true
cookie_samesite = none
cookie_secure = true
content_security_policy = false
```

## Datasource Configuration

The InfluxDB datasource is configured for Flux queries:

```yaml
jsonData:
  version: Flux          # Required for InfluxDB 2.x
  organization: linknode # Must match InfluxDB organization
  defaultBucket: energy  # Must match InfluxDB bucket
  httpMode: POST         # Required for Flux queries
```

## Dashboard Queries

All queries use these measurement and field names:

- Measurement: `energy_monitor`
- Power field: `power_w`
- Energy field: `energy_delivered_kwh`

Example query:
```flux
from(bucket: "energy")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "energy_monitor")
  |> filter(fn: (r) => r._field == "power_w")
```

## Access Points

- **Direct Dashboard**: https://linknode-grafana.fly.dev/d/power-monitoring/eagle-energy-monitor
- **Public Dashboard**: https://linknode-grafana.fly.dev/public-dashboards/cbdf956d4ab84932bf6841531f6524d9
- **Embedded View**: https://linknode.com (iframe in web interface)
- **Admin Login**: https://linknode-grafana.fly.dev/login
- **API Health Check**: https://linknode-grafana.fly.dev/api/health

## Environment Variables

**Required secrets (set via `fly secrets set`):**
- `INFLUXDB_TOKEN` - Authentication token for InfluxDB
- `GF_SECURITY_ADMIN_PASSWORD` - Admin user password

**Optional environment variables (set in fly.toml):**
- `GF_LOG_LEVEL` - Logging level (default: "info")
- `GF_SERVER_ROOT_URL` - Public URL for Grafana

## Troubleshooting

### Reset Admin Password

If you lose admin access:
```bash
flyctl ssh console -a linknode-grafana -C "grafana-cli admin reset-admin-password 'NEW_PASSWORD'"
```

### Check Logs

```bash
flyctl logs -a linknode-grafana
```

### Verify Anonymous Access

```bash
curl -s "https://linknode-grafana.fly.dev/api/dashboards/uid/power-monitoring" | jq '.meta.slug'
# Should return: "eagle-energy-monitor"
```

## Version History

- **Grafana 11.4.0** - Current version (fixed DOMPurify CVE-2024-47875)
- Security hardening applied 2026-01-14
