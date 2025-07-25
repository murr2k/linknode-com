#!/usr/bin/env python3
"""
Security monitoring module for Eagle Monitor API
Tracks authentication failures, rate limit violations, and suspicious activity
"""

import logging
import json
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock
import os

logger = logging.getLogger(__name__)

class SecurityMonitor:
    def __init__(self):
        self.auth_failures = defaultdict(list)
        self.rate_limit_violations = defaultdict(list)
        self.suspicious_ips = set()
        self.lock = Lock()
        
        # Configuration
        self.MAX_AUTH_FAILURES = 5
        self.AUTH_FAILURE_WINDOW = 3600  # 1 hour
        self.MAX_RATE_VIOLATIONS = 10
        self.RATE_VIOLATION_WINDOW = 3600  # 1 hour
        
        # Log file for security events
        self.security_log_file = os.getenv('SECURITY_LOG_FILE', '/tmp/security_events.log')
    
    def log_security_event(self, event_type, ip_address, details=None):
        """Log security events to file and logger"""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'ip_address': ip_address,
            'details': details or {}
        }
        
        # Log to file
        try:
            with open(self.security_log_file, 'a') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            logger.error(f"Failed to write security log: {e}")
        
        # Log to logger
        logger.warning(f"Security Event: {event_type} from {ip_address} - {details}")
    
    def record_auth_failure(self, ip_address, api_key=None):
        """Record authentication failure"""
        with self.lock:
            current_time = datetime.utcnow()
            self.auth_failures[ip_address].append(current_time)
            
            # Clean old entries
            cutoff_time = current_time - timedelta(seconds=self.AUTH_FAILURE_WINDOW)
            self.auth_failures[ip_address] = [
                t for t in self.auth_failures[ip_address] if t > cutoff_time
            ]
            
            # Check if IP should be flagged as suspicious
            if len(self.auth_failures[ip_address]) >= self.MAX_AUTH_FAILURES:
                self.suspicious_ips.add(ip_address)
                self.log_security_event(
                    'SUSPICIOUS_IP_FLAGGED',
                    ip_address,
                    {'auth_failures': len(self.auth_failures[ip_address])}
                )
            
            self.log_security_event(
                'AUTH_FAILURE',
                ip_address,
                {'api_key': api_key[:8] + '...' if api_key else 'none'}
            )
    
    def record_rate_limit_violation(self, ip_address):
        """Record rate limit violation"""
        with self.lock:
            current_time = datetime.utcnow()
            self.rate_limit_violations[ip_address].append(current_time)
            
            # Clean old entries
            cutoff_time = current_time - timedelta(seconds=self.RATE_VIOLATION_WINDOW)
            self.rate_limit_violations[ip_address] = [
                t for t in self.rate_limit_violations[ip_address] if t > cutoff_time
            ]
            
            # Check if IP should be flagged as suspicious
            if len(self.rate_limit_violations[ip_address]) >= self.MAX_RATE_VIOLATIONS:
                self.suspicious_ips.add(ip_address)
                self.log_security_event(
                    'EXCESSIVE_RATE_VIOLATIONS',
                    ip_address,
                    {'violations': len(self.rate_limit_violations[ip_address])}
                )
            
            self.log_security_event('RATE_LIMIT_VIOLATION', ip_address)
    
    def is_ip_suspicious(self, ip_address):
        """Check if IP is flagged as suspicious"""
        return ip_address in self.suspicious_ips
    
    def get_security_stats(self):
        """Get current security statistics"""
        with self.lock:
            current_time = datetime.utcnow()
            
            # Clean old entries
            auth_cutoff = current_time - timedelta(seconds=self.AUTH_FAILURE_WINDOW)
            rate_cutoff = current_time - timedelta(seconds=self.RATE_VIOLATION_WINDOW)
            
            active_auth_failures = {
                ip: len([t for t in times if t > auth_cutoff])
                for ip, times in self.auth_failures.items()
            }
            
            active_rate_violations = {
                ip: len([t for t in times if t > rate_cutoff])
                for ip, times in self.rate_limit_violations.items()
            }
            
            return {
                'suspicious_ips': list(self.suspicious_ips),
                'auth_failures': {k: v for k, v in active_auth_failures.items() if v > 0},
                'rate_violations': {k: v for k, v in active_rate_violations.items() if v > 0},
                'total_suspicious': len(self.suspicious_ips),
                'timestamp': current_time.isoformat()
            }
    
    def clear_ip(self, ip_address):
        """Clear suspicious flag for an IP address"""
        with self.lock:
            self.suspicious_ips.discard(ip_address)
            self.auth_failures.pop(ip_address, None)
            self.rate_limit_violations.pop(ip_address, None)
            self.log_security_event('IP_CLEARED', ip_address)


# Global security monitor instance
security_monitor = SecurityMonitor()


def require_api_key_with_monitoring(f):
    """Enhanced API key decorator with security monitoring"""
    from functools import wraps
    from flask import request, jsonify
    import os
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get client IP
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Check if IP is suspicious
        if security_monitor.is_ip_suspicious(client_ip):
            security_monitor.log_security_event('BLOCKED_SUSPICIOUS_IP', client_ip)
            return jsonify({'error': 'Access denied'}), 403
        
        # Skip auth for public endpoints
        PUBLIC_ENDPOINTS = ['/health', '/']
        if request.endpoint in PUBLIC_ENDPOINTS or request.path in PUBLIC_ENDPOINTS:
            return f(*args, **kwargs)
        
        # Check for API key
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        API_KEY = os.getenv('EAGLE_API_KEY')
        
        if not API_KEY:
            logger.warning("API_KEY not configured - authentication disabled")
            return f(*args, **kwargs)
        
        if not api_key:
            security_monitor.record_auth_failure(client_ip)
            return jsonify({'error': 'API key required'}), 401
        
        if api_key != API_KEY:
            security_monitor.record_auth_failure(client_ip, api_key)
            return jsonify({'error': 'Invalid API key'}), 401
        
        # Check rate limit (assuming rate limit check is done elsewhere)
        # If rate limit exceeded, it should call:
        # security_monitor.record_rate_limit_violation(client_ip)
        
        return f(*args, **kwargs)
    
    return decorated_function