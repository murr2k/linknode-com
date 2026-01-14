#!/usr/bin/env python3
"""
Delete historical energy data from InfluxDB
"""
import os
import sys
from influxdb_client import InfluxDBClient
from datetime import datetime, timezone

# Configuration
INFLUXDB_URL = 'http://localhost:8086'  # Will use proxy
INFLUXDB_ORG = 'linknode'
INFLUXDB_BUCKET = 'energy'

# Get token from fly secrets
import subprocess
result = subprocess.run(['flyctl', 'ssh', 'console', '-a', 'linknode-eagle-monitor', '-C', 'echo $INFLUXDB_TOKEN'], 
                       capture_output=True, text=True)
if result.returncode != 0:
    print("Failed to get INFLUXDB_TOKEN")
    sys.exit(1)

INFLUXDB_TOKEN = result.stdout.strip()

print(f"Connecting to InfluxDB at {INFLUXDB_URL}")
print(f"Organization: {INFLUXDB_ORG}")
print(f"Bucket: {INFLUXDB_BUCKET}")

# Connect to InfluxDB
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
delete_api = client.delete_api()

# Delete energy data
start = datetime(1970, 1, 1, tzinfo=timezone.utc)
stop = datetime(2025, 12, 31, tzinfo=timezone.utc)

print("\nDeleting energy_delivered_kwh data...")
delete_api.delete(
    start=start,
    stop=stop,
    predicate='_measurement="energy_monitor" AND _field="energy_delivered_kwh"',
    bucket=INFLUXDB_BUCKET,
    org=INFLUXDB_ORG
)
print("✓ Deleted energy_delivered_kwh data")

print("\nDeleting energy_received_kwh data...")
delete_api.delete(
    start=start,
    stop=stop,
    predicate='_measurement="energy_monitor" AND _field="energy_received_kwh"',
    bucket=INFLUXDB_BUCKET,
    org=INFLUXDB_ORG
)
print("✓ Deleted energy_received_kwh data")

client.close()
print("\nHistorical energy data has been cleared.")
print("The Grafana dashboard should now show 0 kWh until new energy data arrives from the Eagle device.")