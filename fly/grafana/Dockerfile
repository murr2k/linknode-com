FROM grafana/grafana:10.2.0

# Use root user to set permissions
USER root

# Copy custom configuration
COPY grafana.ini /etc/grafana/grafana.ini

# Copy provisioning files  
COPY provisioning /etc/grafana/provisioning

# Set proper permissions
RUN chown -R grafana:root /etc/grafana && \
    chmod -R 755 /usr/share/grafana && \
    chown -R grafana:root /var/lib/grafana

# Switch back to grafana user
USER 472

# Expose Grafana port
EXPOSE 3000