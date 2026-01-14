#!/bin/bash

echo "Connecting to InfluxDB to clear energy data..."

# Use flyctl ssh to execute influx commands directly
flyctl ssh console -a linknode-influxdb -C "influx delete \
  --org linknode \
  --bucket energy \
  --start 1970-01-01T00:00:00Z \
  --stop 2025-12-31T23:59:59Z \
  --predicate '_measurement=\"energy_monitor\" AND _field=\"energy_delivered_kwh\"'"

echo "Cleared energy_delivered_kwh data"

flyctl ssh console -a linknode-influxdb -C "influx delete \
  --org linknode \
  --bucket energy \
  --start 1970-01-01T00:00:00Z \
  --stop 2025-12-31T23:59:59Z \
  --predicate '_measurement=\"energy_monitor\" AND _field=\"energy_received_kwh\"'"

echo "Cleared energy_received_kwh data"
echo "Historical energy data has been cleared. The dashboard should now show 0 kWh until new data arrives."