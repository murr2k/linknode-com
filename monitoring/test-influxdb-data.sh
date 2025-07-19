#!/bin/bash

echo "=== InfluxDB Data Check ==="
echo ""

# Create a test script to run inside the InfluxDB pod
cat > /tmp/check-influx-data.flux << 'EOF'
// Check data in the last hour
echo "1. Power Demand Data Count (last hour):"
from(bucket: "power_metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "power_demand")
  |> count()
  |> yield(name: "demand_count")

echo ""
echo "2. Power Summation Data Count (last hour):"
from(bucket: "power_metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "power_summation")
  |> count()
  |> yield(name: "summation_count")

echo ""
echo "3. Last 5 Power Demand Readings:"
from(bucket: "power_metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "power_demand")
  |> filter(fn: (r) => r["_field"] == "demand_kw")
  |> last()
  |> limit(n: 5)
  |> yield(name: "last_demands")

echo ""
echo "4. Data Gap Analysis (checks for gaps > 5 minutes):"
from(bucket: "power_metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "power_demand")
  |> filter(fn: (r) => r["_field"] == "demand_kw")
  |> elapsed()
  |> filter(fn: (r) => r["elapsed"] > 300)
  |> yield(name: "data_gaps")
EOF

# Execute the queries
echo "Checking InfluxDB data..."
echo ""

# Query 1: Count recent data points
echo "1. Data Point Counts (last hour):"
echo "---------------------------------"
kubectl exec -n demo-app deployment/influxdb -- influx query 'from(bucket: "power_metrics") |> range(start: -1h) |> filter(fn: (r) => r["_measurement"] == "power_demand" or r["_measurement"] == "power_summation") |> group(columns: ["_measurement"]) |> count()' || echo "Query failed"
echo ""

# Query 2: Last power demand reading with timestamp
echo "2. Most Recent Power Demand:"
echo "----------------------------"
kubectl exec -n demo-app deployment/influxdb -- influx query 'from(bucket: "power_metrics") |> range(start: -1h) |> filter(fn: (r) => r["_measurement"] == "power_demand") |> filter(fn: (r) => r["_field"] == "demand_kw") |> last()' || echo "Query failed"
echo ""

# Query 3: Check for any data in the last 10 minutes
echo "3. Any Data in Last 10 Minutes:"
echo "--------------------------------"
kubectl exec -n demo-app deployment/influxdb -- influx query 'from(bucket: "power_metrics") |> range(start: -10m) |> filter(fn: (r) => r["_measurement"] == "power_demand" or r["_measurement"] == "power_summation") |> count()' || echo "Query failed"
echo ""

# Clean up
rm -f /tmp/check-influx-data.flux

echo ""
echo "=== Additional Checks ==="
echo ""

# Check if EAGLE is still sending data
echo "4. Recent HTTP Requests to Flask:"
echo "---------------------------------"
kubectl logs -n demo-app deployment/flask-app --tail=200 | grep -E "POST /api/power-data|Received power data" | tail -10
echo ""

# Check for any errors in the last hour
echo "5. Recent Errors in Flask Logs:"
echo "--------------------------------"
kubectl logs -n demo-app deployment/flask-app --since=1h | grep -i error | tail -10
echo ""

echo "=== Troubleshooting Tips ==="
echo ""
echo "If no recent data:"
echo "1. Check EAGLE device status and configuration"
echo "2. Verify EAGLE can reach http://119.9.118.22:30500"
echo "3. Check if Flask pod restarted: kubectl get pods -n demo-app"
echo "4. Restart Flask if needed: kubectl rollout restart deployment/flask-app -n demo-app"
echo "5. Check EAGLE logs/status for connection errors"