#!/bin/bash
set -e

echo "Deploying InfluxDB to Fly.io..."

# First, destroy the existing volume to start fresh
echo "Removing existing volume to ensure clean initialization..."
fly volumes destroy influxdb_data -a linknode-influxdb --yes 2>/dev/null || true

# Create a new volume
echo "Creating new volume..."
fly volumes create influxdb_data --size 1 --region ord -a linknode-influxdb

# Deploy the application
echo "Deploying application..."
fly deploy --app linknode-influxdb

echo ""
echo "Deployment complete!"
echo ""
echo "To check the logs and get the admin token:"
echo "  fly logs -a linknode-influxdb"
echo ""
echo "To SSH into the container:"
echo "  fly ssh console -a linknode-influxdb"
echo ""
echo "To check the admin token after deployment:"
echo "  fly ssh console -a linknode-influxdb -c 'cat /var/lib/influxdb2/admin-token.txt'"