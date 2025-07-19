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
    Only stores the data types that are actually present in each message
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
        
        # Initialize tracking variables
        device_id = data.get('deviceGuid', 'unknown')
        timestamp = datetime.utcnow().isoformat()
        data_received = False
        
        # Check if this is the new EAGLE format with 'body' array
        if 'body' in data and isinstance(data['body'], list):
            # Process each item in the body array
            for item in data['body']:
                data_type = item.get('dataType', '')
                item_data = item.get('data', {})
                
                # Use item timestamp if available
                if 'timestamp' in item:
                    try:
                        ts_ms = int(item['timestamp'])
                        timestamp = datetime.fromtimestamp(ts_ms / 1000).isoformat() + 'Z'
                    except:
                        pass
                
                # Store each data type separately
                if data_type == 'InstantaneousDemand' and write_api:
                    # Current power demand (already in kW)
                    demand = float(item_data.get('demand', 0))
                    if demand > 0 or True:  # Store even 0 values for demand
                        try:
                            point = Point("power_demand") \
                                .tag("device_id", device_id) \
                                .tag("data_type", "InstantaneousDemand") \
                                .field("demand_kw", demand) \
                                .time(timestamp, WritePrecision.NS)
                            
                            write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                            logger.info(f"Stored InstantaneousDemand: {demand} kW")
                            data_received = True
                        except Exception as e:
                            logger.error(f"Failed to write demand to InfluxDB: {e}")
                    
                elif data_type == 'CurrentSummation' and write_api:
                    # Total energy consumed (already in kWh)
                    total_delivered = float(item_data.get('summationDelivered', 0))
                    total_received = float(item_data.get('summationReceived', 0))
                    
                    if total_delivered > 0 or total_received > 0:
                        try:
                            point = Point("power_summation") \
                                .tag("device_id", device_id) \
                                .tag("data_type", "CurrentSummation") \
                                .field("total_delivered_kwh", total_delivered) \
                                .field("total_received_kwh", total_received) \
                                .field("net_consumption_kwh", total_delivered - total_received) \
                                .time(timestamp, WritePrecision.NS)
                            
                            write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                            logger.info(f"Stored CurrentSummation: delivered={total_delivered} kWh, received={total_received} kWh")
                            data_received = True
                        except Exception as e:
                            logger.error(f"Failed to write summation to InfluxDB: {e}")
                
                elif data_type == 'Price' and write_api:
                    # Price information
                    price = float(item_data.get('price', 0))
                    price_tier = item_data.get('PriceTier', 0)
                    
                    if price > 0:
                        try:
                            point = Point("power_price") \
                                .tag("device_id", device_id) \
                                .tag("data_type", "Price") \
                                .tag("tier", str(price_tier)) \
                                .field("price_usd", price) \
                                .field("price_label", item_data.get('PriceRateLabel', 'Unknown')) \
                                .time(timestamp, WritePrecision.NS)
                            
                            write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                            logger.info(f"Stored Price: ${price} USD")
                            data_received = True
                        except Exception as e:
                            logger.error(f"Failed to write price to InfluxDB: {e}")
                
                else:
                    logger.info(f"Received {data_type} data (not stored)")
        
        else:
            # Old format fallback (for testing)
            if 'Demand' in data and write_api:
                multiplier = float(data.get('Multiplier', 1))
                divisor = float(data.get('Divisor', 1))
                demand = float(data.get('Demand', 0)) * multiplier / divisor
                
                point = Point("power_demand") \
                    .tag("device_id", device_id) \
                    .tag("data_type", "InstantaneousDemand") \
                    .field("demand_kw", demand) \
                    .time(timestamp, WritePrecision.NS)
                
                write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                data_received = True
        
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
        
        # Get latest demand
        demand_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -1h)
            |> filter(fn: (r) => r["_measurement"] == "power_demand")
            |> filter(fn: (r) => r["_field"] == "demand_kw")
            |> last()
        '''
        
        # Get latest summation
        summation_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -1h)
            |> filter(fn: (r) => r["_measurement"] == "power_summation")
            |> last()
        '''
        
        demand_result = query_api.query(demand_query)
        summation_result = query_api.query(summation_query)
        
        latest_data = {}
        
        # Process demand data
        for table in demand_result:
            for record in table.records:
                latest_data['demand_kw'] = record.get_value()
                latest_data['demand_timestamp'] = record.get_time().isoformat()
        
        # Process summation data
        for table in summation_result:
            for record in table.records:
                field = record.get_field()
                value = record.get_value()
                latest_data[field] = value
                latest_data['summation_timestamp'] = record.get_time().isoformat()
        
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