#!/usr/bin/env python3
"""
Data Staleness Monitor for Eagle-200 Monitor

Decides healthy or unhealthy from the newest power reading (its own timestamp and its
value) and from the meter's kWh register, and alerts on a change of state: Slack plus a
Pushover emergency siren when the feed goes unhealthy, Slack when it recovers. The siren
is sent again on every run until Pushover accepts it, and a normal-priority reminder
follows every 24 hours for as long as the outage lasts.

WatchdogLiveness, at the end, reports a Pi watchdog that has stopped calling.
How the two fit together: docs/ALERTING.md.
"""

import os
import logging
import json
from datetime import datetime, timezone, timedelta
import requests

logger = logging.getLogger(__name__)

PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'

# While an outage lasts, one normal-priority reminder this long after each accepted message.
REMINDER_INTERVAL = timedelta(hours=24)
# A 4xx from Pushover is a refusal (rejected token or user key, or the account over its
# quota). Asking again 5 minutes later cannot help, so hold off this long. Held in memory
# only: a restart, which `fly secrets set` causes, ends it.
PUSHOVER_HOLD = timedelta(hours=24)
# The kWh register counts as frozen when its newest value equals its value this long ago.
# Between 2026-08-27 and 2026-10-03 it never went longer than 13 minutes without changing.
FROZEN_REGISTER_WINDOW = timedelta(hours=2)

# Results of a Pushover request
ACCEPTED, REFUSED, FAILED, HELD = 'accepted', 'refused', 'failed', 'held'


def _utcnow():
    return datetime.now(timezone.utc)


def _parse_time(value):
    """An aware datetime from an ISO string (with or without 'Z'), or None."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        text = value[:-1] + '+00:00' if value.endswith('Z') else value
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError, AttributeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class DataStalenessMonitor:
    """Monitor data freshness and track state transitions"""

    def __init__(self, state_file=None, slack_webhook=None, stale_threshold_minutes=5,
                 pushover_token=None, pushover_user=None,
                 pushover_retry=60, pushover_expire=3600):
        """
        Initialize the monitor.

        Args:
            state_file: Path to JSON file for persisting state (default: $MONITOR_STATE_FILE,
                else /tmp/eagle_monitor_state.json; production sets /data/monitor_state.json)
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

        # Set by _load_state: when the present status began, whether Pushover accepted
        # the siren for this outage, and when it last accepted a message about it.
        self.status_since = None
        self.siren_accepted = False
        self.last_message_at = None
        self._pushover_hold_until = None
        self.previous_status = self._load_state()

        logger.info(f"DataStalenessMonitor initialized with threshold: {stale_threshold_minutes} minutes")

    # ---- state -------------------------------------------------------------

    def _load_state(self):
        """Load previous state from file. Returns the status."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                status = data.get('status')
                if status not in ('healthy', 'unhealthy'):
                    logger.warning(f"Unknown status {status!r} in {self.state_file}; treating as healthy")
                    return 'healthy'
                self.status_since = _parse_time(data.get('timestamp'))
                if status == 'unhealthy':
                    if 'siren_accepted' in data:
                        self.siren_accepted = bool(data['siren_accepted'])
                        self.last_message_at = _parse_time(data.get('last_message_at'))
                    else:
                        # A file from before the siren was tracked: an outage it records was
                        # announced by the code of the day, so do not sound it again.
                        self.siren_accepted = True
                        self.last_message_at = self.status_since
                    if self.siren_accepted and self.last_message_at is None:
                        self.last_message_at = _utcnow()
                return status
        except Exception as e:
            logger.warning(f"Failed to load state from {self.state_file}: {e}")
        return 'healthy'

    def _save_state(self, status):
        """Save state to file"""
        try:
            state_data = {
                'status': status,
                'timestamp': (self.status_since or _utcnow()).isoformat(),
                'siren_accepted': self.siren_accepted,
                'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            }
            os.makedirs(os.path.dirname(self.state_file) or '.', exist_ok=True)
            tmp = self.state_file + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(state_data, f)
            os.replace(tmp, self.state_file)
            logger.debug(f"State saved: {status}")
        except Exception as e:
            logger.error(f"Failed to save state to {self.state_file}: {e}")

    # ---- senders -----------------------------------------------------------

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
            # Not the exception text: for a requests error it holds the webhook URL,
            # which is a secret.
            status = getattr(getattr(e, 'response', None), 'status_code', None)
            logger.error(f"Failed to send Slack alert: {type(e).__name__} (status {status})")
            return False

    def send_pushover(self, message, title='Linknode Power Monitor Alert', priority=2, now=None):
        """Send one Pushover message. Returns ACCEPTED, REFUSED (a 4xx, or credentials
        not set: no further request for PUSHOVER_HOLD), FAILED (worth trying again) or
        HELD (inside that hold: nothing was sent)."""
        now = now or _utcnow()
        if self._pushover_hold_until and now < self._pushover_hold_until:
            return HELD
        if not (self.pushover_token and self.pushover_user):
            logger.warning("Pushover not configured, skipping alert")
            self._pushover_hold_until = now + PUSHOVER_HOLD
            return REFUSED

        payload = {
            'token': self.pushover_token,
            'user': self.pushover_user,
            'title': title,
            'message': message,
            'priority': priority,
        }
        if priority == 2:
            # Emergency: re-alerts every `retry` seconds until the user acknowledges
            # in the app, or `expire` seconds elapse.
            payload.update({'retry': self.pushover_retry, 'expire': self.pushover_expire,
                            'sound': 'siren'})
        try:
            response = requests.post(PUSHOVER_URL, data=payload, timeout=10)
            status = getattr(response, 'status_code', None)
            if isinstance(status, int) and 400 <= status < 500:
                logger.error(f"Pushover refused the message (HTTP {status}); "
                             f"not asking again for {PUSHOVER_HOLD}")
                self._pushover_hold_until = now + PUSHOVER_HOLD
                return REFUSED
            response.raise_for_status()
            logger.info(f"Pushover message sent successfully (priority {priority})")
            return ACCEPTED
        except Exception as e:
            status = getattr(getattr(e, 'response', None), 'status_code', None)
            logger.error(f"Failed to send Pushover alert: {type(e).__name__} (status {status})")
            return FAILED

    def _send_pushover_alert(self, message, title='Linknode Power Monitor Alert'):
        """Send an emergency (siren) push via Pushover that repeats until acknowledged."""
        return self.send_pushover(message, title=title, priority=2) == ACCEPTED

    # ---- the check ---------------------------------------------------------

    def check_data_freshness(self, stats_dict, now=None):
        """
        Check if data is fresh and handle state transitions.

        Args:
            stats_dict: last_data_received (ISO time of the newest power reading),
                last_power_reading (its watts), and optionally register_now and
                register_then (the kWh register's newest value and its value
                FROZEN_REGISTER_WINDOW ago). Other keys are ignored.
            now: the time of this run (default: the current time)

        Returns:
            tuple: (current_status, transitioned) - transitioned is True if state changed
        """
        now = now or _utcnow()
        if (self.previous_status == 'healthy' and self.status_since is not None
                and now - self.status_since < FROZEN_REGISTER_WINDOW):
            # A recovery less than the window ago: the register lookup still reaches
            # back over the outage, and a register that sat still through an outage (a
            # power cut) is not frozen. No verdict on the register yet.
            stats_dict = dict(stats_dict, register_now=None, register_then=None)
        current_status = self._evaluate_health(stats_dict, now)
        transitioned = current_status != self.previous_status

        if transitioned:
            logger.warning(f"Status transition: {self.previous_status} → {current_status}")
            self.status_since = now
            self.siren_accepted = False
            self.last_message_at = None
            self._pushover_hold_until = None      # a new outage asks again

            if current_status == 'unhealthy':
                # Going unhealthy
                message = self._outage_message(stats_dict, now)
                self._send_slack_alert(message, emoji='🚨')
                if self.send_pushover(message, priority=2, now=now) == ACCEPTED:
                    self.siren_accepted = True
                    self.last_message_at = now
            else:
                # Going healthy
                current_power = stats_dict.get('last_power_reading', 'N/A')
                last_update = stats_dict.get('last_data_received', 'N/A')
                message = f"Power meter is back online!\nCurrent: {current_power}W\nLast update: {last_update}"
                self._send_slack_alert(message, emoji='✅')

            # Save new state
            self.previous_status = current_status
            self._save_state(current_status)

        elif current_status == 'unhealthy':
            if not self.siren_accepted:
                # The siren has not got through yet. Only the siren is tried again:
                # Slack was posted once, at the change of state.
                message = self._outage_message(stats_dict, now)
                if self.send_pushover(message, priority=2, now=now) == ACCEPTED:
                    self.siren_accepted = True
                    self.last_message_at = now
                    self._save_state(current_status)
            elif self.last_message_at is None or now - self.last_message_at >= REMINDER_INTERVAL:
                since = self.status_since.strftime('%Y-%m-%d %H:%M UTC') if self.status_since else 'an earlier run'
                message = f"Still down since {since}.\n{self._outage_message(stats_dict, now)}"
                if self.send_pushover(message, priority=0, now=now) == ACCEPTED:
                    self.last_message_at = now
                    self._save_state(current_status)

        return current_status, transitioned

    def _classify(self, stats_dict, now=None):
        """(kind, reason) for an unhealthy feed, (None, None) for a healthy one.
        kind is 'no_data', 'stale', 'zero', 'frozen' or 'error'."""
        last_update = stats_dict.get('last_data_received')
        if not last_update:
            return 'no_data', "No data received yet"

        try:
            last_update_dt = _parse_time(last_update)
            if last_update_dt is None:
                raise ValueError(f"unreadable timestamp {last_update!r}")

            # Calculate age
            age = (now or _utcnow()) - last_update_dt
            age_minutes = age.total_seconds() / 60

            # Check if data is stale
            if age_minutes > self.stale_threshold_minutes:
                return 'stale', (f"Last data received {age_minutes:.1f} minutes ago "
                                 f"(threshold: {self.stale_threshold_minutes} minutes)")

            # Check if last power reading exists and is non-zero
            last_power = stats_dict.get('last_power_reading')
            if last_power is None or last_power == 0:
                return 'zero', f"Invalid power reading: {last_power}W"

            # Judged last, and only when the rules above pass. Once readings have
            # stopped for the whole window both register lookups return the same row,
            # so every long outage would meet this test: it must stay reported as stale.
            register_now = stats_dict.get('register_now')
            register_then = stats_dict.get('register_then')
            if register_now is not None and register_then is not None and register_now == register_then:
                hours = FROZEN_REGISTER_WINDOW.total_seconds() / 3600
                return 'frozen', (f"The meter's kWh register has not changed in over {hours:g} hours "
                                  f"(still {register_now} kWh), although readings keep arriving")

            return None, None

        except Exception as e:
            logger.error(f"Error evaluating health: {e}")
            return 'error', f"Error determining reason: {e}"

    def _evaluate_health(self, stats_dict, now=None):
        """
        Evaluate system health based on stats.

        Returns:
            'healthy' or 'unhealthy'
        """
        kind, reason = self._classify(stats_dict, now)
        if kind is None:
            return 'healthy'
        logger.warning(f"Feed unhealthy ({kind}): {reason}")
        return 'unhealthy'

    def _get_failure_reason(self, stats_dict, now=None):
        """Get human-readable reason for failure"""
        kind, reason = self._classify(stats_dict, now)
        return reason if kind is not None else "Unknown error"

    def _outage_message(self, stats_dict, now=None):
        """The alert text for an unhealthy feed."""
        kind, reason = self._classify(stats_dict, now)
        if kind == 'frozen':
            return f"Meter readings look frozen!\n{reason}"
        return f"Data is not arriving from power meter!\n{reason if kind is not None else 'Unknown error'}"


class WatchdogLiveness:
    """Reports a Pi watchdog that has stopped calling.

    The ingest service notes when a request with the watchdog's User-Agent last reached
    /health/data. When there has been none for `silence`, one normal-priority message
    goes out, delivered like the siren (tried again until Pushover accepts it, then
    repeated every 24 hours while the silence lasts), and one more when the requests
    resume. A run that finds the feed unhealthy sends nothing and restarts the clock: a
    Pi that is off is already reported, and one that has just come back has not called
    yet.

    It sees only a watchdog that has stopped calling. One that still calls and cannot
    alert looks alive from here.
    """

    TITLE = 'Linknode watchdog: silent'
    RECOVERED_TITLE = 'Linknode watchdog: calling again'

    def __init__(self, monitor, started, silence=timedelta(hours=6), load=None, save=None):
        """
        Args:
            monitor: the DataStalenessMonitor whose Pushover sender is used
            started: when this service started. With nothing saved, the silence is
                counted from here, so a watchdog that never calls is reported `silence`
                after the first deploy: not at once, and not never.
            load, save: callables that read and write the state dict (the store's meta
                table in production). Either may be None.
        """
        self.monitor = monitor
        self.silence = silence
        self._save = save
        state = {}
        if load is not None:
            try:
                state = load() or {}
            except Exception as e:
                logger.warning(f"Could not load the watchdog liveness state: {e}")
        if not isinstance(state, dict):
            state = {}
        saved_from = _parse_time(state.get('silence_from'))
        self.silence_from = saved_from or _parse_time(started) or _utcnow()
        self.alerted = bool(state.get('alerted'))
        self.alerted_at = _parse_time(state.get('alerted_at'))
        self.last_message_at = _parse_time(state.get('last_message_at'))
        if saved_from is None:
            # Nothing saved yet (the first deploy): keep the start time, so that a later
            # restart counts from here and not from its own start.
            self._store()

    def _store(self):
        if self._save is None:
            return
        try:
            self._save({
                'silence_from': self.silence_from.isoformat(),
                'alerted': self.alerted,
                'alerted_at': self.alerted_at.isoformat() if self.alerted_at else None,
                'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            })
        except Exception as e:
            # Logged and nothing more: a failed save must not abort the job.
            logger.warning(f"Could not save the watchdog liveness state: {e}")

    def check(self, last_seen, feed_status, now=None):
        """One run. last_seen: when the watchdog last called (datetime, ISO string or
        None); feed_status: 'healthy' or 'unhealthy', from the staleness check."""
        now = now or _utcnow()
        last_seen = _parse_time(last_seen)

        if feed_status != 'healthy':
            self.silence_from = now
            self._store()
            return

        if self.alerted:
            if last_seen is not None and (self.alerted_at is None or last_seen > self.alerted_at):
                # Calling again. The recovery message is tried once.
                self.monitor.send_pushover("The Pi watchdog is making its requests again.",
                                           title=self.RECOVERED_TITLE, priority=0, now=now)
                self.alerted = False
                self.alerted_at = None
                self.last_message_at = None
                self._store()
            elif (now - self.silence_from >= self.silence
                  and (self.last_message_at is None or now - self.last_message_at >= REMINDER_INTERVAL)):
                # The repeat waits out the restarted clock too: a Pi that has just come
                # back has not called yet.
                if self.monitor.send_pushover(self._message(last_seen, now), title=self.TITLE,
                                              priority=0, now=now) == ACCEPTED:
                    self.last_message_at = now
                    self._store()
            return

        reference = max(t for t in (last_seen, self.silence_from) if t is not None)
        if now - reference >= self.silence:
            if self.monitor.send_pushover(self._message(last_seen, now), title=self.TITLE,
                                          priority=0, now=now) == ACCEPTED:
                self.alerted = True
                self.alerted_at = now
                self.last_message_at = now
                self._store()

    def _message(self, last_seen, now):
        hours = self.silence.total_seconds() / 3600
        seen = (f"Its last request came at {last_seen.strftime('%Y-%m-%d %H:%M UTC')}."
                if last_seen else "It has not called since this service started.")
        return (f"No request from the Pi watchdog for over {hours:g} hours, while readings keep "
                f"arriving. {seen} Nothing is watching the ingest service or the site: check "
                f"linknode-watchdog.timer on the Pi.")
