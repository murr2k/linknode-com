#!/bin/bash

echo "=== Checking Device IDs in InfluxDB ==="
echo ""

# Check all unique device IDs in power_demand
echo "1. Device IDs in power_demand measurement:"
kubectl exec -n demo-app deployment/influxdb -- influx query '
from(bucket: "power_metrics")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "power_demand")
  |> filter(fn: (r) => r["_field"] == "demand_kw")
  |> group(columns: ["device_id"])
  |> distinct(column: "device_id")
' 2>/dev/null || echo "Query failed"

echo ""
echo "2. Latest data from each device:"
kubectl exec -n demo-app deployment/influxdb -- influx query '
from(bucket: "power_metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "power_demand")
  |> filter(fn: (r) => r["_field"] == "demand_kw")
  |> last()
  |> group(columns: ["device_id"])
  |> yield(name: "latest_by_device")
' 2>/dev/null || echo "Query failed"

echo ""
echo "3. Count of records per device (last hour):"
kubectl exec -n demo-app deployment/influxdb -- influx query '
from(bucket: "power_metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "power_demand")
  |> group(columns: ["device_id"])
  |> count()
' 2>/dev/null || echo "Query failed"