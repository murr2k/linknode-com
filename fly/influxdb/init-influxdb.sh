#!/bin/bash
set -e

echo "=========================================="
echo "Starting InfluxDB initialization process"
echo "=========================================="

# Generate a predictable admin token (UUID-like format)
ADMIN_TOKEN="linknode-$(date +%Y%m%d)-$(openssl rand -hex 16)"

# Set environment variables for auto-setup
export DOCKER_INFLUXDB_INIT_MODE=setup
export DOCKER_INFLUXDB_INIT_USERNAME=admin
export DOCKER_INFLUXDB_INIT_PASSWORD="${INFLUXDB_ADMIN_PASSWORD}"
export DOCKER_INFLUXDB_INIT_ORG=linknode
export DOCKER_INFLUXDB_INIT_BUCKET=energy
export DOCKER_INFLUXDB_INIT_RETENTION=30d
export DOCKER_INFLUXDB_INIT_ADMIN_TOKEN="$ADMIN_TOKEN"

echo "Configuration:"
echo "  Organization: linknode"
echo "  Initial Bucket: energy (30-day retention)"
echo "  Admin Username: admin"
echo "  Admin Token: $ADMIN_TOKEN"
echo ""

# Create a marker file to show we've initialized
mkdir -p /var/lib/influxdb2
touch /var/lib/influxdb2/.initialized

# Store the token in a file for reference
echo "$ADMIN_TOKEN" > /var/lib/influxdb2/admin-token.txt

echo "==================================================================================="
echo "IMPORTANT: Save this admin token and set it as a Fly secret:"
echo ""
echo "fly secrets set INFLUXDB_TOKEN='$ADMIN_TOKEN' --app linknode-influxdb"
echo ""
echo "Also set this token in your other Fly apps that need to access InfluxDB:"
echo "fly secrets set INFLUXDB_TOKEN='$ADMIN_TOKEN' --app linknode-eagle-monitor"
echo "fly secrets set INFLUXDB_TOKEN='$ADMIN_TOKEN' --app linknode-grafana"
echo "==================================================================================="
echo ""
echo "Starting InfluxDB with automatic setup..."

# Start InfluxDB with the default entrypoint
exec /entrypoint.sh influxd