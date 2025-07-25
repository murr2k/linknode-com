#!/bin/bash

# Script to clear historical energy data from InfluxDB
# This will remove the incorrectly scaled energy values

echo "Clearing historical energy data from InfluxDB..."

# Connect to InfluxDB via Fly.io proxy
flyctl proxy 8086:8086 -a linknode-influxdb &
PROXY_PID=$!

# Wait for proxy to start
sleep 3

# Delete energy_delivered_kwh data
curl -X POST "http://localhost:8086/api/v2/delete?org=myorg&bucket=energy" \
  -H "Authorization: Token mytoken" \
  -H "Content-Type: application/json" \
  -d '{
    "start": "1970-01-01T00:00:00Z",
    "stop": "2025-12-31T23:59:59Z",
    "predicate": "_measurement=\"energy_monitor\" AND _field=\"energy_delivered_kwh\""
  }'

echo "Deleted energy_delivered_kwh data"

# Also delete energy_received_kwh data if any
curl -X POST "http://localhost:8086/api/v2/delete?org=myorg&bucket=energy" \
  -H "Authorization: Token mytoken" \
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