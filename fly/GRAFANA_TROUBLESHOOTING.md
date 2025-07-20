# Grafana Dashboard Troubleshooting Guide

This document captures all the issues encountered and fixes applied when setting up the Grafana dashboard for the Linknode Energy Monitor project. Use this guide when porting to a new server to avoid common pitfalls.

## Issues Encountered and Solutions

### 1. Grafana Dockerfile Using Wrong Configuration File

**Issue**: The Dockerfile was copying `grafana-minimal.ini` instead of `grafana.ini`, which was missing critical embedding settings.

**Symptom**: Grafana charts wouldn't embed in iframes, showing loading errors.

**Fix**: 
```dockerfile
# ❌ Wrong
COPY --chown=grafana:root grafana-minimal.ini /etc/grafana/grafana.ini

# ✅ Correct
COPY --chown=grafana:root grafana.ini /etc/grafana/grafana.ini
```

**Critical Settings Required in grafana.ini**:
```ini
[security]
allow_embedding = true
cookie_samesite = none
cookie_secure = true
content_security_policy = false
```

### 2. Dashboard JSON Had Duplicate Panel Arrays

**Issue**: The `power-monitoring.json` file had panels defined correctly at the top, but then an empty `"panels": []` array at the bottom that was overriding them.

**Symptom**: "Panel with id 2 not found" error in the embedded view.

**Fix**: Remove the duplicate empty panels array. The JSON should only have one panels array with the actual panel definitions.

### 3. Mismatched InfluxDB Tokens

**Issue**: Different services were using different InfluxDB authentication tokens.

**Symptom**: "Authentication to data source failed" errors in Grafana logs.

**Fix**: Ensure all services use the same token:
```bash
# Set the same token for all services
fly secrets set INFLUXDB_TOKEN="my-super-secret-auth-token" -a linknode-influxdb
fly secrets set INFLUXDB_TOKEN="my-super-secret-auth-token" -a linknode-eagle-monitor
fly secrets set INFLUXDB_TOKEN="my-super-secret-auth-token" -a linknode-grafana
```

### 4. Wrong Measurement and Field Names in Queries

**Issue**: Grafana queries were looking for incorrect measurement and field names that didn't match what the Eagle monitor was writing.

**Symptom**: "No data" displayed in all panels even though data was being collected.

**Fix**: Update queries to match actual data structure:
```flux
# ❌ Wrong
from(bucket: "energy")
  |> filter(fn: (r) => r._measurement == "power_data")
  |> filter(fn: (r) => r._field == "power")

# ✅ Correct
from(bucket: "energy")
  |> filter(fn: (r) => r._measurement == "energy_monitor")
  |> filter(fn: (r) => r._field == "power_w")
```

**Actual Data Structure**:
- Measurement: `energy_monitor`
- Fields:
  - `power_w` (power in watts)
  - `energy_delivered_kwh` (cumulative energy)
  - `energy_received_kwh`
  - `price_per_kwh`
  - `link_strength`

### 5. InfluxDB 2.x Datasource Configuration

**Issue**: Datasource wasn't properly configured for InfluxDB 2.x with Flux queries.

**Fix**: Ensure the datasource configuration includes:
```yaml
apiVersion: 1
datasources:
  - name: InfluxDB
    type: influxdb
    access: proxy
    url: http://linknode-influxdb.internal:8086
    isDefault: true
    jsonData:
      version: Flux          # Must be "Flux" for InfluxDB 2.x
      organization: linknode # Must match InfluxDB org
      defaultBucket: energy  # Must match actual bucket name
      tlsSkipVerify: true
      httpMode: POST         # Important for Flux queries
    secureJsonData:
      token: ${INFLUXDB_TOKEN}
    editable: false
```

## Pre-Deployment Checklist

Before deploying to a new server, verify:

1. **Token Synchronization**:
   ```bash
   # Check all apps have the same token
   fly secrets list -a linknode-influxdb
   fly secrets list -a linknode-eagle-monitor
   fly secrets list -a linknode-grafana
   ```

2. **Verify Data Structure**:
   ```bash
   # Check what measurement/fields are being written
   curl -s https://linknode-eagle-monitor.fly.dev/api/stats
   ```

3. **Grafana Configuration Files**:
   - Ensure `grafana.ini` (not `grafana-minimal.ini`) is used in Dockerfile
   - Verify embedding settings are present
   - Check datasource has `httpMode: POST`

4. **Dashboard JSON Validation**:
   - No duplicate panel arrays
   - Correct measurement names (`energy_monitor`)
   - Correct field names (`power_w`, `energy_delivered_kwh`)
   - Each panel has `"datasource": "InfluxDB"`

5. **Test Queries Before Deployment**:
   - Use Grafana's Explore feature to test queries
   - Verify data is returned before creating panels

## Common Error Messages and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| "Panel with id X not found" | Duplicate panel arrays in JSON | Remove empty `panels: []` array |
| "No data" | Wrong measurement/field names | Check actual data structure |
| "Authentication to data source failed" | Token mismatch | Sync tokens across all services |
| "Grafana has failed to load its application files" | Missing static files or wrong base URL | Check Grafana logs and server configuration |

## Testing the Fix

After deployment, verify:

1. **Datasource Health**:
   ```bash
   curl -s https://linknode-grafana.fly.dev/api/datasources/uid/{UID}/health | jq
   ```
   Should return: `{"status": "OK", "message": "datasource is working. 3 buckets found"}`

2. **Direct Dashboard Access**:
   - Visit: https://linknode-grafana.fly.dev/d/power-monitoring/eagle-energy-monitor
   - Should show data in all panels

3. **Embedded View**:
   - Visit: https://linknode-web.fly.dev/
   - Grafana chart should display with live data

## Additional Notes

- There's a known issue where shell characters (`< /dev/null | >`) get injected into Flux queries in some environments. This doesn't affect pre-configured dashboard panels but may affect ad-hoc queries.
- Always use single-line Flux queries in dashboard JSON to avoid parsing issues
- The Eagle monitor writes data approximately every 6 seconds, so allow time for data to accumulate