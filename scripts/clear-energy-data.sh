#!/bin/bash

# Script to clear historical energy data from InfluxDB
# This will remove the incorrectly scaled energy values

echo "Clearing historical energy data from InfluxDB..."

# NOTE: Set these environment variables before running:
# export INFLUXDB_TOKEN="your-token"  # Get from: fly secrets list -a linknode-influxdb
INFLUXDB_TOKEN="${INFLUXDB_TOKEN:-}"
INFLUXDB_ORG="${INFLUXDB_ORG:-linknode}"

if [ -z "$INFLUXDB_TOKEN" ]; then
    echo "ERROR: INFLUXDB_TOKEN environment variable not set"
    echo "Get your token from: fly secrets list -a linknode-influxdb"
    echo "Then run: export INFLUXDB_TOKEN='your-token'"
    exit 1
fi

# Connect to InfluxDB via Fly.io proxy
flyctl proxy 8086:8086 -a linknode-influxdb &
PROXY_PID=$!

# Wait for proxy to start
sleep 3

# Delete energy_delivered_kwh data
curl -X POST "http://localhost:8086/api/v2/delete?org=${INFLUXDB_ORG}&bucket=energy" \
  -H "Authorization: Token ${INFLUXDB_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "start": "1970-01-01T00:00:00Z",
    "stop": "2025-12-31T23:59:59Z",
    "predicate": "_measurement=\"energy_monitor\" AND _field=\"energy_delivered_kwh\""
  }'

echo "Deleted energy_delivered_kwh data"

# Also delete energy_received_kwh data if any
curl -X POST "http://localhost:8086/api/v2/delete?org=${INFLUXDB_ORG}&bucket=energy" \
  -H "Authorization: Token ${INFLUXDB_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "start": "1970-01-01T00:00:00Z",
    "stop": "2025-12-31T23:59:59Z",
    "predicate": "_measurement=\"energy_monitor\" AND _field=\"energy_received_kwh\""
  }'

echo "Deleted energy_received_kwh data"

# Kill the proxy
kill $PROXY_PID

echo "Historical energy data cleared. New data will be stored with correct scaling."
