"""
EAGLE Power Monitor XML Debug Version
Logs all incoming XML data for analysis
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, request, jsonify, Response
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import json
import os
from typing import Dict, Any, Optional

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# InfluxDB configuration
INFLUXDB_URL = os.getenv('INFLUXDB_URL', 'http://influxdb:8086')
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN', 'my-super-secret-auth-token')
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG', 'rackspace')
INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET', 'power_metrics')

# Initialize InfluxDB client
influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)


def parse_hex_value(value: str) -> int:
    """Parse hex values (with or without 0x prefix)"""
    if value is None:
        return 0
    
    value = value.strip()
    if not value:
        return 0
    
    try:
        if value.startswith('0x') or value.startswith('0X'):
            return int(value, 16)
        else:
            # Try as hex without 0x prefix
            return int(value, 16)
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse hex value: {value}")
        return 0


def parse_eagle_timestamp(hex_timestamp: str) -> datetime:
    """Parse EAGLE timestamp (seconds since 2000-01-01)"""
    try:
        # Special case for "CURRENT" timestamp
        if hex_timestamp == "CURRENT":
            return datetime.utcnow()
            
        seconds_since_2000 = parse_hex_value(hex_timestamp)
        # EAGLE epoch is 2000-01-01 00:00:00 UTC
        eagle_epoch = datetime(2000, 1, 1)
        timestamp = eagle_epoch.timestamp() + seconds_since_2000
        return datetime.fromtimestamp(timestamp)
    except Exception as e:
        logger.error(f"Failed to parse timestamp {hex_timestamp}: {e}")
        return datetime.utcnow()


def parse_xml_data(xml_data: str) -> Optional[Dict[str, Any]]:
    """Parse EAGLE XML data and extract metrics"""
    try:
        # Log the raw XML for debugging
        logger.info("=" * 60)
        logger.info("RAW XML DATA RECEIVED:")
        logger.info(xml_data[:1000])  # Log first 1000 chars
        if len(xml_data) > 1000:
            logger.info(f"... (truncated, total length: {len(xml_data)})")
        logger.info("=" * 60)
        
        # Parse XML
        root = ET.fromstring(xml_data)
        
        # Log root element
        logger.info(f"Root element: {root.tag}")
        
        # Log all child elements
        for child in root:
            logger.info(f"  Child: {child.tag} = {child.text}")
        
        # Check for different message types
        if root.tag == 'rainforest':
            # This might be a wrapper element
            logger.info("Found rainforest wrapper element")
            # Look for actual message inside
            for child in root:
                if child.tag in ['InstantaneousDemand', 'CurrentSummation', 'PriceCluster']:
                    logger.info(f"Processing inner element: {child.tag}")
                    return parse_message_element(child)
            
            # If no recognized child, log all children
            logger.warning("No recognized message type in rainforest element")
            return {
                'message_type': 'rainforest',
                'timestamp': datetime.utcnow(),
                'device_mac': '',
                'meter_mac': ''
            }
            
        elif root.tag in ['InstantaneousDemand', 'CurrentSummation', 'PriceCluster']:
            return parse_message_element(root)
        
        else:
            logger.warning(f"Unknown root element: {root.tag}")
            return None
            
    except ET.ParseError as e:
        logger.error(f"XML Parse Error: {e}")
        logger.error(f"Failed XML: {xml_data[:200]}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing XML: {e}")
        return None


def parse_message_element(element) -> Dict[str, Any]:
    """Parse a specific message element"""
    message_type = element.tag
    metrics = {
        'message_type': message_type,
        'timestamp': datetime.utcnow()
    }
    
    # Extract all fields
    fields = {}
    for child in element:
        fields[child.tag] = child.text
        logger.debug(f"  {child.tag}: {child.text}")
    
    # Common fields
    metrics['device_mac'] = fields.get('DeviceMacId', '').replace('0x', '')
    metrics['meter_mac'] = fields.get('MeterMacId', '').replace('0x', '')
    
    # Parse timestamp if available
    if 'TimeStamp' in fields:
        metrics['timestamp'] = parse_eagle_timestamp(fields['TimeStamp'])
    
    # Message-specific parsing
    if message_type == 'InstantaneousDemand':
        demand = parse_hex_value(fields.get('Demand', '0'))
        multiplier = parse_hex_value(fields.get('Multiplier', '1'))
        divisor = parse_hex_value(fields.get('Divisor', '1'))
        
        if divisor > 0:
            power_kw = (demand * multiplier) / divisor
            metrics['power_watts'] = power_kw * 1000  # Convert to watts
            logger.info(f"Parsed power: {metrics['power_watts']} W")
        else:
            metrics['power_watts'] = 0
            
    elif message_type == 'CurrentSummation':
        delivered = parse_hex_value(fields.get('SummationDelivered', '0'))
        received = parse_hex_value(fields.get('SummationReceived', '0'))
        multiplier = parse_hex_value(fields.get('Multiplier', '1'))
        divisor = parse_hex_value(fields.get('Divisor', '1'))
        
        if divisor > 0:
            metrics['energy_delivered_wh'] = (delivered * multiplier * 1000) / divisor
            metrics['energy_received_wh'] = (received * multiplier * 1000) / divisor
            logger.info(f"Energy delivered: {metrics['energy_delivered_wh']} Wh")
    
    return metrics


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'eagle-xml-monitor-debug'})


@app.route('/api/eagle', methods=['GET', 'POST', 'PUT'])
@app.route('/api/eagle/', methods=['GET', 'POST', 'PUT'])
@app.route('/eagle', methods=['GET', 'POST', 'PUT'])
@app.route('/eagle/', methods=['GET', 'POST', 'PUT'])
def eagle_endpoint():
    """Handle EAGLE data submissions"""
    if request.method == 'GET':
        return jsonify({'status': 'ready', 'message': 'Send XML data via POST'})
    
    try:
        # Get raw data
        raw_data = request.get_data(as_text=True)
        
        # Log request details
        logger.info(f"Request method: {request.method}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Content-Length: {request.content_length}")
        
        if not raw_data:
            logger.warning("Empty request body")
            return jsonify({'status': 'success', 'message': 'No data received'})
        
        # Try to parse as XML
        metrics = parse_xml_data(raw_data)
        
        if metrics:
            # Write to InfluxDB
            try:
                point = Point("eagle_power_monitor") \
                    .tag("device_mac", metrics.get('device_mac', 'unknown')) \
                    .tag("meter_mac", metrics.get('meter_mac', 'unknown')) \
                    .tag("message_type", metrics['message_type']) \
                    .time(metrics['timestamp'])
                
                # Add fields based on message type
                if 'power_watts' in metrics:
                    point = point.field("power_watts", float(metrics['power_watts']))
                if 'energy_delivered_wh' in metrics:
                    point = point.field("energy_delivered_wh", float(metrics['energy_delivered_wh']))
                if 'energy_received_wh' in metrics:
                    point = point.field("energy_received_wh", float(metrics['energy_received_wh']))
                
                write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                logger.info(f"Wrote metrics to InfluxDB: {metrics}")
                
            except Exception as e:
                logger.error(f"Failed to write to InfluxDB: {e}")
            
            return jsonify({'status': 'success', 'metrics': metrics})
        else:
            return jsonify({'status': 'success', 'message': 'Invalid XML format'})
            
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        # Return success to keep EAGLE happy
        return jsonify({'status': 'success', 'error': str(e)})


@app.route('/api/eagle/status', methods=['GET'])
@app.route('/eagle/status', methods=['GET'])
def eagle_status():
    """Status endpoint"""
    return jsonify({
        'status': 'running',
        'service': 'eagle-xml-monitor-debug',
        'timestamp': datetime.utcnow().isoformat(),
        'influxdb_url': INFLUXDB_URL,
        'influxdb_bucket': INFLUXDB_BUCKET
    })


if __name__ == '__main__':
    logger.info("Starting EAGLE XML Monitor Debug Service")
    logger.info(f"InfluxDB URL: {INFLUXDB_URL}")
    logger.info(f"InfluxDB Org: {INFLUXDB_ORG}")
    logger.info(f"InfluxDB Bucket: {INFLUXDB_BUCKET}")
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)