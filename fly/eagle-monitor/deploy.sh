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
fly secrets set INFLUXDB_TOKEN='linknode-20250720-7468d2699f48f7f91ee4abbeec90a25f' --app linknode-eagle-monitor

# Deploy the app
echo "Deploying application..."
fly deploy --app linknode-eagle-monitor

# Show status
echo "Deployment complete!"
fly status --app linknode-eagle-monitor