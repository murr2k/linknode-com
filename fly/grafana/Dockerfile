FROM grafana/grafana:10.2.0

# Copy custom configuration
COPY --chown=472:472 grafana.ini /etc/grafana/grafana.ini

# Copy provisioning files  
COPY --chown=472:472 provisioning /etc/grafana/provisioning

# Expose Grafana port
EXPOSE 3000