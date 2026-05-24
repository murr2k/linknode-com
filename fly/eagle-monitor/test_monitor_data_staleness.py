#!/usr/bin/env python3
"""
Test suite for DataStalenessMonitor
Tests state transitions and Slack alert behavior
"""

import unittest
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import sys

# Import the monitor module
from monitor_data_staleness import DataStalenessMonitor


class TestDataStalenessMonitor(unittest.TestCase):
    """Test the data staleness monitoring logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, 'test_state.json')

        # Create monitor without Slack webhook for testing
        self.monitor = DataStalenessMonitor(
            state_file=self.state_file,
            slack_webhook=None,  # Disable Slack for unit tests
            stale_threshold_minutes=5
        )

    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        os.rmdir(self.temp_dir)

    def test_healthy_system(self):
        """Test that a system with recent data is healthy"""
        now = datetime.now(timezone.utc)
        stats = {
            'last_data_received': now.isoformat(),
            'last_power_reading': 422.0
        }

        status = self.monitor._evaluate_health(stats)
        self.assertEqual(status, 'healthy')

    def test_stale_data_is_unhealthy(self):
        """Test that stale data triggers unhealthy status"""
        # Data from 10 minutes ago
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        stats = {
            'last_data_received': old_time.isoformat(),
            'last_power_reading': 422.0
        }

        status = self.monitor._evaluate_health(stats)
        self.assertEqual(status, 'unhealthy')

    def test_zero_power_is_unhealthy(self):
        """Test that zero power reading triggers unhealthy status"""
        now = datetime.now(timezone.utc)
        stats = {
            'last_data_received': now.isoformat(),
            'last_power_reading': 0
        }

        status = self.monitor._evaluate_health(stats)
        self.assertEqual(status, 'unhealthy')

    def test_missing_power_reading_is_unhealthy(self):
        """Test that missing power reading triggers unhealthy status"""
        now = datetime.now(timezone.utc)
        stats = {
            'last_data_received': now.isoformat(),
            'last_power_reading': None
        }

        status = self.monitor._evaluate_health(stats)
        self.assertEqual(status, 'unhealthy')

    def test_state_transition_healthy_to_unhealthy(self):
        """Test transition from healthy to unhealthy"""
        # Start with healthy
        now = datetime.now(timezone.utc)
        healthy_stats = {
            'last_data_received': now.isoformat(),
            'last_power_reading': 422.0
        }

        # Verify we start healthy
        self.assertEqual(self.monitor.previous_status, 'healthy')

        # Transition to unhealthy (old data)
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        unhealthy_stats = {
            'last_data_received': old_time.isoformat(),
            'last_power_reading': 422.0
        }

        status, transitioned = self.monitor.check_data_freshness(unhealthy_stats)
        self.assertEqual(status, 'unhealthy')
        self.assertTrue(transitioned)

        # Verify state was saved
        self.assertEqual(self.monitor.previous_status, 'unhealthy')

    def test_state_transition_unhealthy_to_healthy(self):
        """Test transition from unhealthy to healthy"""
        # Manually set to unhealthy state
        self.monitor.previous_status = 'unhealthy'

        # Now provide healthy stats
        now = datetime.now(timezone.utc)
        healthy_stats = {
            'last_data_received': now.isoformat(),
            'last_power_reading': 422.0
        }

        status, transitioned = self.monitor.check_data_freshness(healthy_stats)
        self.assertEqual(status, 'healthy')
        self.assertTrue(transitioned)
        self.assertEqual(self.monitor.previous_status, 'healthy')

    def test_no_transition_healthy_to_healthy(self):
        """Test that staying healthy doesn't trigger transition"""
        now = datetime.now(timezone.utc)
        stats = {
            'last_data_received': now.isoformat(),
            'last_power_reading': 422.0
        }

        # First call
        status1, transitioned1 = self.monitor.check_data_freshness(stats)
        self.assertEqual(status1, 'healthy')
        self.assertFalse(transitioned1)  # Initial is not a "transition"

        # Second call with same healthy state
        status2, transitioned2 = self.monitor.check_data_freshness(stats)
        self.assertEqual(status2, 'healthy')
        self.assertFalse(transitioned2)  # No transition

    def test_state_persistence(self):
        """Test that state is saved and loaded from file"""
        # Create first monitor and set it to unhealthy
        now = datetime.now(timezone.utc) - timedelta(minutes=10)
        stats = {
            'last_data_received': now.isoformat(),
            'last_power_reading': 422.0
        }

        monitor1 = DataStalenessMonitor(state_file=self.state_file)
        monitor1.check_data_freshness(stats)
        self.assertEqual(monitor1.previous_status, 'unhealthy')

        # Create new monitor from same state file
        monitor2 = DataStalenessMonitor(state_file=self.state_file)
        self.assertEqual(monitor2.previous_status, 'unhealthy')

    def test_iso_timestamp_parsing_with_z(self):
        """Test parsing ISO timestamps with Z suffix"""
        # Timestamp with Z suffix
        now_str = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        stats = {
            'last_data_received': now_str,
            'last_power_reading': 422.0
        }

        status = self.monitor._evaluate_health(stats)
        self.assertEqual(status, 'healthy')

    @patch('monitor_data_staleness.requests.post')
    def test_slack_alert_on_unhealthy_transition(self, mock_post):
        """Test that Slack alert is sent on unhealthy transition"""
        # Create monitor with Slack webhook
        monitor = DataStalenessMonitor(
            state_file=self.state_file,
            slack_webhook='https://hooks.slack.com/services/TEST/WEBHOOK',
            stale_threshold_minutes=5
        )

        # Mock the POST request
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Transition to unhealthy
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        stats = {
            'last_data_received': old_time.isoformat(),
            'last_power_reading': 422.0
        }

        monitor.check_data_freshness(stats)

        # Verify Slack was called
        self.assertTrue(mock_post.called)

        # Verify the alert contains key information
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertIn('Linknode Power Monitor Alert', payload['text'])
        self.assertIn('Data is not arriving', payload['text'])

    @patch('monitor_data_staleness.requests.post')
    def test_slack_alert_on_healthy_transition(self, mock_post):
        """Test that Slack recovery alert is sent on healthy transition"""
        # Create monitor with Slack webhook
        monitor = DataStalenessMonitor(
            state_file=self.state_file,
            slack_webhook='https://hooks.slack.com/services/TEST/WEBHOOK',
            stale_threshold_minutes=5
        )

        # Manually set to unhealthy
        monitor.previous_status = 'unhealthy'

        # Mock the POST request
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Transition to healthy
        now = datetime.now(timezone.utc)
        stats = {
            'last_data_received': now.isoformat(),
            'last_power_reading': 422.0
        }

        monitor.check_data_freshness(stats)

        # Verify Slack was called
        self.assertTrue(mock_post.called)

        # Verify the alert contains recovery message
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertIn('back online', payload['text'])
        self.assertIn('✅', payload['text'])

    @patch('monitor_data_staleness.requests.post')
    def test_pushover_siren_on_unhealthy_transition(self, mock_post):
        """Test that an emergency Pushover siren is sent on unhealthy transition"""
        monitor = DataStalenessMonitor(
            state_file=self.state_file,
            slack_webhook=None,  # isolate Pushover as the only POST
            pushover_token='PUSHOVER_TEST_TOKEN',
            pushover_user='PUSHOVER_TEST_USER',
            stale_threshold_minutes=5
        )

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        stats = {
            'last_data_received': old_time.isoformat(),
            'last_power_reading': 422.0
        }

        monitor.check_data_freshness(stats)

        self.assertTrue(mock_post.called)
        call_args = mock_post.call_args
        # Pushover posts form-encoded data to its messages endpoint
        self.assertEqual(call_args[0][0], 'https://api.pushover.net/1/messages.json')
        payload = call_args[1]['data']
        self.assertEqual(payload['priority'], 2)  # emergency: repeats until acked
        self.assertEqual(payload['sound'], 'siren')
        self.assertIn('Data is not arriving', payload['message'])

    @patch('monitor_data_staleness.requests.post')
    def test_pushover_not_sent_on_healthy_transition(self, mock_post):
        """Test that the siren does NOT fire on recovery (healthy transition)"""
        monitor = DataStalenessMonitor(
            state_file=self.state_file,
            slack_webhook=None,
            pushover_token='PUSHOVER_TEST_TOKEN',
            pushover_user='PUSHOVER_TEST_USER',
            stale_threshold_minutes=5
        )
        monitor.previous_status = 'unhealthy'

        now = datetime.now(timezone.utc)
        stats = {
            'last_data_received': now.isoformat(),
            'last_power_reading': 422.0
        }

        monitor.check_data_freshness(stats)

        # Recovery is Slack-only; with Slack disabled, no POST should occur
        self.assertFalse(mock_post.called)

    @patch('monitor_data_staleness.requests.post')
    def test_pushover_skipped_when_unconfigured(self, mock_post):
        """Test that missing Pushover credentials skip the siren gracefully"""
        result = self.monitor._send_pushover_alert('test message')
        self.assertFalse(result)
        self.assertFalse(mock_post.called)

    def test_failure_reason_stale_data(self):
        """Test failure reason for stale data"""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        stats = {
            'last_data_received': old_time.isoformat(),
            'last_power_reading': 422.0
        }

        reason = self.monitor._get_failure_reason(stats)
        self.assertIn('minutes ago', reason)
        self.assertIn('threshold', reason)

    def test_failure_reason_zero_power(self):
        """Test failure reason for zero power"""
        now = datetime.now(timezone.utc)
        stats = {
            'last_data_received': now.isoformat(),
            'last_power_reading': 0
        }

        reason = self.monitor._get_failure_reason(stats)
        self.assertIn('Invalid power reading', reason)

    def test_custom_stale_threshold(self):
        """Test with custom stale threshold"""
        monitor = DataStalenessMonitor(
            state_file=self.state_file,
            stale_threshold_minutes=2  # Custom 2-minute threshold
        )

        # Data from 3 minutes ago should be stale
        old_time = datetime.now(timezone.utc) - timedelta(minutes=3)
        stats = {
            'last_data_received': old_time.isoformat(),
            'last_power_reading': 422.0
        }

        status = monitor._evaluate_health(stats)
        self.assertEqual(status, 'unhealthy')

        # But data from 1 minute ago should be healthy
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        stats = {
            'last_data_received': recent_time.isoformat(),
            'last_power_reading': 422.0
        }

        status = monitor._evaluate_health(stats)
        self.assertEqual(status, 'healthy')


class TestIntegrationWithFlaskStats(unittest.TestCase):
    """Integration tests with actual Flask stats format"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, 'test_state.json')
        self.monitor = DataStalenessMonitor(
            state_file=self.state_file,
            slack_webhook=None,
            stale_threshold_minutes=5
        )

    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        os.rmdir(self.temp_dir)

    def test_with_flask_stats_format(self):
        """Test with actual Flask stats dictionary format"""
        now = datetime.now(timezone.utc)
        flask_stats = {
            'total_requests': 100,
            'successful_writes': 98,
            'failed_writes': 2,
            'filtered_requests': 5,
            'last_data_received': now.isoformat(),
            'last_power_reading': 422.0,
            'packet_interval_ms': 4612,
            'packets_today': 100,
            'packets_today_date': now.strftime('%Y-%m-%d')
        }

        status, transitioned = self.monitor.check_data_freshness(flask_stats)
        self.assertEqual(status, 'healthy')

    def test_with_missing_last_data_received(self):
        """Test behavior when last_data_received is None (app just started)"""
        flask_stats = {
            'total_requests': 0,
            'successful_writes': 0,
            'failed_writes': 0,
            'last_data_received': None,
            'last_power_reading': None,
        }

        status = self.monitor._evaluate_health(flask_stats)
        self.assertEqual(status, 'unhealthy')


def run_tests():
    """Run all tests with detailed output"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestDataStalenessMonitor))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationWithFlaskStats))

    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
