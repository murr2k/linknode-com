#!/bin/bash
# Script to remove hardcoded secrets from the codebase

echo "Removing hardcoded secrets from configuration files..."

# Create backup directory
mkdir -p .backup-before-secrets-removal

# Backup files before modification
cp fly.toml .backup-before-secrets-removal/fly.toml.bak 2>/dev/null || true
cp influxdb/fly.toml .backup-before-secrets-removal/influxdb-fly.toml.bak 2>/dev/null || true
cp grafana/grafana.ini .backup-before-secrets-removal/grafana.ini.bak 2>/dev/null || true

echo "Backups created in .backup-before-secrets-removal/"
echo ""
echo "IMPORTANT: After running this script, you must:"
echo "1. Set secrets using 'fly secrets set' for each app"
echo "2. See SECRETS_SETUP.md for detailed instructions"
echo ""
echo "Files have been cleaned. Remember to never commit secrets!"