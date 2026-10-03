#!/usr/bin/env python3
"""
Eagle-200 XML Monitor
Receives XML POST data from Eagle-200 energy monitor and stores it in SQLite
(store.py, on the Fly volume). Includes data staleness monitoring with
Slack/Pushover alerts.
"""

import os
import calendar
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify
from flask_cors import CORS
import xml.etree.ElementTree as ET
import time
from functools import wraps
import hashlib
import base64
import re
from security_monitor import security_monitor, require_api_key_with_monitoring
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from monitor_data_staleness import DataStalenessMonitor, WatchdogLiveness, FROZEN_REGISTER_WINDOW
import store
import dashboard

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
    "https://www.linknode.com",
    # Cloudflare Worker serving the site: production and preview-version hosts
    r"^https://([a-z0-9-]+-)?linknode-web\.[a-z0-9-]+\.workers\.dev$",
    # Local site preview (run.cmd, port from ~/.claude/port-registry.md)
    "http://localhost:8771",
    "http://127.0.0.1:8771",
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

# SQLite store. /data is the Fly volume.
DB_PATH = os.getenv('DB_PATH', '/data/energy.db')
# Retention: 5 years (43800h).
RETENTION_DAYS = int(os.getenv('RETENTION_DAYS', '1825'))

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

# BC Hydro residential tiered rate (rate schedule 1101), effective 2026-04-01:
# https://app.bchydro.com/accounts-billing/rates-energy-use/electricity-rates/residential-rates/tiered.html
# BCUC order G-42-25 holds Step 2 at 14.08 cents and raises Step 1 and the basic charge
# each April 1, so check these every April. They are the authoritative rates: the price
# the Eagle reports (PriceCluster) is not updated when BC Hydro changes rates (it still
# read 0.1172, the April 2025 Step 1, after the April 2026 change) and is only exposed as
# meter_price_per_kwh.
TIER1_RATE = float(os.getenv('TIER1_RATE', '0.1187'))  # $/kWh - Step 1, below threshold
TIER2_RATE = float(os.getenv('TIER2_RATE', '0.1408'))  # $/kWh - Step 2, above threshold
DAILY_THRESHOLD_KWH = float(os.getenv('DAILY_THRESHOLD_KWH', '22.1918'))  # kWh/day for tier boundary
BASIC_CHARGE_DAILY = float(os.getenv('BASIC_CHARGE_DAILY', '0.2344'))  # $/day basic charge
# The other lines on the bill (Jul 30, 2026): the deferral account rate rider on basic
# charge + energy (it changes, and has been positive in past years), the regional
# transit levy per day, and GST on the subtotal.
RATE_RIDER_PCT = float(os.getenv('RATE_RIDER_PCT', '-1.5'))
TRANSIT_LEVY_DAILY = float(os.getenv('TRANSIT_LEVY_DAILY', '0.0624'))  # $/day
GST_PCT = float(os.getenv('GST_PCT', '5'))
# Billing cycle: every 2 months, periods starting in odd months around the 26th (the day
# after the meter read, which drifts by a few days). BILLING_PERIOD_START (YYYY-MM-DD,
# from the latest bill) pins it exactly. Days are counted in local (Pacific) time.
BILLING_CYCLE_MONTHS = int(os.getenv('BILLING_CYCLE_MONTHS', '2'))
BILLING_CYCLE_FIRST_MONTH = int(os.getenv('BILLING_CYCLE_FIRST_MONTH', '1'))  # 1 = Jan, Mar, May...
BILLING_CYCLE_START_DAY = int(os.getenv('BILLING_CYCLE_START_DAY', '26'))
BILLING_PERIOD_START = os.getenv('BILLING_PERIOD_START')
# "Your next meter reading is on or around ..." from the latest bill (Sep 29, 2026): the
# period ends that day and the next starts the day after, in place of the nominal
# boundary. Update it with each bill; a date nowhere near a boundary is ignored.
BILLING_NEXT_READ = os.getenv('BILLING_NEXT_READ', '2026-11-26')
BILLING_READ_WINDOW_DAYS = 10  # how far a read may sit from the nominal boundary it replaces
BILLING_TZ = ZoneInfo(os.getenv('BILLING_TZ', 'America/Vancouver'))

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
    # When the Pi watchdog (scripts/linknode_watchdog.py) last asked /health/data.
    # None until it does; restored from the store on restart.
    'watchdog_last_seen': None,
}

# Initialize data staleness monitor
monitor = DataStalenessMonitor(
    slack_webhook=os.getenv('SLACK_WEBHOOK_URL'),
    stale_threshold_minutes=int(os.getenv('STALE_THRESHOLD_MINUTES', '5')),
    pushover_token=os.getenv('PUSHOVER_API_TOKEN'),
    pushover_user=os.getenv('PUSHOVER_USER_KEY')
)

# Reports a Pi watchdog that has stopped calling; built by init_store(), which gives
# it the store to keep its state in.
watchdog_liveness = None
# The watchdog names itself in its User-Agent (USER_AGENT in linknode_watchdog.py).
# A run by hand, --dry-run included, sends the same one and counts as the watchdog.
WATCHDOG_USER_AGENT_PREFIX = 'linknode-watchdog/'
# Its requests come every 2 minutes; the time is saved to the store this often.
WATCHDOG_SAVE_SECONDS = 600
_watchdog_saved_at = None

# Background scheduler for monitoring
scheduler = None

# SQLite store, opened by init_store()
db = None

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

def init_store(path=None):
    """Open (creating if needed) the SQLite store"""
    global db, watchdog_liveness, _watchdog_saved_at
    path = path or DB_PATH
    parent = os.path.dirname(path)
    if parent.startswith('/data') and not os.path.ismount('/data'):
        logger.error("/data is not a mounted volume: readings will be lost on restart")
    try:
        db = store.Store(path)
        logger.info(f"SQLite store ready at {db.path}")
        # The Pi's heartbeat arrives every 15 minutes; restore the last one so a
        # restart does not blank the uptime and sample-interval tiles until then.
        saved = db.get_meta('bypass_status')
        if saved:
            stats['bypass_status'] = json.loads(saved)
        # Likewise the time of the Pi watchdog's last request, and what has been
        # said about its silence, so a restart neither forgets nor repeats it.
        stats['watchdog_last_seen'] = db.get_meta('watchdog_last_seen')
        _watchdog_saved_at = None
        watchdog_liveness = WatchdogLiveness(
            monitor, started=stats['start_time'],
            load=_load_watchdog_state, save=_save_watchdog_state)
        return True
    except Exception as e:
        db = None
        watchdog_liveness = None
        logger.error(f"Failed to open SQLite store at {path}: {e}")
        return False

def _load_watchdog_state():
    saved = db.get_meta('watchdog_alert') if db is not None else None
    return json.loads(saved) if saved else None

def _save_watchdog_state(state):
    if db is not None:
        db.set_meta('watchdog_alert', json.dumps(state))

def note_watchdog_request():
    """Record that the Pi watchdog has just called. In memory at once; in the store
    at most every WATCHDOG_SAVE_SECONDS. A save that fails is logged and nothing more:
    it must not fail the request."""
    global _watchdog_saved_at
    if not request.headers.get('User-Agent', '').startswith(WATCHDOG_USER_AGENT_PREFIX):
        return
    stats['watchdog_last_seen'] = datetime.now(timezone.utc).isoformat()
    now = time.monotonic()
    if db is None or (_watchdog_saved_at is not None and now - _watchdog_saved_at < WATCHDOG_SAVE_SECONDS):
        return
    try:
        db.set_meta('watchdog_last_seen', stats['watchdog_last_seen'])
        _watchdog_saved_at = now
    except Exception as e:
        logger.warning(f"Could not save the watchdog's last request time: {e}")

def start_data_monitor():
    """Start the background jobs: data staleness check and daily retention prune"""
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

        scheduler.add_job(
            prune_old_readings,
            IntervalTrigger(hours=24),
            id='db_prune',
            name='Prune readings past retention',
            max_instances=1,
            replace_existing=True
        )

        scheduler.start()
        logger.info("Data staleness monitor started (checks every 5 minutes)")

def prune_old_readings():
    """Background job: drop readings older than RETENTION_DAYS"""
    if db is None:
        return
    try:
        cutoff = store.now_ms() - RETENTION_DAYS * 86_400_000
        deleted = db.prune(cutoff)
        if deleted:
            logger.info(f"Pruned {deleted} readings older than {RETENTION_DAYS} days")
    except Exception as e:
        logger.error(f"Error pruning old readings: {e}")

def latest_reading():
    """(datetime, watts) of the newest power reading in the store, or None.

    This is the telemetry-freshness signal. The Pi stamps each power reading with the
    time the Eagle last heard from the meter, so it normally stops advancing when the
    meter link, the Eagle, the Pi, the home network or our own writes fail.
    stats['last_data_received'] does not: it is the arrival time of the last POST, and
    the Pi keeps re-posting a frozen reading while the Eagle answers but has lost the
    meter. The stamp falls back to a clock when no usable time arrives, which makes a
    frozen reading look fresh: see "The freshness signal" in docs/ALERTING.md.
    """
    if db is None:
        return None
    row = db.latest('power_w', 0, store.now_ms())
    if row is None:
        return None
    return store.EPOCH + timedelta(milliseconds=row[0]), row[1]


def register_values():
    """(newest, then) values of the meter's kWh register: the newest stored row,
    however old, and the newest row from FROZEN_REGISTER_WINDOW or more ago. Either
    is None when there is no such row. The monitor calls the register frozen when
    the two are equal: it does not trust timestamps, so it also catches a frozen
    reading that arrives stamped as new.
    """
    if db is None:
        return None, None
    now = store.now_ms()
    window_ms = FROZEN_REGISTER_WINDOW // timedelta(milliseconds=1)
    newest = db.latest('energy_delivered_kwh', 0, now)
    then = db.latest('energy_delivered_kwh', 0, now - window_ms)
    return (newest[1] if newest else None), (then[1] if then else None)


def check_data_health():
    """Background job to check if data is still arriving"""
    try:
        reading = latest_reading()
    except Exception as e:
        logger.error(f"Error in data health check: {e}")
        return
    try:
        register_now, register_then = register_values()
    except Exception as e:
        # No verdict on the register; the rules on the power reading still apply.
        logger.error(f"Error reading the kWh register for the health check: {e}")
        register_now = register_then = None
    try:
        current_status, transitioned = monitor.check_data_freshness({
            'last_data_received': reading[0].isoformat() if reading else None,
            'last_power_reading': reading[1] if reading else None,
            'register_now': register_now,
            'register_then': register_then,
        })
        if transitioned:
            logger.info(f"Data health status changed to: {current_status}")
    except Exception as e:
        logger.error(f"Error in data health check: {e}")
        return
    try:
        if watchdog_liveness is not None:
            watchdog_liveness.check(stats.get('watchdog_last_seen'), current_status)
    except Exception as e:
        logger.error(f"Error in watchdog liveness check: {e}")

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
                'cycle_period_s': _num('CyclePeriodSeconds', float),
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

STORABLE_FIELDS = ('power_w', 'energy_delivered_kwh', 'energy_received_kwh',
                   'price_per_kwh', 'link_strength', 'message_text')

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
        # dashboard and acknowledge. Deliberately returns BEFORE the store write and
        # the last_data_received update below -- it must not be mistaken for fresh meter
        # data, or it would mask the staleness/Pushover alerting during a real outage.
        if data.get('message_type') == 'bypass_status':
            b = data.get('bypass', {})
            b['updated_at'] = datetime.now(timezone.utc).isoformat()
            stats['bypass_status'] = b
            if db is not None:
                try:
                    db.set_meta('bypass_status', json.dumps(b))
                except Exception as e:
                    logger.warning(f"Could not persist bypass heartbeat: {e}")
            logger.info(f"Bypass heartbeat: data_uptime={b.get('data_uptime_pct')}% "
                        f"device_uptime={b.get('device_uptime_pct')}% "
                        f"outages={b.get('outage_count')}")
            return jsonify({'status': 'ok', 'type': 'bypass_status'}), 200

        # Messages with no storable fields (DeviceInfo, BillingPeriodList, TimeCluster,
        # BlockPriceDetail, etc.) carry only metadata. Acknowledge them without a write.
        if not any(field in data for field in STORABLE_FIELDS):
            stats['filtered_requests'] += 1
            logger.debug(f"No storable fields for message_type={data.get('message_type')}; acknowledged without write")
            return jsonify({'status': 'ignored', 'reason': 'no_storable_fields',
                            'message_type': data.get('message_type')}), 200

        if 'power_w' in data:
            stats['last_power_reading'] = data['power_w']

        # Write to SQLite. Freshness tracking, the staleness alarm and the live stream
        # all key off this write.
        if db is None:
            stats['failed_writes'] += 1
            logger.error("SQLite store not initialized")
            # Still return success to Eagle device
            return jsonify({'status': 'received', 'data': data}), 200
        try:
            db.write(store.to_ms(data['timestamp']),
                     {field: data[field] for field in STORABLE_FIELDS if field in data})
        except Exception as e:
            stats['failed_writes'] += 1
            logger.error(f"Failed to write to SQLite: {e}")
            # Still return success to Eagle device
            return jsonify({'status': 'received', 'data': data}), 200

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

        logger.info(f"Stored reading: {data}")

        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        stats['failed_writes'] += 1
        logger.error(f"Error processing request: {e}")
        return jsonify({'error': str(e)}), 500

def _add_months(dt, months):
    """Same day-of-month `months` later (or earlier), clamped to the month's last day."""
    total = dt.month - 1 + months
    year, month = dt.year + total // 12, total % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def get_billing_period_start(now=None):
    """Start (local midnight, BILLING_TZ) of the billing period containing `now`.

    BC Hydro bills every BILLING_CYCLE_MONTHS months. Without BILLING_PERIOD_START the
    periods start on BILLING_CYCLE_START_DAY of every other month from
    BILLING_CYCLE_FIRST_MONTH (odd months for this account). The real start is the day
    after the meter is read, which drifts by a few days (bills ended Jul 28, Sep 25,
    Nov 26, Jan 27, Mar 27, May 28), so for an exact match set BILLING_PERIOD_START to
    the start date printed on the latest bill; it is stepped forward by whole cycles.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(BILLING_TZ)
    if BILLING_PERIOD_START:
        anchor = datetime.strptime(BILLING_PERIOD_START, '%Y-%m-%d').replace(tzinfo=BILLING_TZ)
    else:
        anchor = datetime(2000, BILLING_CYCLE_FIRST_MONTH, BILLING_CYCLE_START_DAY, tzinfo=BILLING_TZ)
    months = (now.year - anchor.year) * 12 + (now.month - anchor.month)
    k = months // BILLING_CYCLE_MONTHS
    start = _add_months(anchor, k * BILLING_CYCLE_MONTHS)
    if start > now:
        start = _add_months(anchor, (k - 1) * BILLING_CYCLE_MONTHS)
    return start


def get_billing_period(now=None):
    """(start, next_start) of the billing period containing `now`, as local midnights.

    get_billing_period_start gives the nominal boundaries. BILLING_NEXT_READ, the meter
    read date printed on the latest bill, moves the nominal boundary nearest to it to the
    day after the read, so the period runs to the day BC Hydro actually reads the meter.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(BILLING_TZ)
    start = get_billing_period_start(now)
    next_start = _add_months(start, BILLING_CYCLE_MONTHS)
    if not BILLING_NEXT_READ:
        return start, next_start

    read = datetime.strptime(BILLING_NEXT_READ, '%Y-%m-%d').replace(tzinfo=BILLING_TZ)
    boundary = read + timedelta(days=1)
    window = timedelta(days=BILLING_READ_WINDOW_DAYS)
    if abs(boundary - start) <= window:
        if now >= boundary:
            start = boundary
        else:  # the nominal boundary has passed but the read has not: still the old period
            start, next_start = _add_months(start, -BILLING_CYCLE_MONTHS), boundary
    elif abs(boundary - next_start) <= window:
        if now >= boundary:
            start, next_start = boundary, _add_months(next_start, BILLING_CYCLE_MONTHS)
        else:
            next_start = boundary
    return start, next_start


def calculate_tiered_cost(energy_kwh, days_in_period, tier1_rate=None, tier2_rate=None):
    """
    Bill for `energy_kwh` over `days_in_period` days, built line by line the way BC Hydro's
    residential tiered bill (rate schedule 1101) is: each line rounded to the cent, the
    deferral account rate rider applied to basic charge + energy, the regional transit
    levy per day, then GST on the subtotal. Reproduces the Jul 30, 2026 bill
    (855 kWh over 61 days = $123.75) and the Sep 29, 2026 bill (914 kWh over 59 days =
    $130.38) exactly; see test_api.TestBilling.

    Args:
        energy_kwh: Total energy consumed in kWh
        days_in_period: Number of days in the billing period
        tier1_rate: Rate for consumption below threshold (default: TIER1_RATE)
        tier2_rate: Rate for consumption above threshold (default: TIER2_RATE)

    Returns:
        dict with cost breakdown; total_cost is the amount due including GST
    """
    tier1 = tier1_rate or TIER1_RATE
    tier2 = tier2_rate or TIER2_RATE

    # The Step 1 threshold scales with the days in the period (1,354 kWh over 61 days)
    threshold_kwh = days_in_period * DAILY_THRESHOLD_KWH
    tier1_kwh = min(energy_kwh, threshold_kwh)
    tier2_kwh = max(0.0, energy_kwh - threshold_kwh)

    basic_charge = round(days_in_period * BASIC_CHARGE_DAILY, 2)
    tier1_cost = round(tier1_kwh * tier1, 2)
    tier2_cost = round(tier2_kwh * tier2, 2)
    rider = round((basic_charge + tier1_cost + tier2_cost) * RATE_RIDER_PCT / 100, 2)
    transit_levy = round(days_in_period * TRANSIT_LEVY_DAILY, 2)
    subtotal = round(basic_charge + tier1_cost + tier2_cost + rider + transit_levy, 2)
    gst = round(subtotal * GST_PCT / 100, 2)

    return {
        'threshold_kwh': round(threshold_kwh, 2),
        'tier1_kwh': round(tier1_kwh, 2),
        'tier2_kwh': round(tier2_kwh, 2),
        'tier1_cost': tier1_cost,
        'tier2_cost': tier2_cost,
        'basic_charge': basic_charge,
        'rider_pct': RATE_RIDER_PCT,
        'rider': rider,
        'transit_levy': transit_levy,
        'subtotal': subtotal,
        'gst_pct': GST_PCT,
        'gst': gst,
        'total_cost': round(subtotal + gst, 2),
        'tier1_rate': tier1,
        'tier2_rate': tier2
    }


def _linear_fit(points):
    """Least-squares (slope, intercept) through [(x, y)], or None without two distinct x."""
    n = len(points)
    mean_x = sum(x for x, _ in points) / n
    mean_y = sum(y for _, y in points) / n
    sxx = sum((x - mean_x) ** 2 for x, _ in points)
    if not sxx:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / sxx
    return slope, mean_y - slope * mean_x


def billing_trend(day_kwh, elapsed_days, energy_kwh, cycle_days):
    """Bill so far against the day of the cycle, with a straight-line forecast.

    The points are $0 at day 0, the bill at the end of each completed day (`day_kwh` is
    the cumulative kWh at each of those midnights) and the bill now, at `elapsed_days`
    with the per-day charges prorated so it sits on the same curve as the rest. The
    trendline is the least-squares line through them: its slope is the spend rate in
    $/day (the consumption rate only while the unit price holds) and its value at
    `cycle_days` is the bill if that rate holds. No trendline until one full day is in.
    """
    points = [(0.0, 0.0)]
    points += [(float(day), calculate_tiered_cost(kwh, day)['total_cost'])
               for day, kwh in enumerate(day_kwh, start=1)]
    if energy_kwh is not None and elapsed_days > len(day_kwh):
        points.append((round(elapsed_days, 3),
                       calculate_tiered_cost(energy_kwh, elapsed_days)['total_cost']))

    trend = {'points': [list(p) for p in points],
             'slope_per_day': None, 'intercept': None, 'projected_total': None}
    fit = _linear_fit(points) if day_kwh else None
    if fit:
        slope, intercept = fit
        trend['slope_per_day'] = round(slope, 4)
        trend['intercept'] = round(intercept, 4)
        trend['projected_total'] = round(slope * cycle_days + intercept, 2)
    return trend


_billing_days_cache = {}
_billing_days_cache_lock = Lock()
BILLING_DAYS_CACHE_SECONDS = 3600
HOUR_MS = 3_600_000


def _billing_day_kwh(billing_start, completed_days):
    """Cumulative kWh at the end of each completed local day of the billing period.

    One pass over the period in hourly buckets, summed up to each local midnight (hours,
    so a DST change inside the period cannot shift a day). Completed days do not change,
    so the result is kept until the day count does; the hourly expiry only picks up
    late backfilled readings."""
    start_ms = store.to_ms(billing_start)
    key = (start_ms, completed_days)
    now = time.monotonic()
    with _billing_days_cache_lock:
        cached = _billing_days_cache.get('days')
        if cached and cached[0] == key and now - cached[1] < BILLING_DAYS_CACHE_SECONDS:
            return cached[2]

    edges = [store.to_ms(billing_start + timedelta(days=day)) for day in range(1, completed_days + 1)]
    buckets = sorted(db.integral_wh_buckets(start_ms, edges[-1], HOUR_MS).items()) if edges else []
    day_kwh, total_wh, i = [], 0.0, 0
    for edge in edges:
        while i < len(buckets) and start_ms + buckets[i][0] * HOUR_MS < edge:
            total_wh += buckets[i][1]
            i += 1
        day_kwh.append(total_wh / 1000.0)

    with _billing_days_cache_lock:
        _billing_days_cache['days'] = (key, now, day_kwh)
    return day_kwh


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    db_ok = db is not None and db.ping()
    health_status = {
        'status': 'healthy' if db_ok else 'unhealthy',
        'db_ok': db_ok,
        'uptime_seconds': (datetime.now(timezone.utc) - datetime.fromisoformat(stats['start_time'])).total_seconds()
    }

    return jsonify(health_status), 200 if health_status['status'] == 'healthy' else 503

@app.route('/health/data', methods=['GET'])
def data_health():
    """Telemetry freshness, for a watcher outside this service: 200 while the newest
    meter reading is recent, 503 once it is older than the staleness threshold.

    Separate from /health on purpose. /health is Fly's service check: while it fails Fly
    stops routing requests to this machine (it does not restart it). That is right for a
    dead process or store and wrong for a dead Pi or Eagle, where it would cut off the
    uploads that could make the feed fresh again.
    """
    note_watchdog_request()
    stale_after = monitor.stale_threshold_minutes * 60
    try:
        reading = latest_reading()
    except Exception as e:
        logger.error(f"Error reading the store for /health/data: {e}")
        return jsonify({'status': 'unavailable', 'stale_after_seconds': stale_after}), 503
    if reading is None:
        return jsonify({'status': 'no_data', 'stale_after_seconds': stale_after}), 503

    age = (datetime.now(timezone.utc) - reading[0]).total_seconds()
    fresh = age <= stale_after
    return jsonify({
        'status': 'fresh' if fresh else 'stale',
        'reading_age_seconds': round(age, 1),
        'last_reading': reading[0].isoformat(),
        'power_w': reading[1],
        'stale_after_seconds': stale_after,
    }), 200 if fresh else 503

def _window_stats_sqlite(hours, billing_start):
    """Raw window statistics from the SQLite store. None if the store is not open."""
    if db is None:
        return None
    now = store.now_ms()
    start = now - hours * 3_600_000
    power = db.agg('power_w', start, now)
    price = db.latest('price_per_kwh', start, now)
    energy_wh = db.integral_wh(store.to_ms(billing_start), now)
    return {
        'min': power['min'],
        'max': power['max'],
        'mean': power['mean'],
        'count': power['count'],
        'price': price[1] if price else None,
        'billing_energy_kwh': energy_wh / 1000.0 if energy_wh is not None else None,
    }

@app.route('/api/stats', methods=['GET'])
@require_api_key
def get_stats():
    """Get power statistics with min/max/avg calculations"""
    try:
        hours = int(request.args.get('hours', 24))
    except ValueError:
        return jsonify({'error': 'hours must be an integer'}), 400
    if not 1 <= hours <= 720:
        return jsonify({'error': 'hours must be between 1 and 720'}), 400

    # Count active SSE viewers
    with sse_clients_lock:
        active_viewers = len(sse_clients)

    # The last power value posted since this process started. After a restart there is
    # none until the next power reading, so fall back to the newest stored one: a
    # restart during a telemetry outage must not look like the stats API failing.
    # The in-memory value itself stays unset: the live stream sends it to each page
    # that connects, and the page would show it as live.
    current_power = stats.get('last_power_reading')
    if current_power is None:
        try:
            reading = latest_reading()
            current_power = reading[1] if reading else None
        except Exception as e:
            logger.error(f"Error reading the newest power reading for stats: {e}")

    result = {
        'current_power': current_power,
        'min_24h': 0,
        'max_24h': 0,
        'avg_24h': 0,
        'cost_24h': 0,
        # The configured Step 1 rate; the Eagle's own (stale) price is meter_price_per_kwh
        'price_per_kwh': TIER1_RATE,
        'meter_price_per_kwh': None,
        'last_update': stats.get('last_data_received'),
        'active_viewers': active_viewers,
        'packet_interval_ms': stats.get('packet_interval_ms'),
        'packets_today': stats.get('packets_today', 0),
        # Rolling 24h completeness: fresh meter reads received vs expected at the report
        # rate. Populated from the store below; None if the store is unreachable.
        'reads_24h': None,
        # Live uptime from the Pi bypass heartbeat (None until the first arrives).
        'bypass_status': stats.get('bypass_status'),
        'monitor_stats': stats,
        # Billing period info (tiered rates)
        'billing_period': {
            'start': None,
            'next_start': None,
            'days': 0,
            'cycle_days': 0,
            'energy_kwh': 0,
            'tiered_cost': None,
            'trend': None
        }
    }

    billing_start, next_start = get_billing_period()
    try:
        window = _window_stats_sqlite(hours, billing_start)
    except Exception as e:
        logger.error(f"Error querying the store for stats: {e}")
        window = None

    if window is None:
        return jsonify(result), 200

    for key, field in (('min_24h', 'min'), ('max_24h', 'max'), ('avg_24h', 'mean')):
        if window[field] is not None:
            result[key] = window[field]

    # Rolling-window completeness: how many FRESH meter reads arrived vs how many
    # should have at the report rate. "received" = distinct stored power_w
    # (InstantaneousDemand) points in the window; because the Pi timestamps each
    # reading with the meter's LastContact time, a cycle where the Eagle did not
    # respond (nothing shipped) or returned stale data (same LastContact -> same
    # point, overwritten) does not add a point, so it does not count. "expected" =
    # window / period, where period is the Pi's MEASURED true cycle time (sleep +
    # per-cycle work, ~33s at a nominal 30s interval), else the nominal interval,
    # else SAMPLE_INTERVAL_SEC env, else 30. Using the measured period avoids a
    # phantom shortfall from counting against an unachievable nominal rate.
    received = window['count']
    bypass = stats.get('bypass_status') or {}
    period_s = (bypass.get('cycle_period_s') or bypass.get('interval_s')
                or float(os.getenv('SAMPLE_INTERVAL_SEC', '30')))
    period_s = period_s if period_s and period_s > 0 else 30.0
    expected = round(hours * 3600 / period_s)
    result['reads_24h'] = {
        'received': min(received, expected),   # clamp jitter so it never exceeds 100%
        'expected': expected,
        'period_s': round(period_s, 1),
        'window_hours': hours,
    }

    result['meter_price_per_kwh'] = window['price']

    # Calculate cost using avg power * hours * the Step 1 rate (simple estimate)
    if result['avg_24h'] > 0 and result['price_per_kwh'] > 0:
        kwh = (result['avg_24h'] / 1000) * hours  # Convert W to kW and multiply by hours
        result['cost_24h'] = round(kwh * result['price_per_kwh'], 2)

    # Billing period so far, in local calendar days like the bill
    local_now = datetime.now(timezone.utc).astimezone(BILLING_TZ)
    today = local_now.date()
    days_in_period = (today - billing_start.date()).days + 1  # Include today
    cycle_days = (next_start.date() - billing_start.date()).days

    result['billing_period']['start'] = billing_start.isoformat()
    result['billing_period']['next_start'] = next_start.isoformat()
    result['billing_period']['days'] = days_in_period
    result['billing_period']['cycle_days'] = cycle_days

    energy_kwh = window['billing_energy_kwh']
    if energy_kwh is not None:
        result['billing_period']['energy_kwh'] = round(energy_kwh, 2)

        # Tiered cost from the configured BC Hydro rates
        tiered = calculate_tiered_cost(energy_kwh, days_in_period)
        result['billing_period']['tiered_cost'] = tiered

        # Bill so far by day, and the straight line through it out to the last day
        try:
            completed_days = days_in_period - 1
            midnight = billing_start + timedelta(days=completed_days)
            elapsed_days = completed_days + (local_now - midnight) / timedelta(days=1)
            result['billing_period']['trend'] = billing_trend(
                _billing_day_kwh(billing_start, completed_days), elapsed_days, energy_kwh, cycle_days)
        except Exception as e:
            logger.error(f"Error building the billing trend: {e}")

    return jsonify(result), 200

_dashboard_cache = {}
_dashboard_cache_lock = Lock()
DASHBOARD_CACHE_SECONDS = 15

@app.route('/api/dashboard', methods=['GET'])
@require_api_key
def get_dashboard():
    """Dashboard panels (chart series + stat values) for a preset time range"""
    range_key = request.args.get('range', dashboard.DEFAULT_RANGE)
    if range_key not in dashboard.RANGES:
        return jsonify({'error': 'invalid range', 'allowed': list(dashboard.RANGES)}), 400
    if db is None:
        return jsonify({'error': 'store unavailable'}), 503

    now = time.monotonic()
    with _dashboard_cache_lock:
        cached = _dashboard_cache.get(range_key)
        if cached and now - cached[0] < DASHBOARD_CACHE_SECONDS:
            return jsonify(cached[1]), 200
    try:
        payload = dashboard.build(db, range_key, store.now_ms(), TIER1_RATE)
    except Exception as e:
        logger.error(f"Error building dashboard ({range_key}): {e}")
        return jsonify({'error': 'query failed'}), 500
    with _dashboard_cache_lock:
        _dashboard_cache[range_key] = (now, payload)
    return jsonify(payload), 200

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'service': 'Eagle-200 XML Monitor',
        'version': '1.0.0',
        'endpoints': {
            '/eagle': 'POST - Receive Eagle-200 XML data',
            '/api/stats': 'GET - Monitor statistics',
            '/api/dashboard': 'GET - Dashboard panels (?range=1h|6h|24h|7d|30d)',
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
    init_store()

    # Start the data staleness monitor
    start_data_monitor()

    # Run Flask app
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)