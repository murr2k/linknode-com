# Update to latest Grafana to fix DOMPurify vulnerability (CVE-2024-47875)
# Previous version 10.2.0 contained vulnerable DOMPurify 2.4.5
FROM grafana/grafana:11.4.0

# Copy provisioning files first
COPY --chown=grafana:root provisioning /etc/grafana/provisioning

# Copy custom configuration
COPY --chown=grafana:root grafana.ini /etc/grafana/grafana.ini