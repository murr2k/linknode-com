from flask import Blueprint, request, jsonify
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import logging
from datetime import datetime
import xml.etree.ElementTree as ET

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

def parse_hex_value(hex_string):
    """Convert hex string (0x format) to integer"""
    if hex_string and hex_string.startswith('0x'):
        return int(hex_string, 16)
    return 0

@power_monitor.route('/api/power-data', methods=['POST'])
def receive_power_data():
    """
    Endpoint to receive power data from EAGLE device in XML format
    """
    try:
        # Log the incoming request
        logger.info(f"Received power data request from {request.remote_addr}")
        
        # Get raw data
        raw_data = request.data
        if not raw_data:
            logger.warning("No data provided")
            return '', 200
        
        # Log content type
        content_type = request.headers.get('Content-Type', '')
        logger.info(f"Content-Type: {content_type}")
        
        # Handle XML data
        if 'xml' in content_type.lower() or raw_data.strip().startswith(b'<'):
            try:
                # Parse XML
                root = ET.fromstring(raw_data)
                logger.info(f"Received XML message type: {root.tag}")
                
                # Extract device IDs
                device_id = root.find('DeviceMacId')
                device_id = device_id.text if device_id is not None else 'unknown'
                
                # Get timestamp
                timestamp = datetime.utcnow().isoformat() + 'Z'
                
                # Handle InstantaneousDemand
                if root.tag == 'InstantaneousDemand':
                    demand_hex = root.find('Demand').text
                    multiplier = parse_hex_value(root.find('Multiplier').text)
                    divisor = parse_hex_value(root.find('Divisor').text)
                    
                    # Calculate demand in kW
                    demand_raw = parse_hex_value(demand_hex)
                    demand_kw = (demand_raw * multiplier / divisor) if divisor > 0 else 0
                    
                    logger.info(f"Power Demand: {demand_kw} kW (raw={demand_raw}, mult={multiplier}, div={divisor})")
                    
                    if write_api and demand_kw >= 0:
                        point = Point("power_metrics") \
                            .tag("device_id", device_id) \
                            .field("demand_kw", demand_kw) \
                            .time(timestamp, WritePrecision.NS)
                        
                        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                        logger.info(f"Stored power demand: {demand_kw} kW")
                
                # Handle CurrentSummationDelivered
                elif root.tag == 'CurrentSummationDelivered':
                    summation_hex = root.find('SummationDelivered').text
                    multiplier = parse_hex_value(root.find('Multiplier').text)
                    divisor = parse_hex_value(root.find('Divisor').text)
                    
                    # Calculate total in kWh
                    total_raw = parse_hex_value(summation_hex)
                    total_kwh = (total_raw * multiplier / divisor) if divisor > 0 else 0
                    
                    logger.info(f"Total Delivered: {total_kwh} kWh")
                    
                    if write_api:
                        point = Point("power_metrics") \
                            .tag("device_id", device_id) \
                            .field("total_delivered_kwh", total_kwh) \
                            .time(timestamp, WritePrecision.NS)
                        
                        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                        logger.info(f"Stored total delivered: {total_kwh} kWh")
                
                # Handle PriceCluster
                elif root.tag == 'PriceCluster':
                    price = root.find('Price')
                    if price is not None:
                        price_hex = price.text
                        price_value = parse_hex_value(price_hex) / 10000.0  # Usually in cents/100
                        
                        if write_api:
                            point = Point("power_metrics") \
                                .tag("device_id", device_id) \
                                .field("price_usd_per_kwh", price_value) \
                                .time(timestamp, WritePrecision.NS)
                            
                            write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                            logger.info(f"Stored price: ${price_value}/kWh")
                
                else:
                    logger.info(f"Unhandled XML message type: {root.tag}")
                
                return '', 200
                
            except ET.ParseError as e:
                logger.error(f"XML parsing error: {e}")
                # Fall back to JSON parsing
        
        # Try JSON parsing as fallback
        try:
            data = request.get_json(force=True)
            logger.info(f"Parsing as JSON: {data}")
            
            # Handle the nested EAGLE JSON format
            if 'body' in data and isinstance(data['body'], list):
                device_id = data.get('deviceGuid', 'unknown')
                
                for item in data['body']:
                    data_type = item.get('dataType', '')
                    item_data = item.get('data', {})
                    
                    if data_type == 'InstantaneousDemand':
                        demand = float(item_data.get('demand', 0))
                        
                        if write_api and demand >= 0:
                            point = Point("power_metrics") \
                                .tag("device_id", device_id) \
                                .field("demand_kw", demand) \
                                .time(datetime.utcnow().isoformat() + 'Z', WritePrecision.NS)
                            
                            write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                            logger.info(f"Stored JSON power demand: {demand} kW")
            
        except Exception as e:
            logger.error(f"JSON parsing error: {e}")
        
        return '', 200
        
    except Exception as e:
        logger.error(f"Error processing power data: {e}")
        return '', 500

@power_monitor.route('/api/power-data/test', methods=['GET'])
def test_endpoint():
    """Test endpoint to verify the API is working"""
    return jsonify({
        'status': 'ok',
        'message': 'Power monitoring endpoint is active (XML/JSON support)',
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
            |> range(start: -5m)
            |> filter(fn: (r) => r["_measurement"] == "power_metrics")
            |> filter(fn: (r) => r["_field"] == "demand_kw")
            |> last()
        '''
        
        result = query_api.query(query)
        
        for table in result:
            for record in table.records:
                return jsonify({
                    'status': 'success',
                    'demand_kw': record.get_value(),
                    'device_id': record.values.get('device_id'),
                    'timestamp': record.get_time().isoformat()
                })
        
        return jsonify({
            'status': 'no_data',
            'message': 'No recent power readings'
        }), 404
        
    except Exception as e:
        logger.error(f"Error querying InfluxDB: {e}")
        return jsonify({'error': str(e)}), 500