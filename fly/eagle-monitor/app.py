#!/usr/bin/env python3
"""
Eagle-200 XML Monitor for InfluxDB
Receives XML POST data from Eagle-200 energy monitor and stores in InfluxDB
Includes data staleness monitoring with Slack alerts
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import xml.etree.ElementTree as ET
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import time
from functools import wraps
import hashlib
import base64
import re
from security_monitor import security_monitor, require_api_key_with_monitoring
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from monitor_data_staleness import DataStalenessMonitor

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

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    # Server header is handled at the web server level
    return response

# InfluxDB configuration
INFLUXDB_URL = os.getenv('INFLUXDB_URL', 'http://linknode-influxdb.internal:8086')
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN')  # Required - must be set via fly secrets
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG', 'linknode')
INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET', 'energy')

# API Authentication
API_KEY = os.getenv('EAGLE_API_KEY')  # Set via fly secrets for API endpoints
EAGLE_USERNAME = os.getenv('EAGLE_USERNAME', 'eagle')  # Basic auth username for Eagle device
EAGLE_PASSWORD = os.getenv('EAGLE_PASSWORD')  # Basic auth password for Eagle device
PUBLIC_API_ENDPOINTS = ['/health', '/']  # Endpoints that don't require auth

# Rate limiting configuration
from collections import defaultdict
from threading import Lock
import queue
import json
rate_limit_storage = defaultdict(list)
rate_limit_lock = Lock()
RATE_LIMIT = 60  # requests per minute
RATE_WINDOW = 60  # seconds

# Server-Sent Events (SSE) for real-time updates
sse_clients = []
sse_clients_lock = Lock()

# Device MAC filtering
# The Eagle-200 has two Zigbee radios that report with different MACs.
# ef68 (HAN radio) only sends empty message_cluster data - filter it out.
# ef69 (Control radio) sends all useful meter data (power, energy, price).
IGNORED_DEVICE_MACS = [
    'd8d5b9000000ef68',  # HAN radio - only sends empty message_cluster
]

# Message types that are recognized but intentionally not stored (static metadata,
# no telemetry). Acknowledged without a write and logged at DEBUG, not as "unhandled".
IGNORED_MESSAGE_TYPES = {'DeviceInfo'}

# Field tags whose values are secrets (Zigbee keys/codes) and must never be logged.
SENSITIVE_FIELD_TAGS = ('InstallCode', 'LinkKey')

# TEMPORARY diagnostic: when RAW_CAPTURE=1, log the raw (secret-redacted) payload of
# DeviceInfo and MessageCluster messages so we can read the firmware version and check
# whether the utility text channel is truly empty. Off by default; safe to leave in.
RAW_CAPTURE = os.getenv('RAW_CAPTURE', '') == '1'

# BC Hydro Tiered Rate Configuration
# https://app.bchydro.com/accounts-billing/rates-energy-use/electricity-rates/residential-rates/tiered.html
TIER1_RATE = float(os.getenv('TIER1_RATE', '0.1172'))  # $/kWh - below threshold
TIER2_RATE = float(os.getenv('TIER2_RATE', '0.1408'))  # $/kWh - above threshold
DAILY_THRESHOLD_KWH = float(os.getenv('DAILY_THRESHOLD_KWH', '22.1918'))  # kWh/day for tier boundary
BILLING_CYCLE_START_DAY = int(os.getenv('BILLING_CYCLE_START_DAY', '26'))  # Day of month billing resets (BC Hydro)
BASIC_CHARGE_DAILY = float(os.getenv('BASIC_CHARGE_DAILY', '0.2330'))  # $/day fixed charge

# Statistics
stats = {
    'total_requests': 0,
    'successful_writes': 0,
    'failed_writes': 0,
    'filtered_requests': 0,
    'last_data_received': None,
    'previous_data_received': None,
    'packet_interval_ms': None,
    'last_power_reading': None,
    'start_time': datetime.now(timezone.utc).isoformat(),
    'packets_today': 0,
    'packets_today_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
    # Reliability heartbeat from the Pi bypass (uptime the dashboard displays).
    # Populated out-of-band by BypassStatus messages; None until the first arrives.
    'bypass_status': None,
}

# Initialize data staleness monitor
monitor = DataStalenessMonitor(
    slack_webhook=os.getenv('SLACK_WEBHOOK_URL'),
    stale_threshold_minutes=int(os.getenv('STALE_THRESHOLD_MINUTES', '5')),
    pushover_token=os.getenv('PUSHOVER_API_TOKEN'),
    pushover_user=os.getenv('PUSHOVER_USER_KEY')
)

# Background scheduler for monitoring
scheduler = None

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

def check_basic_auth():
    """Check HTTP Basic Authentication"""
    auth = request.authorization
    if not auth:
        return False
    
    # Check if credentials match
    return auth.username == EAGLE_USERNAME and auth.password == EAGLE_PASSWORD

def require_auth(f):
    """Decorator to require authentication (Basic Auth for Eagle, API key for others)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip auth for public endpoints
        if request.endpoint in PUBLIC_API_ENDPOINTS or request.path in PUBLIC_API_ENDPOINTS:
            return f(*args, **kwargs)
        
        # For Eagle webhook endpoint, use Basic Auth
        if request.endpoint == 'eagle_webhook':
            # Check if Basic Auth password is configured
            if not EAGLE_PASSWORD:
                logger.warning("EAGLE_PASSWORD not configured - authentication disabled for Eagle")
                return f(*args, **kwargs)
            
            # Check Basic Auth
            if not check_basic_auth():
                # Return 401 with WWW-Authenticate header for Basic Auth
                return jsonify({'error': 'Authentication required'}), 401, {
                    'WWW-Authenticate': 'Basic realm="Eagle Monitor"'
                }
        else:
            # For API endpoints, use API key
            api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
            
            if not API_KEY:
                # If no API key is configured, allow access. Logged at DEBUG to avoid
                # per-request noise from the dashboard/Grafana polling /api/stats.
                logger.debug("API_KEY not configured - authentication disabled for API")
                return f(*args, **kwargs)
            
            if not api_key:
                return jsonify({'error': 'API key required'}), 401
            
            if api_key != API_KEY:
                return jsonify({'error': 'Invalid API key'}), 401
        
        # Check rate limit
        auth_id = request.authorization.username if request.authorization else (request.headers.get('X-API-Key') or request.remote_addr)
        client_id = request.remote_addr + ':' + auth_id
        if not check_rate_limit(client_id):
            # Record rate limit violation for security monitoring
            security_monitor.record_rate_limit_violation(request.remote_addr)
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        return f(*args, **kwargs)
    return decorated_function

# Keep the old decorator for backward compatibility
require_api_key = require_auth

def broadcast_power_update(power_w, timestamp, packet_interval_ms=None):
    """Broadcast power update to all connected SSE clients"""
    data = json.dumps({
        'power_w': power_w,
        'timestamp': timestamp,
        'packet_interval_ms': packet_interval_ms
    })
    message = f"data: {data}\n\n"

    with sse_clients_lock:
        # Remove dead clients and send to live ones
        dead_clients = []
        for client_queue in sse_clients:
            try:
                client_queue.put_nowait(message)
            except:
                dead_clients.append(client_queue)

        for dead in dead_clients:
            sse_clients.remove(dead)

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

def start_data_monitor():
    """Start the data staleness monitoring background task"""
    global scheduler

    if scheduler is None:
        scheduler = BackgroundScheduler()

        # Add job to check data freshness every 5 minutes
        scheduler.add_job(
            check_data_health,
            IntervalTrigger(minutes=5),
            id='data_staleness_check',
            name='Check data staleness',
            replace_existing=True
        )

        scheduler.start()
        logger.info("Data staleness monitor started (checks every 5 minutes)")

def check_data_health():
    """Background job to check if data is still arriving"""
    try:
        current_status, transitioned = monitor.check_data_freshness(stats)
        if transitioned:
            logger.info(f"Data health status changed to: {current_status}")
    except Exception as e:
        logger.error(f"Error in data health check: {e}")

# Eagle/Zigbee Smart Energy timestamps count seconds from 2000-01-01 UTC,
# not the Unix epoch (1970-01-01). This is the gap between the two.
ZIGBEE_EPOCH_OFFSET = 946684800  # seconds from 1970-01-01 to 2000-01-01 UTC

def _dump_message_redacted(elem):
    """Serialize an XML message for logging, masking any secret-bearing fields."""
    try:
        raw = ET.tostring(elem, encoding='unicode').strip()
    except Exception:
        return '<unserializable>'
    for tag in SENSITIVE_FIELD_TAGS:
        raw = re.sub(rf'(<{tag}>)[^<]*(</{tag}>)', r'\1***REDACTED***\2', raw)
    return raw

def parse_eagle_xml(xml_data):
    """Parse Eagle-200 XML data"""
    try:
        root = ET.fromstring(xml_data)
        
        # Extract common fields
        device_mac = root.findtext('.//DeviceMacId', '').replace('0x', '')
        meter_mac = root.findtext('.//MeterMacId', '').replace('0x', '')
        timestamp = root.findtext('.//TimeStamp', '')
        now = datetime.now(timezone.utc)

        # Decode the Zigbee-epoch timestamp; missing/non-numeric values fall back to now.
        try:
            timestamp_int = int(timestamp, 16) if timestamp.startswith('0x') else int(timestamp)
            dt = datetime.fromtimestamp(timestamp_int + ZIGBEE_EPOCH_OFFSET, tz=timezone.utc)
        except (ValueError, TypeError, OSError, OverflowError):
            dt = now

        # Safety net for genuinely implausible timestamps (more than a year off).
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
        
        # 2b. BypassStatus - reliability heartbeat from our Pi failover uploader.
        # Not a Rainforest telemetry type: it carries the bypass's own uptime numbers
        # so the dashboard can show real availability. Stashed in stats, never written
        # to the time-series (see eagle_webhook), so it can't distort energy data.
        elif root.find('.//BypassStatus') is not None:
            elem = root.find('.//BypassStatus')
            data['message_type'] = 'bypass_status'

            def _num(tag, cast):
                raw = elem.findtext(tag, '')
                if raw is None or raw == '':
                    return None
                try:
                    return cast(raw)
                except (ValueError, TypeError):
                    return None

            data['bypass'] = {
                'data_uptime_pct': _num('DataUptimePct', float),
                'device_uptime_pct': _num('DeviceUptimePct', float),
                'observed_seconds': _num('ObservedSeconds', int),
                'outage_count': _num('OutageCount', int),
                'total_outage_seconds': _num('TotalOutageSeconds', int),
                'worst_outage_seconds': _num('WorstOutageSeconds', int),
                'readings_rescued': _num('ReadingsRescued', int),
                'interval_s': _num('IntervalSeconds', int),
            }

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
        
        # Unhandled message types: recognized metadata that carries no telemetry
        # (e.g. DeviceInfo) is acknowledged quietly; anything else is logged with its
        # payload (secrets redacted) so it can be inspected before deciding what to do.
        else:
            for child in root:
                if child.tag != 'rainforest':
                    if child.tag in IGNORED_MESSAGE_TYPES:
                        data['message_type'] = child.tag.lower()
                        logger.debug(f"Ignoring metadata message type: {child.tag}")
                    else:
                        data['message_type'] = 'unknown_' + child.tag.lower()
                        logger.warning(f"Unhandled message type {child.tag}: {_dump_message_redacted(child)}")
                    break
        
        return data
        
    except Exception as e:
        logger.error(f"Error parsing XML: {e}")
        logger.debug(f"XML data: {xml_data}")
        return None

@app.route('/eagle', methods=['POST'])
@require_auth
def eagle_webhook():
    """Handle Eagle-200 XML POST requests"""
    global stats
    
    stats['total_requests'] += 1
    
    try:
        # Get XML data
        xml_data = request.data.decode('utf-8')
        logger.debug(f"Received XML: {xml_data[:200]}...")

        # TEMPORARY (RAW_CAPTURE=1): dump DeviceInfo/MessageCluster payloads verbatim,
        # before the ignored-MAC filter below drops ef68, so we see the ef68 messages
        # too. Secrets are redacted. Remove this block once the questions are answered.
        if RAW_CAPTURE and ('<DeviceInfo' in xml_data or '<MessageCluster' in xml_data):
            try:
                _root = ET.fromstring(xml_data)
                _mac = _root.findtext('.//DeviceMacId', '')
                # Collapse to one physical line: concurrent workers logging multi-line
                # XML interleave in the stream and become unreadable otherwise.
                _flat = ' '.join(_dump_message_redacted(_root).split())
                logger.info(f"RAWCAP mac={_mac} {_flat}")
            except Exception as _e:
                logger.info(f"RAWCAP parse-failed: {_e}")

        # Parse XML
        data = parse_eagle_xml(xml_data)
        if not data:
            return jsonify({'error': 'Failed to parse XML'}), 400

        # Filter out ignored device MACs (e.g., ef68 which only sends empty messages)
        device_mac = data.get('device_mac', '')
        if device_mac in IGNORED_DEVICE_MACS:
            stats['filtered_requests'] += 1
            logger.debug(f"Filtered message from ignored device: {device_mac}")
            return jsonify({'status': 'filtered', 'reason': 'ignored_device_mac'}), 200

        # Reliability heartbeat from the Pi bypass: record the uptime numbers for the
        # dashboard and acknowledge. Deliberately returns BEFORE the InfluxDB write and
        # the last_data_received update below -- it must not be mistaken for fresh meter
        # data, or it would mask the staleness/Pushover alerting during a real outage.
        if data.get('message_type') == 'bypass_status':
            b = data.get('bypass', {})
            b['updated_at'] = datetime.now(timezone.utc).isoformat()
            stats['bypass_status'] = b
            logger.info(f"Bypass heartbeat: data_uptime={b.get('data_uptime_pct')}% "
                        f"device_uptime={b.get('device_uptime_pct')}% "
                        f"outages={b.get('outage_count')}")
            return jsonify({'status': 'ok', 'type': 'bypass_status'}), 200

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

        # Messages with no storable fields (DeviceInfo, BillingPeriodList, TimeCluster,
        # BlockPriceDetail, etc.) carry only metadata. A fieldless InfluxDB write always
        # fails, so acknowledge them without attempting one.
        storable_fields = ('power_w', 'energy_delivered_kwh', 'energy_received_kwh',
                           'price_per_kwh', 'link_strength', 'message_text')
        if not any(field in data for field in storable_fields):
            stats['filtered_requests'] += 1
            logger.debug(f"No storable fields for message_type={data.get('message_type')}; acknowledged without write")
            return jsonify({'status': 'ignored', 'reason': 'no_storable_fields',
                            'message_type': data.get('message_type')}), 200

        # Write to InfluxDB
        if write_api:
            try:
                write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                stats['successful_writes'] += 1

                # Track daily packets (reset at midnight UTC)
                now = datetime.now(timezone.utc)
                today = now.strftime('%Y-%m-%d')
                if stats['packets_today_date'] != today:
                    stats['packets_today'] = 0
                    stats['packets_today_date'] = today
                stats['packets_today'] += 1

                # Calculate packet interval
                if stats['last_data_received']:
                    previous = datetime.fromisoformat(stats['last_data_received'].replace('Z', '+00:00'))
                    interval = (now - previous).total_seconds() * 1000  # milliseconds
                    stats['packet_interval_ms'] = round(interval)
                    stats['previous_data_received'] = stats['last_data_received']
                stats['last_data_received'] = now.isoformat()

                # Broadcast to SSE clients for real-time updates (after interval is calculated)
                if 'power_w' in data:
                    broadcast_power_update(
                        data['power_w'],
                        data['timestamp'].isoformat(),
                        stats.get('packet_interval_ms')
                    )

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

def get_billing_period_start():
    """Calculate the start of the current billing period based on BILLING_CYCLE_START_DAY"""
    now = datetime.now(timezone.utc)
    # If we're past the billing start day this month, use this month
    # Otherwise, use the previous month
    if now.day >= BILLING_CYCLE_START_DAY:
        billing_start = now.replace(day=BILLING_CYCLE_START_DAY, hour=0, minute=0, second=0, microsecond=0)
    else:
        # Go to previous month
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month = first_of_month - timedelta(days=1)
        billing_start = last_month.replace(day=BILLING_CYCLE_START_DAY, hour=0, minute=0, second=0, microsecond=0)
    return billing_start


def calculate_tiered_cost(energy_kwh, days_in_period, tier1_rate=None, tier2_rate=None):
    """
    Calculate cost using BC Hydro tiered rate structure.

    Args:
        energy_kwh: Total energy consumed in kWh
        days_in_period: Number of days in the billing period
        tier1_rate: Rate for consumption below threshold (default: TIER1_RATE)
        tier2_rate: Rate for consumption above threshold (default: TIER2_RATE)

    Returns:
        dict with cost breakdown
    """
    tier1 = tier1_rate or TIER1_RATE
    tier2 = tier2_rate or TIER2_RATE

    # Calculate threshold based on days in period
    threshold_kwh = days_in_period * DAILY_THRESHOLD_KWH

    # Calculate tiered costs
    if energy_kwh <= threshold_kwh:
        tier1_kwh = energy_kwh
        tier2_kwh = 0
        tier1_cost = tier1_kwh * tier1
        tier2_cost = 0
    else:
        tier1_kwh = threshold_kwh
        tier2_kwh = energy_kwh - threshold_kwh
        tier1_cost = tier1_kwh * tier1
        tier2_cost = tier2_kwh * tier2

    # Basic charge
    basic_charge = days_in_period * BASIC_CHARGE_DAILY

    total_cost = tier1_cost + tier2_cost + basic_charge

    return {
        'threshold_kwh': round(threshold_kwh, 2),
        'tier1_kwh': round(tier1_kwh, 2),
        'tier2_kwh': round(tier2_kwh, 2),
        'tier1_cost': round(tier1_cost, 2),
        'tier2_cost': round(tier2_cost, 2),
        'basic_charge': round(basic_charge, 2),
        'total_cost': round(total_cost, 2),
        'tier1_rate': tier1,
        'tier2_rate': tier2
    }


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

    # Count active SSE viewers
    with sse_clients_lock:
        active_viewers = len(sse_clients)

    result = {
        'current_power': stats.get('last_power_reading', 0),
        'min_24h': 0,
        'max_24h': 0,
        'avg_24h': 0,
        'cost_24h': 0,
        'price_per_kwh': 0,
        'last_update': stats.get('last_data_received'),
        'active_viewers': active_viewers,
        'packet_interval_ms': stats.get('packet_interval_ms'),
        'packets_today': stats.get('packets_today', 0),
        # Rolling 24h completeness: readings received vs expected at the report rate.
        # Populated from InfluxDB below; None if the DB is unreachable.
        'samples_24h': None,
        # Live uptime from the Pi bypass heartbeat (None until the first arrives).
        'bypass_status': stats.get('bypass_status'),
        'monitor_stats': stats,
        # Billing period info (tiered rates)
        'billing_period': {
            'start': None,
            'days': 0,
            'energy_kwh': 0,
            'tiered_cost': None
        }
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
            
            # Get min (group() aggregates across all device_mac series)
            min_query = query + '|> group() |> min()'
            min_result = query_api.query(org=INFLUXDB_ORG, query=min_query)
            if min_result and min_result[0].records:
                result['min_24h'] = min_result[0].records[0].get_value()

            # Get max
            max_query = query + '|> group() |> max()'
            max_result = query_api.query(org=INFLUXDB_ORG, query=max_query)
            if max_result and max_result[0].records:
                result['max_24h'] = max_result[0].records[0].get_value()

            # Get mean
            avg_query = query + '|> group() |> mean()'
            avg_result = query_api.query(org=INFLUXDB_ORG, query=avg_query)
            if avg_result and avg_result[0].records:
                result['avg_24h'] = avg_result[0].records[0].get_value()

            # Rolling-window completeness: how many meter readings actually arrived vs
            # how many should have at the report rate. "received" = stored power_w
            # (InstantaneousDemand) points in the window; "expected" = window / interval.
            # Interval source, in priority: the Pi's own heartbeat, then SAMPLE_INTERVAL_SEC
            # env, then 30s. This auto-adjusts if the Pi's report rate changes.
            count_query = query + '|> group() |> count()'
            count_result = query_api.query(org=INFLUXDB_ORG, query=count_query)
            received = 0
            if count_result and count_result[0].records:
                received = int(count_result[0].records[0].get_value() or 0)
            bypass = stats.get('bypass_status') or {}
            interval_s = bypass.get('interval_s') or int(os.getenv('SAMPLE_INTERVAL_SEC', '30'))
            interval_s = interval_s if interval_s and interval_s > 0 else 30
            expected = round(hours * 3600 / interval_s)
            result['samples_24h'] = {
                'received': min(received, expected),   # clamp jitter so it never exceeds 100%
                'expected': expected,
                'interval_s': interval_s,
                'window_hours': hours,
            }

            # Get current electricity rate from InfluxDB (reported by Eagle from utility)
            price_query = f'''
            from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: -{hours}h)
                |> filter(fn: (r) => r["_measurement"] == "energy_monitor")
                |> filter(fn: (r) => r["_field"] == "price_per_kwh")
                |> group()
                |> last()
            '''
            price_result = query_api.query(org=INFLUXDB_ORG, query=price_query)
            if price_result and price_result[0].records:
                result['price_per_kwh'] = price_result[0].records[0].get_value()

            # Calculate cost using avg power * hours * actual rate from utility (simple estimate)
            if result['avg_24h'] > 0 and result['price_per_kwh'] > 0:
                kwh = (result['avg_24h'] / 1000) * hours  # Convert W to kW and multiply by hours
                result['cost_24h'] = round(kwh * result['price_per_kwh'], 2)

            # Calculate billing period with tiered rates
            billing_start = get_billing_period_start()
            now = datetime.now(timezone.utc)
            days_in_period = (now - billing_start).days + 1  # Include today

            result['billing_period']['start'] = billing_start.isoformat()
            result['billing_period']['days'] = days_in_period

            # Query cumulative energy for billing period using integral
            billing_energy_query = f'''
            from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: {billing_start.strftime("%Y-%m-%dT%H:%M:%SZ")})
                |> filter(fn: (r) => r["_measurement"] == "energy_monitor")
                |> filter(fn: (r) => r["_field"] == "power_w")
                |> integral(unit: 1h)
                |> group()
                |> sum()
                |> map(fn: (r) => ({{r with _value: r._value / 1000.0}}))
            '''
            energy_result = query_api.query(org=INFLUXDB_ORG, query=billing_energy_query)
            if energy_result and energy_result[0].records:
                energy_kwh = energy_result[0].records[0].get_value()
                result['billing_period']['energy_kwh'] = round(energy_kwh, 2)

                # Calculate tiered cost using Eagle-reported Tier 1 rate if available
                tier1_rate = result['price_per_kwh'] if result['price_per_kwh'] > 0 else TIER1_RATE
                tiered = calculate_tiered_cost(energy_kwh, days_in_period, tier1_rate=tier1_rate)
                result['billing_period']['tiered_cost'] = tiered

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
            '/api/stream': 'GET - Real-time power updates (SSE)',
            '/health': 'GET - Health check',
            '/api/security/stats': 'GET - Security monitoring statistics'
        }
    }), 200

@app.route('/api/stream', methods=['GET'])
def power_stream():
    """Server-Sent Events endpoint for real-time power updates"""
    from flask import Response

    def generate():
        # Create a queue for this client
        client_queue = queue.Queue(maxsize=10)

        with sse_clients_lock:
            sse_clients.append(client_queue)

        try:
            # Send initial connection message
            yield "data: {\"connected\": true}\n\n"

            # Send current power reading if available
            if stats.get('last_power_reading') is not None:
                initial = json.dumps({
                    'power_w': stats['last_power_reading'],
                    'timestamp': stats.get('last_data_received')
                })
                yield f"data: {initial}\n\n"

            # Stream updates as they arrive
            while True:
                try:
                    # Wait for new data with timeout (keeps connection alive)
                    message = client_queue.get(timeout=30)
                    yield message
                except queue.Empty:
                    # Send keepalive comment to prevent connection timeout
                    yield ": keepalive\n\n"

        except GeneratorExit:
            # Client disconnected
            pass
        finally:
            with sse_clients_lock:
                if client_queue in sse_clients:
                    sse_clients.remove(client_queue)

    response = Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering
        }
    )
    return response


@app.route('/api/security/stats', methods=['GET'])
@require_api_key
def get_security_stats():
    """Get security monitoring statistics (requires special admin API key)"""
    # Check for admin API key
    admin_key = os.getenv('ADMIN_API_KEY')
    provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    
    if not admin_key or provided_key != admin_key:
        return jsonify({'error': 'Admin access required'}), 403
    
    stats_result = security_monitor.get_security_stats()
    return jsonify(stats_result), 200

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

    # Start the data staleness monitor
    start_data_monitor()

    # Run Flask app
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)