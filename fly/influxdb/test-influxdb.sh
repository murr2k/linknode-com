#!/bin/bash

echo "Testing InfluxDB connection..."

# Get the admin token from the deployed instance
echo "Retrieving admin token..."
ADMIN_TOKEN=$(fly ssh console -a linknode-influxdb -c 'cat /var/lib/influxdb2/admin-token.txt 2>/dev/null' | tr -d '\r\n')

if [ -z "$ADMIN_TOKEN" ]; then
    echo "ERROR: Could not retrieve admin token. InfluxDB may not be initialized yet."
    exit 1
fi

echo "Admin token retrieved: $ADMIN_TOKEN"

# Test the API using internal URL
echo ""
echo "Testing InfluxDB API..."
fly ssh console -a linknode-influxdb -c "curl -s -H 'Authorization: Token $ADMIN_TOKEN' http://localhost:8086/api/v2/buckets"

echo ""
echo "To use this token in other apps:"
echo "  fly secrets set INFLUXDB_TOKEN='$ADMIN_TOKEN' --app linknode-eagle-monitor"
echo "  fly secrets set INFLUXDB_TOKEN='$ADMIN_TOKEN' --app linknode-grafana"