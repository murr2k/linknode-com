#!/usr/bin/env python3
"""
Eagle-200 XML Monitor for InfluxDB
Receives XML POST data from Eagle-200 energy monitor and stores in InfluxDB
"""

import os
import logging
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
import xml.etree.ElementTree as ET
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import time
from functools import wraps
import hashlib
from security_monitor import security_monitor, require_api_key_with_monitoring

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
# Configure CORS with specific origins
CORS(app, origins=[
    "https://linknode.com",
    "https://linknode-grafana.fly.dev",
    "https://linknode-web.fly.dev"
])

# InfluxDB configuration
INFLUXDB_URL = os.getenv('INFLUXDB_URL', 'http://linknode-influxdb.internal:8086')
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN')  # Required - must be set via fly secrets
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG', 'linknode')
INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET', 'energy')

# API Authentication
API_KEY = os.getenv('EAGLE_API_KEY')  # Set via fly secrets
PUBLIC_API_ENDPOINTS = ['/health', '/']  # Endpoints that don't require auth

# Rate limiting configuration
from collections import defaultdict
from threading import Lock
rate_limit_storage = defaultdict(list)
rate_limit_lock = Lock()
RATE_LIMIT = 60  # requests per minute
RATE_WINDOW = 60  # seconds

# Statistics
stats = {
    'total_requests': 0,
    'successful_writes': 0,
    'failed_writes': 0,
    'last_data_received': None,
    'last_power_reading': None,
    'start_time': datetime.now(timezone.utc).isoformat()
}

# Initialize InfluxDB client
influx_client = None
write_api = None

def check_rate_limit(identifier):
    """Check if request exceeds rate limit"""
    current_time = time.time()
    with rate_limit_lock:
        # Clean old entries
        rate_limit_storage[identifier] = [
            timestamp for timestamp in rate_limit_storage[identifier]
            if current_time - timestamp < RATE_WINDOW
        ]
        
        # Check rate limit
        if len(rate_limit_storage[identifier]) >= RATE_LIMIT:
            return False
        
        # Add current request
        rate_limit_storage[identifier].append(current_time)
        return True

def require_api_key(f):
    """Decorator to require API key for endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip auth for public endpoints
        if request.endpoint in PUBLIC_API_ENDPOINTS or request.path in PUBLIC_API_ENDPOINTS:
            return f(*args, **kwargs)
        
        # Check for API key
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        if not API_KEY:
            # If no API key is configured, log warning but allow access
            logger.warning("API_KEY not configured - authentication disabled")
            return f(*args, **kwargs)
        
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        if api_key != API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        
        # Check rate limit
        client_id = request.remote_addr + ':' + api_key
        if not check_rate_limit(client_id):
            # Record rate limit violation for security monitoring
            security_monitor.record_rate_limit_violation(request.remote_addr)
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        return f(*args, **kwargs)
    return decorated_function

def init_influxdb():
    """Initialize InfluxDB connection"""
    global influx_client, write_api
    try:
        influx_client = InfluxDBClient(
            url=INFLUXDB_URL,
            token=INFLUXDB_TOKEN,
            org=INFLUXDB_ORG,
            timeout=30_000
        )
        write_api = influx_client.write_api(write_options=SYNCHRONOUS)
        logger.info(f"Connected to InfluxDB at {INFLUXDB_URL}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to InfluxDB: {e}")
        return False

def parse_eagle_xml(xml_data):
    """Parse Eagle-200 XML data"""
    try:
        root = ET.fromstring(xml_data)
        
        # Extract common fields
        device_mac = root.findtext('.//DeviceMacId', '').replace('0x', '')
        meter_mac = root.findtext('.//MeterMacId', '').replace('0x', '')
        timestamp = root.findtext('.//TimeStamp', '')
        
        # Parse timestamp (Eagle sends as hex seconds since epoch)
        if timestamp.startswith('0x'):
            timestamp_int = int(timestamp, 16)
        else:
            timestamp_int = int(timestamp)
        
        # Convert to datetime
        dt = datetime.fromtimestamp(timestamp_int, tz=timezone.utc)
        
        # Check if timestamp is reasonable (not more than 1 year in the past or future)
        now = datetime.now(timezone.utc)
        one_year = 365 * 24 * 60 * 60  # seconds
        if abs((now - dt).total_seconds()) > one_year:
            logger.warning(f"Unreasonable timestamp from Eagle: {dt}, using current time instead")
            dt = now
        
        # Extract power data based on message type
        data = {
            'device_mac': device_mac,
            'meter_mac': meter_mac,
            'timestamp': dt
        }
        
        # Handle different message types
        # 1. InstantaneousDemand - Current power usage
        if root.find('.//InstantaneousDemand') is not None:
            elem = root.find('.//InstantaneousDemand')
            demand = elem.findtext('Demand', '')
            multiplier = elem.findtext('Multiplier', '1')
            divisor = elem.findtext('Divisor', '1')
            
            # Convert hex values
            demand_val = int(demand, 16) if demand.startswith('0x') else int(demand)
            mult_val = int(multiplier, 16) if multiplier.startswith('0x') else int(multiplier)
            div_val = int(divisor, 16) if divisor.startswith('0x') else int(divisor)
            
            # Calculate actual power in watts
            if div_val != 0:
                power_kw = (demand_val * mult_val) / div_val
                data['power_w'] = power_kw * 1000  # Convert to watts
                data['message_type'] = 'instantaneous_demand'
        
        # 2. CurrentSummationDelivered - Total energy consumed
        # Note: Eagle devices typically report energy in Wh (watt-hours), not kWh
        elif root.find('.//CurrentSummationDelivered') is not None or root.find('.//CurrentSummation') is not None:
            elem = root.find('.//CurrentSummationDelivered')
            if elem is None:
                elem = root.find('.//CurrentSummation')
            summation = elem.findtext('SummationDelivered', '')
            summation_received = elem.findtext('SummationReceived', '')
            multiplier = elem.findtext('Multiplier', '1')
            divisor = elem.findtext('Divisor', '1')
            
            # Convert hex values
            if summation:
                delivered_val = int(summation, 16) if summation.startswith('0x') else int(summation)
                mult_val = int(multiplier, 16) if multiplier.startswith('0x') else int(multiplier)
                div_val = int(divisor, 16) if divisor.startswith('0x') else int(divisor)
                
                # Calculate actual energy in kWh
                # Note: Check your Eagle device settings - some report in Wh, others in kWh
                if div_val != 0:
                    data['energy_delivered_kwh'] = (delivered_val * mult_val) / div_val
                    data['message_type'] = 'current_summation_delivered'
            
            # Handle energy received (for solar)
            if summation_received:
                received_val = int(summation_received, 16) if summation_received.startswith('0x') else int(summation_received)
                if div_val != 0:
                    data['energy_received_kwh'] = (received_val * mult_val) / div_val
        
        # 3. TimeCluster - Time synchronization
        elif root.find('.//TimeCluster') is not None:
            elem = root.find('.//TimeCluster')
            utc_time = elem.findtext('UTCTime', '')
            local_time = elem.findtext('LocalTime', '')
            data['message_type'] = 'time_cluster'
            if utc_time:
                data['utc_time'] = int(utc_time, 16) if utc_time.startswith('0x') else int(utc_time)
            if local_time:
                data['local_time'] = int(local_time, 16) if local_time.startswith('0x') else int(local_time)
        
        # 4. NetworkInfo - Network status
        elif root.find('.//NetworkInfo') is not None:
            elem = root.find('.//NetworkInfo')
            data['message_type'] = 'network_info'
            data['link_strength'] = elem.findtext('LinkStrength', '')
            data['status'] = elem.findtext('Status', '')
        
        # 5. PriceCluster - Pricing information
        elif root.find('.//PriceCluster') is not None:
            elem = root.find('.//PriceCluster')
            price = elem.findtext('Price', '')
            trailing_digits = elem.findtext('TrailingDigits', '2')
            data['message_type'] = 'price_cluster'
            if price:
                price_val = int(price, 16) if price.startswith('0x') else int(price)
                digits = int(trailing_digits, 16) if trailing_digits.startswith('0x') else int(trailing_digits)
                data['price_per_kwh'] = price_val / (10 ** digits)
        
        # 6. MessageCluster - Text messages from utility
        elif root.find('.//MessageCluster') is not None:
            elem = root.find('.//MessageCluster')
            data['message_type'] = 'message_cluster'
            data['message_text'] = elem.findtext('Text', '')
            data['message_id'] = elem.findtext('Id', '')
        
        # 7. BlockPriceDetail - Time of use pricing
        elif root.find('.//BlockPriceDetail') is not None:
            elem = root.find('.//BlockPriceDetail')
            data['message_type'] = 'block_price_detail'
            data['current_block'] = elem.findtext('CurrentBlock', '')
            data['current_price'] = elem.findtext('CurrentPrice', '')
        
        # Log unknown message types
        else:
            # Find the first child element of rainforest to identify message type
            for child in root:
                if child.tag != 'rainforest':
                    data['message_type'] = 'unknown_' + child.tag.lower()
                    logger.warning(f"Unknown message type: {child.tag}")
                    break
        
        return data
        
    except Exception as e:
        logger.error(f"Error parsing XML: {e}")
        logger.debug(f"XML data: {xml_data}")
        return None

@app.route('/eagle', methods=['POST'])
@require_api_key
def eagle_webhook():
    """Handle Eagle-200 XML POST requests"""
    global stats
    
    stats['total_requests'] += 1
    
    try:
        # Get XML data
        xml_data = request.data.decode('utf-8')
        logger.debug(f"Received XML: {xml_data[:200]}...")
        
        # Parse XML
        data = parse_eagle_xml(xml_data)
        if not data:
            return jsonify({'error': 'Failed to parse XML'}), 400
        
        # Create InfluxDB point
        point = Point("energy_monitor") \
            .tag("device_mac", data['device_mac']) \
            .tag("meter_mac", data['meter_mac']) \
            .tag("message_type", data.get('message_type', 'unknown')) \
            .time(data['timestamp'])
        
        # Add fields based on message type
        if 'power_w' in data:
            point.field("power_w", float(data['power_w']))
            stats['last_power_reading'] = data['power_w']
        
        if 'energy_delivered_kwh' in data:
            point.field("energy_delivered_kwh", float(data['energy_delivered_kwh']))
        
        if 'energy_received_kwh' in data:
            point.field("energy_received_kwh", float(data['energy_received_kwh']))
        
        if 'price_per_kwh' in data:
            point.field("price_per_kwh", float(data['price_per_kwh']))
        
        if 'link_strength' in data:
            point.field("link_strength", data['link_strength'])
        
        if 'message_text' in data:
            point.field("message_text", data['message_text'])
        
        # Write to InfluxDB
        if write_api:
            try:
                write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                stats['successful_writes'] += 1
                stats['last_data_received'] = datetime.now(timezone.utc).isoformat()
                logger.info(f"Written data to InfluxDB: {data}")
            except Exception as e:
                stats['failed_writes'] += 1
                logger.error(f"Failed to write to InfluxDB: {e}")
                # Still return success to Eagle device
                return jsonify({'status': 'received', 'data': data}), 200
        else:
            stats['failed_writes'] += 1
            logger.error("InfluxDB write API not initialized")
            # Still return success to Eagle device
            return jsonify({'status': 'received', 'data': data}), 200
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        stats['failed_writes'] += 1
        logger.error(f"Error processing request: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    health_status = {
        'status': 'healthy' if influx_client else 'unhealthy',
        'influxdb_connected': influx_client is not None,
        'uptime_seconds': (datetime.now(timezone.utc) - datetime.fromisoformat(stats['start_time'])).total_seconds()
    }
    
    return jsonify(health_status), 200 if health_status['status'] == 'healthy' else 503

@app.route('/api/stats', methods=['GET'])
@require_api_key
def get_stats():
    """Get power statistics with min/max/avg calculations"""
    hours = int(request.args.get('hours', 24))
    
    result = {
        'current_power': stats.get('last_power_reading', 0),
        'min_24h': 0,
        'max_24h': 0,
        'avg_24h': 0,
        'cost_24h': 0,
        'last_update': stats.get('last_data_received'),
        'monitor_stats': stats
    }
    
    # Query InfluxDB for statistics if connected
    if influx_client:
        try:
            query_api = influx_client.query_api()
            
            # Get min/max/avg for the specified time period
            query = f'''
            from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: -{hours}h)
                |> filter(fn: (r) => r["_measurement"] == "energy_monitor")
                |> filter(fn: (r) => r["_field"] == "power_w")
            '''
            
            # Get min
            min_query = query + '|> min()'
            min_result = query_api.query(org=INFLUXDB_ORG, query=min_query)
            if min_result and min_result[0].records:
                result['min_24h'] = min_result[0].records[0].get_value()
            
            # Get max
            max_query = query + '|> max()'
            max_result = query_api.query(org=INFLUXDB_ORG, query=max_query)
            if max_result and max_result[0].records:
                result['max_24h'] = max_result[0].records[0].get_value()
            
            # Get mean
            avg_query = query + '|> mean()'
            avg_result = query_api.query(org=INFLUXDB_ORG, query=avg_query)
            if avg_result and avg_result[0].records:
                result['avg_24h'] = avg_result[0].records[0].get_value()
            
            # Calculate cost (assuming $0.12 per kWh)
            if result['avg_24h'] > 0:
                kwh = (result['avg_24h'] / 1000) * hours  # Convert W to kW and multiply by hours
                result['cost_24h'] = round(kwh * 0.12, 2)  # $0.12 per kWh
                
        except Exception as e:
            logger.error(f"Error querying InfluxDB: {e}")
    
    return jsonify(result), 200

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'service': 'Eagle-200 XML Monitor',
        'version': '1.0.0',
        'endpoints': {
            '/eagle': 'POST - Receive Eagle-200 XML data',
            '/api/stats': 'GET - Monitor statistics',
            '/health': 'GET - Health check',
            '/api/security/stats': 'GET - Security monitoring statistics'
        }
    }), 200

@app.route('/api/security/stats', methods=['GET'])
@require_api_key
def get_security_stats():
    """Get security monitoring statistics (requires special admin API key)"""
    # Check for admin API key
    admin_key = os.getenv('ADMIN_API_KEY')
    provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    
    if not admin_key or provided_key != admin_key:
        return jsonify({'error': 'Admin access required'}), 403
    
    stats = security_monitor.get_security_stats()
    return jsonify(stats), 200

if __name__ == '__main__':
    # Wait for InfluxDB to be ready
    retries = 0
    while retries < 30:
        if init_influxdb():
            break
        retries += 1
        logger.warning(f"Waiting for InfluxDB... retry {retries}/30")
        time.sleep(2)
    
    if not influx_client:
        logger.error("Failed to connect to InfluxDB after 30 retries")
    
    # Run Flask app
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)