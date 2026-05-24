#!/usr/bin/env python3
"""
Data Staleness Monitor for Eagle-200 Monitor
Detects when data stops arriving from the power meter and sends Slack alerts
on state transitions (healthy <-> unhealthy).
"""

import os
import logging
import json
from datetime import datetime, timezone, timedelta
import requests
from pathlib import Path

logger = logging.getLogger(__name__)


class DataStalenessMonitor:
    """Monitor data freshness and track state transitions"""

    def __init__(self, state_file=None, slack_webhook=None, stale_threshold_minutes=5,
                 pushover_token=None, pushover_user=None,
                 pushover_retry=60, pushover_expire=3600):
        """
        Initialize the monitor.

        Args:
            state_file: Path to JSON file for persisting state (default: /tmp/eagle_monitor_state.json)
            slack_webhook: Slack webhook URL for alerts
            stale_threshold_minutes: Consider data stale if older than this many minutes
            pushover_token: Pushover application API token (for emergency siren alerts)
            pushover_user: Pushover user key
            pushover_retry: Seconds between siren re-alerts while unacknowledged (Pushover min 30)
            pushover_expire: Seconds before Pushover stops re-alerting (Pushover max 10800)
        """
        self.state_file = state_file or os.getenv('MONITOR_STATE_FILE', '/tmp/eagle_monitor_state.json')
        self.slack_webhook = slack_webhook or os.getenv('SLACK_WEBHOOK_URL')
        self.stale_threshold_minutes = stale_threshold_minutes
        self.pushover_token = pushover_token or os.getenv('PUSHOVER_API_TOKEN')
        self.pushover_user = pushover_user or os.getenv('PUSHOVER_USER_KEY')
        self.pushover_retry = pushover_retry
        self.pushover_expire = pushover_expire
        self.previous_status = self._load_state()

        logger.info(f"DataStalenessMonitor initialized with threshold: {stale_threshold_minutes} minutes")

    def _load_state(self):
        """Load previous state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    return data.get('status', 'healthy')
        except Exception as e:
            logger.warning(f"Failed to load state from {self.state_file}: {e}")
        return 'healthy'

    def _save_state(self, status):
        """Save state to file"""
        try:
            state_data = {
                'status': status,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            os.makedirs(os.path.dirname(self.state_file) or '.', exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f)
            logger.debug(f"State saved: {status}")
        except Exception as e:
            logger.error(f"Failed to save state to {self.state_file}: {e}")

    def _send_slack_alert(self, message, emoji='⚠️'):
        """Send message to Slack"""
        if not self.slack_webhook:
            logger.warning("No Slack webhook configured, skipping alert")
            return False

        try:
            payload = {
                'text': f"{emoji} *Linknode Power Monitor Alert*\n{message}\nTime: {datetime.now(timezone.utc).isoformat()}"
            }
            response = requests.post(self.slack_webhook, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Slack alert sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    def _send_pushover_alert(self, message, title='Linknode Power Monitor Alert'):
        """Send an emergency (siren) push via Pushover that repeats until acknowledged."""
        if not (self.pushover_token and self.pushover_user):
            logger.warning("Pushover not configured, skipping siren alert")
            return False

        try:
            # priority=2 (emergency) re-alerts every `retry` seconds until the user
            # acknowledges in the app, or `expire` seconds elapse.
            payload = {
                'token': self.pushover_token,
                'user': self.pushover_user,
                'title': title,
                'message': message,
                'priority': 2,
                'retry': self.pushover_retry,
                'expire': self.pushover_expire,
                'sound': 'siren',
            }
            response = requests.post('https://api.pushover.net/1/messages.json', data=payload, timeout=10)
            response.raise_for_status()
            logger.info("Pushover siren alert sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send Pushover alert: {e}")
            return False

    def check_data_freshness(self, stats_dict):
        """
        Check if data is fresh and handle state transitions.

        Args:
            stats_dict: The stats dictionary from the Flask app

        Returns:
            tuple: (current_status, transitioned) - transitioned is True if state changed
        """
        # Determine current status
        current_status = self._evaluate_health(stats_dict)
        transitioned = current_status != self.previous_status

        if transitioned:
            logger.warning(f"Status transition: {self.previous_status} → {current_status}")

            if current_status == 'unhealthy':
                # Going unhealthy
                reason = self._get_failure_reason(stats_dict)
                message = f"Data is not arriving from power meter!\n{reason}"
                self._send_slack_alert(message, emoji='🚨')
                self._send_pushover_alert(message)
            else:
                # Going healthy
                current_power = stats_dict.get('last_power_reading', 'N/A')
                last_update = stats_dict.get('last_data_received', 'N/A')
                message = f"Power meter is back online!\nCurrent: {current_power}W\nLast update: {last_update}"
                self._send_slack_alert(message, emoji='✅')

            # Save new state
            self._save_state(current_status)
            self.previous_status = current_status

        return current_status, transitioned

    def _evaluate_health(self, stats_dict):
        """
        Evaluate system health based on stats.

        Returns:
            'healthy' or 'unhealthy'
        """
        # Check if we have a last_data_received timestamp
        last_update = stats_dict.get('last_data_received')
        if not last_update:
            return 'unhealthy'

        try:
            # Parse the ISO format timestamp
            if isinstance(last_update, str):
                # Handle ISO format with or without 'Z'
                if last_update.endswith('Z'):
                    last_update = last_update.rstrip('Z') + '+00:00'
                last_update_dt = datetime.fromisoformat(last_update)
            else:
                last_update_dt = last_update

            # Calculate age
            now = datetime.now(timezone.utc)
            age = now - last_update_dt
            age_minutes = age.total_seconds() / 60

            # Check if data is stale
            if age_minutes > self.stale_threshold_minutes:
                logger.warning(f"Data is stale: {age_minutes:.1f} minutes old (threshold: {self.stale_threshold_minutes})")
                return 'unhealthy'

            # Check if last power reading exists and is non-zero
            last_power = stats_dict.get('last_power_reading')
            if last_power is None or last_power == 0:
                logger.warning(f"Invalid power reading: {last_power}")
                return 'unhealthy'

            return 'healthy'

        except Exception as e:
            logger.error(f"Error evaluating health: {e}")
            return 'unhealthy'

    def _get_failure_reason(self, stats_dict):
        """Get human-readable reason for failure"""
        last_update = stats_dict.get('last_data_received')
        if not last_update:
            return "No data received yet"

        try:
            if isinstance(last_update, str):
                if last_update.endswith('Z'):
                    last_update = last_update.rstrip('Z') + '+00:00'
                last_update_dt = datetime.fromisoformat(last_update)
            else:
                last_update_dt = last_update

            now = datetime.now(timezone.utc)
            age = now - last_update_dt
            age_minutes = age.total_seconds() / 60

            if age_minutes > self.stale_threshold_minutes:
                return f"Last data received {age_minutes:.1f} minutes ago (threshold: {self.stale_threshold_minutes} minutes)"

            last_power = stats_dict.get('last_power_reading')
            if last_power is None or last_power == 0:
                return f"Invalid power reading: {last_power}W"

            return "Unknown error"
        except Exception as e:
            return f"Error determining reason: {e}"
