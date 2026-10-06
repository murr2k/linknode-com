# Secrets Setup Guide

This guide explains how to properly configure secrets for the Fly.io app and the CI/CD
pipelines without exposing them in the codebase.

## Overview

All sensitive information (tokens, passwords, API keys) should be stored as Fly.io or
GitHub Actions secrets, NOT in the code or configuration files.

Since 2026-09-27 there is one Fly app, `linknode-eagle-monitor`. The site is a
Cloudflare Worker deployed from GitHub Actions. The InfluxDB and Grafana apps, and
their secrets, are retired.

## Required Secrets

### 1. Eagle Monitor Secrets (Fly.io)

Set these on `linknode-eagle-monitor`:

```bash
# Basic auth for the ingest endpoint (/eagle)
fly secrets set EAGLE_PASSWORD="your-secure-password-here" -a linknode-eagle-monitor

# Outage alerting
fly secrets set SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." -a linknode-eagle-monitor
fly secrets set PUSHOVER_API_TOKEN="..." PUSHOVER_USER_KEY="..." -a linknode-eagle-monitor
```

**Important**: `EAGLE_PASSWORD` must match `EAGLE_UPLOAD_PASSWORD` in
`/etc/eagle-bypass.env` on the Raspberry Pi. A mismatch makes every upload fail with
401 and the dashboard goes stale. Change both in the same step.

Optional (not set in production): `EAGLE_API_KEY` to require a key on the read
endpoints, `ADMIN_API_KEY` for `/api/security/stats`.

### 2. GitHub Actions Secrets

Set these at https://github.com/murr2k/linknode-com/settings/secrets/actions:

- `FLY_API_TOKEN` - Fly.io deploy token (`deploy-fly.yml`); see
  [FLY_TOKEN_UPDATE_PROCEDURE.md](FLY_TOKEN_UPDATE_PROCEDURE.md)
- `CLOUDFLARE_API_TOKEN` - Cloudflare token allowed to deploy Workers (`deploy-web.yml`)
- `CLOUDFLARE_ACCOUNT_ID` - Cloudflare account (`deploy-web.yml`)

### Retired Secrets

No longer used; remove any leftovers:

- GitHub: `INFLUXDB_TOKEN`, `GRAFANA_ADMIN_PASSWORD`
- Fly: `INFLUXDB_TOKEN` and `DOCKER_INFLUXDB_INIT_*` (InfluxDB app),
  `GF_SECURITY_ADMIN_PASSWORD` (Grafana app). The apps themselves were destroyed.

## Verifying Secrets

To verify that secrets are set correctly:

```bash
# List all secrets (names and digests only, not values)
fly secrets list -a linknode-eagle-monitor
# Expected: EAGLE_PASSWORD, SLACK_WEBHOOK_URL, PUSHOVER_API_TOKEN, PUSHOVER_USER_KEY,
# CLOUDFLARE_ANALYTICS (optional: the site traffic figures)

gh secret list -R murr2k/linknode-com
```

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

If the service fails to start or data stops arriving:

1. Check logs:
   ```bash
   fly logs -a linknode-eagle-monitor
   ```

2. Verify all required secrets are set:
   ```bash
   fly secrets list -a linknode-eagle-monitor
   ```

3. Ensure secret names match exactly what the application expects

4. If uploads get 401, compare the Pi's `EAGLE_UPLOAD_PASSWORD` with `EAGLE_PASSWORD`

## Secret Rotation

To rotate the ingest password:

```bash
# Generate new secret
NEW_PASSWORD=$(openssl rand -hex 32)

# Update the Fly app (this restarts the machine)
fly secrets set EAGLE_PASSWORD="$NEW_PASSWORD" -a linknode-eagle-monitor

# Update the Pi to match, then restart the uploader
ssh -t pi@<pi-ip> sudoedit /etc/eagle-bypass.env     # EAGLE_UPLOAD_PASSWORD
ssh pi@<pi-ip> sudo systemctl restart eagle-bypass.service
```

Caution: Rainforest's upload destination for this endpoint was locked to the current
password and can no longer be edited. The Eagle's own uploader is removed today, but if
it is ever restored, a rotated password would break that path.

Remember to update everything that uses the secret!
