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
    Expected JSON format:
    {
        "DeviceMacId": "0xd8d5b9000000xxxx",
        "MeterMacId": "0x00135003007xxxxx",
        "TimeStamp": "2024-01-15T10:30:00Z",
        "Demand": 1.234,
        "CurrentSummation": 12345.678,
        "CurrentSummationDelivered": 12345.678,
        "CurrentSummationReceived": 0.0,
        "Multiplier": 1,
        "Divisor": 1000,
        "DigitsRight": 3,
        "DigitsLeft": 6,
        "SuppressLeadingZero": "Y"
    }
    """
    try:
        # Log the incoming request
        logger.info(f"Received power data request from {request.remote_addr}")
        
        # Parse JSON data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        logger.info(f"Power data: {data}")
        
        # Extract key metrics
        device_id = data.get('DeviceMacId', 'unknown')
        meter_id = data.get('MeterMacId', 'unknown')
        timestamp = data.get('TimeStamp', datetime.utcnow().isoformat())
        
        # Calculate actual values using multiplier and divisor
        multiplier = float(data.get('Multiplier', 1))
        divisor = float(data.get('Divisor', 1))
        
        # Current power demand in kW
        demand = float(data.get('Demand', 0)) * multiplier / divisor
        
        # Total energy consumed in kWh
        total_delivered = float(data.get('CurrentSummationDelivered', 0)) * multiplier / divisor
        total_received = float(data.get('CurrentSummationReceived', 0)) * multiplier / divisor
        net_consumption = total_delivered - total_received
        
        # Store in InfluxDB if available
        if write_api:
            try:
                # Create InfluxDB point
                point = Point("power_metrics") \
                    .tag("device_id", device_id) \
                    .tag("meter_id", meter_id) \
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
                # Continue processing even if InfluxDB write fails
        
        # Return success response
        return jsonify({
            'status': 'success',
            'message': 'Power data received',
            'metrics': {
                'device_id': device_id,
                'demand_kw': round(demand, 3),
                'net_consumption_kwh': round(net_consumption, 3),
                'timestamp': timestamp
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing power data: {e}")
        return jsonify({'error': str(e)}), 500

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