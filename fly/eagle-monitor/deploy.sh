#!/bin/bash
set -e

echo "Deploying Eagle-200 XML Monitor to Fly.io..."

# Check if app exists
if fly apps list | grep -q "linknode-eagle-monitor"; then
    echo "App already exists, deploying update..."
else
    echo "Creating new app..."
    fly apps create linknode-eagle-monitor --org personal
fi

# Set the InfluxDB token secret
echo "Setting InfluxDB token secret..."
# IMPORTANT: Set the actual token from your InfluxDB setup
# Get token from: fly secrets list -a linknode-influxdb
# fly secrets set INFLUXDB_TOKEN='your-influxdb-token' --app linknode-eagle-monitor
echo "WARNING: You must manually set INFLUXDB_TOKEN secret before deploying"
echo "Run: fly secrets set INFLUXDB_TOKEN='your-token' --app linknode-eagle-monitor"

# Deploy the app
echo "Deploying application..."
fly deploy --app linknode-eagle-monitor

# Show status
echo "Deployment complete!"
fly status --app linknode-eagle-monitor