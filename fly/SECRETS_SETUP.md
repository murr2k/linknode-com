# Secrets Setup Guide

This guide explains how to properly configure secrets for the Fly.io deployment without exposing them in the codebase.

## Overview

All sensitive information (tokens, passwords, API keys) should be stored as Fly.io secrets, NOT in the code or configuration files.

## Required Secrets

### 1. InfluxDB Secrets

First, navigate to the InfluxDB directory:
```bash
cd fly/influxdb
```

Set the following secrets:
```bash
# Generate a secure token (or use your own)
INFLUX_TOKEN=$(openssl rand -hex 32)

# Set InfluxDB secrets
fly secrets set DOCKER_INFLUXDB_INIT_USERNAME=admin
fly secrets set DOCKER_INFLUXDB_INIT_PASSWORD="your-secure-password-here"
fly secrets set DOCKER_INFLUXDB_INIT_ADMIN_TOKEN="$INFLUX_TOKEN"
```

### 2. Eagle Monitor Secrets

Navigate to the Eagle monitor directory:
```bash
cd ../eagle-monitor
```

Set the InfluxDB token for the Eagle monitor:
```bash
# CRITICAL: Use the same token as InfluxDB - token mismatch will cause "No data" errors!
fly secrets set INFLUXDB_TOKEN="$INFLUX_TOKEN"
```

### 3. Grafana Secrets (if using Grafana)

Navigate to the Grafana directory:
```bash
cd ../grafana
```

Set Grafana admin password and InfluxDB token:
```bash
fly secrets set GF_SECURITY_ADMIN_PASSWORD="your-secure-grafana-password"

# CRITICAL: Use the same token as InfluxDB and Eagle monitor!
fly secrets set INFLUXDB_TOKEN="$INFLUX_TOKEN"
```

**Important**: All three services (InfluxDB, Eagle Monitor, and Grafana) MUST use the same `INFLUXDB_TOKEN`. Token mismatch is the most common cause of "No data" errors in Grafana.

## Verifying Secrets

To verify that secrets are set correctly:

```bash
# List all secrets (names only, not values)
fly secrets list
```

To verify token synchronization across services:
```bash
# Check token digest for each service - they should all match!
fly secrets list -a linknode-influxdb | grep INFLUXDB_TOKEN
fly secrets list -a linknode-eagle-monitor | grep INFLUXDB_TOKEN
fly secrets list -a linknode-grafana | grep INFLUXDB_TOKEN
```

If the digest values don't match, update them all to use the same token.

## Environment File for Local Development

For local development, create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
# Edit .env with your actual values
```

**NEVER commit the `.env` file to version control!**

## Security Best Practices

1. **Use strong, unique passwords** - Generate them with:
   ```bash
   openssl rand -base64 32
   ```

2. **Rotate secrets regularly** - Update them every 90 days

3. **Limit access** - Only share secrets with team members who need them

4. **Use different secrets for each environment** - Don't reuse production secrets in development

5. **Monitor access** - Use Fly.io's audit logs to track secret access

## Troubleshooting

If services fail to start due to missing secrets:

1. Check logs:
   ```bash
   fly logs
   ```

2. Verify all required secrets are set:
   ```bash
   fly secrets list
   ```

3. Ensure secret names match exactly what the application expects

## Secret Rotation

To rotate a secret:

```bash
# Generate new secret
NEW_TOKEN=$(openssl rand -hex 32)

# Update in all relevant apps
fly secrets set INFLUXDB_TOKEN="$NEW_TOKEN" -a linknode-eagle-monitor
fly secrets set DOCKER_INFLUXDB_INIT_ADMIN_TOKEN="$NEW_TOKEN" -a linknode-influxdb
```

Remember to update all services that use the secret!