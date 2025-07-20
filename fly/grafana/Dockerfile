FROM grafana/grafana:10.2.0

# Copy provisioning files first
COPY --chown=grafana:root provisioning /etc/grafana/provisioning

# Copy custom configuration
COPY --chown=grafana:root grafana.ini /etc/grafana/grafana.ini