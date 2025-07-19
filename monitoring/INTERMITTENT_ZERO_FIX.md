# Fix for Intermittent 0.000 W Display Issue

## Problem Description

The EAGLE device sends different types of data in separate POST requests:
- **InstantaneousDemand**: Contains current power demand (kW)
- **CurrentSummation**: Contains total energy delivered/received (kWh)

When both data types were stored in the same InfluxDB measurement, CurrentSummation messages would overwrite the demand field with 0, causing intermittent 0.000 W displays in Grafana.

## Solution

The fix involves storing each data type in separate InfluxDB measurements:
- `power_demand`: Stores InstantaneousDemand data
- `power_summation`: Stores CurrentSummation data
- `power_price`: Stores Price data (if available)

## Implementation

### 1. Updated Flask Application

The power monitoring endpoint (`/api/power-data`) now stores each data type selectively:

```python
if data_type == 'InstantaneousDemand':
    point = Point("power_demand") \
        .tag("device_id", device_id) \
        .tag("data_type", "InstantaneousDemand") \
        .field("demand_kw", demand) \
        .time(timestamp, WritePrecision.NS)
    
elif data_type == 'CurrentSummation':
    point = Point("power_summation") \
        .tag("device_id", device_id) \
        .tag("data_type", "CurrentSummation") \
        .field("total_delivered_kwh", total_delivered) \
        .field("total_received_kwh", total_received) \
        .field("net_consumption_kwh", total_delivered - total_received) \
        .time(timestamp, WritePrecision.NS)
```

### 2. Updated Grafana Dashboard

All queries have been updated to use the new measurement names:

- **Current Power Demand**: Queries `power_demand` measurement
- **Total Energy Delivered**: Queries `power_summation` measurement
- **Power Over Time**: Uses `power_demand` for time series data

### 3. Files Created

1. **k8s/configmap-flask-app-selective.yaml**
   - Updated Flask application with selective storage logic
   
2. **k8s/grafana-dashboard-selective.yaml**
   - Updated dashboard queries to use separate measurements
   
3. **apply-selective-storage-fix.sh**
   - Script to apply the fix to your Kubernetes cluster

## How to Apply the Fix

Run the provided script when kubectl is configured:

```bash
./apply-selective-storage-fix.sh
```

This script will:
1. Apply the new Flask ConfigMap
2. Update the Grafana dashboard
3. Restart the Flask deployment
4. Wait for the rollout to complete
5. Show the pod status

## Verification

After applying the fix:

1. Check the Flask logs to ensure data is being stored correctly:
   ```bash
   kubectl logs -n demo-app deployment/flask-app | grep "Stored"
   ```
   
2. Access Grafana at http://119.9.118.22:30300
   - The Current Power Demand gauge should show consistent values
   - No more intermittent 0.000 W readings

3. Use the API test endpoint to verify latest readings:
   ```bash
   curl http://119.9.118.22:30500/api/power-data/latest
   ```

## Benefits

- **No data loss**: Each data type is preserved independently
- **Accurate display**: Power demand is never overwritten by summation data
- **Better organization**: Separate measurements for different data types
- **Future-proof**: Easy to add new data types without conflicts