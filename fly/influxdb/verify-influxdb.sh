#!/bin/bash

echo "Verifying InfluxDB setup..."
echo ""

# Set the admin token
ADMIN_TOKEN="linknode-20250720-7468d2699f48f7f91ee4abbeec90a25f"

# Test from within the container using localhost
echo "1. Testing InfluxDB health check..."
fly ssh console -a linknode-influxdb -c "curl -s http://localhost:8086/health" | jq .

echo ""
echo "2. Listing organizations..."
fly ssh console -a linknode-influxdb -c "curl -s -H 'Authorization: Token $ADMIN_TOKEN' http://localhost:8086/api/v2/orgs" | jq .

echo ""
echo "3. Listing buckets..."
fly ssh console -a linknode-influxdb -c "curl -s -H 'Authorization: Token $ADMIN_TOKEN' http://localhost:8086/api/v2/buckets" | jq .

echo ""
echo "4. InfluxDB Admin Token:"
echo "   $ADMIN_TOKEN"
echo ""
echo "5. Set this token in your other apps:"
echo "   fly secrets set INFLUXDB_TOKEN='$ADMIN_TOKEN' --app linknode-eagle-monitor"
echo "   fly secrets set INFLUXDB_TOKEN='$ADMIN_TOKEN' --app linknode-grafana"
echo ""
echo "6. Internal URL for other Fly apps:"
echo "   http://linknode-influxdb.internal:8086"