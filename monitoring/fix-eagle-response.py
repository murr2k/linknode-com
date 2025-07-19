#!/usr/bin/env python3
"""
Update the Flask app to return EAGLE-compatible responses
"""

# EAGLE devices typically expect one of these response formats:
# 1. Empty 200 OK response (no body)
# 2. Simple text "OK" 
# 3. XML acknowledgment
# 4. Minimal JSON

updated_endpoint = '''
@power_monitor.route('/api/power-data', methods=['POST'])
def receive_power_data():
    """
    Endpoint to receive power data from EAGLE device
    Returns minimal response for EAGLE compatibility
    """
    try:
        # Log the incoming request headers for debugging
        logger.info(f"Received power data request from {request.remote_addr}")
        logger.info(f"Headers: {dict(request.headers)}")
        
        # Parse JSON data
        data = request.get_json()
        if not data:
            # Return empty 200 OK for EAGLE compatibility
            return '', 200
        
        logger.info(f"Power data: {data}")
        
        # Extract and process metrics (same as before)
        device_id = data.get('DeviceMacId', 'unknown')
        meter_id = data.get('MeterMacId', 'unknown')
        timestamp = data.get('TimeStamp', datetime.utcnow().isoformat())
        
        multiplier = float(data.get('Multiplier', 1))
        divisor = float(data.get('Divisor', 1))
        
        demand = float(data.get('Demand', 0)) * multiplier / divisor
        total_delivered = float(data.get('CurrentSummationDelivered', 0)) * multiplier / divisor
        total_received = float(data.get('CurrentSummationReceived', 0)) * multiplier / divisor
        net_consumption = total_delivered - total_received
        
        # Store in InfluxDB
        if write_api:
            try:
                point = Point("power_metrics") \
                    .tag("device_id", device_id) \
                    .tag("meter_id", meter_id) \
                    .field("demand_kw", demand) \
                    .field("total_delivered_kwh", total_delivered) \
                    .field("total_received_kwh", total_received) \
                    .field("net_consumption_kwh", net_consumption) \
                    .time(timestamp, WritePrecision.NS)
                
                write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                logger.info(f"Stored power metrics: demand={demand}kW, net={net_consumption}kWh")
                
            except Exception as e:
                logger.error(f"Failed to write to InfluxDB: {e}")
        
        # Return minimal response for EAGLE
        # Option 1: Empty 200 OK
        return '', 200
        
        # Option 2: Simple text OK
        # return 'OK', 200, {'Content-Type': 'text/plain'}
        
        # Option 3: Minimal JSON
        # return '{"status":"ok"}', 200, {'Content-Type': 'application/json'}
        
    except Exception as e:
        logger.error(f"Error processing power data: {e}")
        # Return empty 500 for EAGLE compatibility
        return '', 500
'''

print("EAGLE Response Fix")
print("==================")
print()
print("The EAGLE device expects a specific response format.")
print("We need to update the Flask endpoint to return a simpler response.")
print()
print("Current response: Full JSON with metrics")
print("EAGLE-compatible options:")
print("1. Empty 200 OK response (recommended)")
print("2. Simple text 'OK'")
print("3. Minimal JSON")
print()
print("To fix this, update the power_monitor.py endpoint to return:")
print("return '', 200")
print()
print("This will acknowledge receipt without sending data that might confuse EAGLE.")