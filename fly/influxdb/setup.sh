#!/bin/sh
# Setup script for InfluxDB

# Wait for InfluxDB to start
sleep 5

# Setup InfluxDB with simple credentials
influx setup \
  --username admin \
  --password linknode123 \
  --org linknode \
  --bucket energy \
  --retention 30d \
  --force

# Create an all-access token
influx auth create \
  --org linknode \
  --description "Eagle Monitor Token" \
  --all-access \
  --json > /tmp/token.json

# Extract token
TOKEN=$(cat /tmp/token.json | grep -o '"token":"[^"]*' | grep -o '[^"]*$')
echo "Generated token: $TOKEN"

# Keep container running
exec influxd