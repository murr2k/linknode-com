FROM grafana/grafana:10.2.0

# Copy custom configuration
COPY grafana.ini /etc/grafana/grafana.ini

# Copy provisioning files  
COPY provisioning /etc/grafana/provisioning

# Expose Grafana port
EXPOSE 3000