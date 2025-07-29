# Service Health Check Endpoints

## Overview
This document lists all health check endpoints for Linknode services and how to properly monitor them.

## Service Endpoints

### InfluxDB
- **URL**: `http://linknode-influxdb.fly.dev:8086/ping`
- **Expected Response**: 204 No Content
- **Method**: GET
- **Timeout**: 10 seconds
- **Example**:
  ```bash
  curl -sf http://linknode-influxdb.fly.dev:8086/ping
  echo $?  # Should return 0 for success
  ```

### Eagle Monitor API
- **URL**: `https://linknode-eagle-monitor.fly.dev/health`
- **Expected Response**: 200 OK with JSON
- **Method**: GET
- **Timeout**: 10 seconds
- **Example**:
  ```bash
  curl -sf https://linknode-eagle-monitor.fly.dev/health | jq .
  # Expected: {"status": "healthy", "timestamp": "..."}
  ```

### Grafana
- **URL**: `https://linknode-grafana.fly.dev/api/health`
- **Expected Response**: 200 OK with JSON
- **Method**: GET
- **Timeout**: 10 seconds
- **Example**:
  ```bash
  curl -sf https://linknode-grafana.fly.dev/api/health | jq .
  # Expected: {"commit": "...", "database": "ok", "version": "..."}
  ```

### Web Interface
- **URL**: `https://linknode-web.fly.dev/`
- **Expected Response**: 200 OK with HTML containing "Linknode"
- **Method**: GET
- **Timeout**: 10 seconds
- **Example**:
  ```bash
  curl -sf https://linknode-web.fly.dev/ | grep -q "Linknode"
  echo $?  # Should return 0 for success
  ```

## Monitoring Script

Create a script to monitor all services:

```bash
#!/bin/bash
# health-check-all.sh - Monitor all Linknode services

check_service() {
  local name=$1
  local url=$2
  local check_cmd=$3
  
  echo -n "Checking $name... "
  if eval "$check_cmd"; then
    echo "✅ Healthy"
    return 0
  else
    echo "❌ Unhealthy"
    return 1
  fi
}

# Run health checks
check_service "InfluxDB" \
  "http://linknode-influxdb.fly.dev:8086/ping" \
  "curl -sf http://linknode-influxdb.fly.dev:8086/ping"

check_service "Eagle Monitor" \
  "https://linknode-eagle-monitor.fly.dev/health" \
  "curl -sf https://linknode-eagle-monitor.fly.dev/health >/dev/null"

check_service "Grafana" \
  "https://linknode-grafana.fly.dev/api/health" \
  "curl -sf https://linknode-grafana.fly.dev/api/health >/dev/null"

check_service "Web Interface" \
  "https://linknode-web.fly.dev/" \
  "curl -sf https://linknode-web.fly.dev/ | grep -q Linknode"
```

## Deployment Workflow Integration

The GitHub Actions deployment workflow uses these health checks after each deployment:

```yaml
# Example from deploy-fly.yml
- name: Deploy InfluxDB
  run: |
    # Deploy...
    
    # Health check using documented endpoint
    if curl -sf http://linknode-influxdb.fly.dev:8086/ping -m 10; then
      echo "✅ InfluxDB health check passed"
    fi
```

## Health Check Standards

1. **Response Time**: All health endpoints MUST respond within 10 seconds
2. **Authentication**: Health endpoints SHOULD NOT require authentication
3. **Status Codes**: 
   - 200 OK - Service is healthy
   - 204 No Content - Service is healthy (InfluxDB ping)
   - Any other code - Service is unhealthy
4. **Content**: Health responses SHOULD include:
   - Service version (when applicable)
   - Timestamp
   - Basic status indicator

## Troubleshooting

### Common Issues

1. **Timeout Errors**
   - Increase timeout value (default is 10s)
   - Check network connectivity
   - Verify service is actually running

2. **SSL/TLS Errors**
   - Use `-k` flag for self-signed certificates (not recommended for production)
   - Verify certificate validity

3. **Connection Refused**
   - Service may not be running
   - Check port configuration
   - Verify firewall rules

### Debug Commands

```bash
# Verbose curl for debugging
curl -v https://linknode-eagle-monitor.fly.dev/health

# Check DNS resolution
nslookup linknode-influxdb.fly.dev

# Test with different timeouts
curl -sf --max-time 30 http://linknode-influxdb.fly.dev:8086/ping

# Get response headers only
curl -I https://linknode-grafana.fly.dev/api/health
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
- [Deployment Guide](./DEPLOYMENT.md)
- [Monitoring Setup](./MONITORING.md)