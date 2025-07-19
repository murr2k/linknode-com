from flask import Blueprint, request, jsonify
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import logging
from datetime import datetime

# Create blueprint for power monitoring endpoints
power_monitor = Blueprint('power_monitor', __name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# InfluxDB configuration
INFLUXDB_URL = os.environ.get('INFLUXDB_URL', 'http://influxdb:8086')
INFLUXDB_TOKEN = os.environ.get('INFLUXDB_TOKEN', 'my-super-secret-auth-token')
INFLUXDB_ORG = os.environ.get('INFLUXDB_ORG', 'rackspace')
INFLUXDB_BUCKET = os.environ.get('INFLUXDB_BUCKET', 'power_metrics')

# Initialize InfluxDB client
try:
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    logger.info(f"Connected to InfluxDB at {INFLUXDB_URL}")
except Exception as e:
    logger.error(f"Failed to connect to InfluxDB: {e}")
    client = None
    write_api = None

@power_monitor.route('/api/power-data', methods=['POST'])
def receive_power_data():
    """
    Endpoint to receive power data from EAGLE device
    Handles both old and new EAGLE JSON formats
    """
    try:
        # Log the incoming request
        logger.info(f"Received power data request from {request.remote_addr}")
        
        # Parse JSON data
        data = request.get_json()
        if not data:
            logger.warning("No JSON data provided, returning empty 200")
            return '', 200
        
        logger.info(f"Power data: {data}")
        
        # Initialize variables
        demand = 0.0
        total_delivered = 0.0
        total_received = 0.0
        timestamp = datetime.utcnow().isoformat()
        device_id = 'unknown'
        
        # Check if this is the new EAGLE format with 'body' array
        if 'body' in data and isinstance(data['body'], list):
            # New format from EAGLE
            device_id = data.get('deviceGuid', 'unknown')
            timestamp_ms = data.get('timestamp', '')
            
            # Process each item in the body array
            for item in data['body']:
                data_type = item.get('dataType', '')
                item_data = item.get('data', {})
                
                if data_type == 'InstantaneousDemand':
                    # Current power demand (already in kW)
                    demand = float(item_data.get('demand', 0))
                    logger.info(f"Found InstantaneousDemand: {demand} kW")
                    
                elif data_type == 'CurrentSummation':
                    # Total energy consumed (already in kWh)
                    total_delivered = float(item_data.get('summationDelivered', 0))
                    total_received = float(item_data.get('summationReceived', 0))
                    logger.info(f"Found CurrentSummation: delivered={total_delivered} kWh, received={total_received} kWh")
                
                # Use item timestamp if available
                if 'timestamp' in item:
                    try:
                        # Convert milliseconds to datetime
                        ts_ms = int(item['timestamp'])
                        timestamp = datetime.fromtimestamp(ts_ms / 1000).isoformat() + 'Z'
                    except:
                        pass
        
        else:
            # Old format (for backward compatibility)
            device_id = data.get('DeviceMacId', 'unknown')
            timestamp = data.get('TimeStamp', datetime.utcnow().isoformat())
            
            # Calculate using multiplier/divisor
            multiplier = float(data.get('Multiplier', 1))
            divisor = float(data.get('Divisor', 1))
            
            demand = float(data.get('Demand', 0)) * multiplier / divisor
            total_delivered = float(data.get('CurrentSummationDelivered', 0)) * multiplier / divisor
            total_received = float(data.get('CurrentSummationReceived', 0)) * multiplier / divisor
        
        # Calculate net consumption
        net_consumption = total_delivered - total_received
        
        # Store in InfluxDB if we have meaningful data
        if write_api and (demand > 0 or total_delivered > 0):
            try:
                # Create InfluxDB point
                point = Point("power_metrics") \
                    .tag("device_id", device_id) \
                    .field("demand_kw", demand) \
                    .field("total_delivered_kwh", total_delivered) \
                    .field("total_received_kwh", total_received) \
                    .field("net_consumption_kwh", net_consumption) \
                    .time(timestamp, WritePrecision.NS)
                
                # Write to InfluxDB
                write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                logger.info(f"Stored power metrics: demand={demand}kW, net={net_consumption}kWh")
                
            except Exception as e:
                logger.error(f"Failed to write to InfluxDB: {e}")
        
        # Return EAGLE-compatible response
        return '', 200
        
    except Exception as e:
        logger.error(f"Error processing power data: {e}")
        return '', 500

@power_monitor.route('/api/power-data/test', methods=['GET'])
def test_endpoint():
    """Test endpoint to verify the API is working"""
    return jsonify({
        'status': 'ok',
        'message': 'Power monitoring endpoint is active',
        'influxdb_connected': client is not None,
        'timestamp': datetime.utcnow().isoformat()
    })

@power_monitor.route('/api/power-data/latest', methods=['GET'])
def get_latest_reading():
    """Get the latest power reading from InfluxDB"""
    if not client:
        return jsonify({'error': 'InfluxDB not connected'}), 503
    
    try:
        query_api = client.query_api()
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -1h)
            |> filter(fn: (r) => r["_measurement"] == "power_metrics")
            |> last()
        '''
        
        result = query_api.query(query)
        
        latest_data = {}
        for table in result:
            for record in table.records:
                field = record.get_field()
                value = record.get_value()
                latest_data[field] = value
                latest_data['timestamp'] = record.get_time().isoformat()
        
        if latest_data:
            return jsonify({
                'status': 'success',
                'data': latest_data
            })
        else:
            return jsonify({
                'status': 'no_data',
                'message': 'No power readings found in the last hour'
            }), 404
            
    except Exception as e:
        logger.error(f"Error querying InfluxDB: {e}")
        return jsonify({'error': str(e)}), 500