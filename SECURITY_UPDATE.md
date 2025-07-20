# Security Update - Secrets Management

## Overview

We have updated the codebase to remove all hardcoded secrets and tokens. All sensitive information must now be managed through environment variables and Fly.io secrets.

## Changes Made

1. **Removed hardcoded tokens** from:
   - InfluxDB configuration files
   - Eagle monitor application
   - Grafana configuration
   - Deployment scripts

2. **Added documentation**:
   - `fly/SECRETS_SETUP.md` - Complete guide for setting up secrets
   - `fly/.env.example` - Template for local development
   - Updated README files with security notices

3. **Updated .gitignore** to exclude:
   - `.env` files
   - Secret files
   - API keys and certificates

## Migration Steps

If you have an existing deployment:

1. **Save your current secrets**:
   ```bash
   # Note down your current tokens and passwords
   fly secrets list -a linknode-influxdb
   fly secrets list -a linknode-eagle-monitor
   fly secrets list -a linknode-grafana
   ```

2. **Set secrets properly**:
   ```bash
   cd fly
   # Follow instructions in SECRETS_SETUP.md
   ```

3. **Redeploy services**:
   ```bash
   # Deploy each service with new configuration
   cd influxdb && fly deploy
   cd ../eagle-monitor && fly deploy
   cd ../grafana && fly deploy
   ```

## Security Best Practices

1. **Never commit secrets** to version control
2. **Use strong, unique passwords** for each service
3. **Rotate secrets regularly** (every 90 days)
4. **Use different secrets** for dev/staging/production
5. **Limit access** to production secrets

## Verification

To verify no secrets are exposed:

```bash
# Search for potential secrets in the codebase
grep -r "password\|token\|secret" --exclude-dir=.git --exclude="*.md" .
```

All results should show only:
- Environment variable references
- Documentation
- Example/template files

## Support

If you encounter issues:
1. Check `fly/SECRETS_SETUP.md` for detailed instructions
2. Verify all required secrets are set with `fly secrets list`
3. Check application logs with `fly logs`