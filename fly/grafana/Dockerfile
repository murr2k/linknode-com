FROM grafana/grafana:10.2.0

# Switch to root to modify files
USER root

# Copy custom configuration
COPY grafana.ini /etc/grafana/grafana.ini

# Copy provisioning files
COPY provisioning /etc/grafana/provisioning

# Create a script to fix permissions on startup
RUN echo '#!/bin/sh\n\
chown -R 472:0 /var/lib/grafana /etc/grafana\n\
chmod -R g+rwX /var/lib/grafana /etc/grafana\n\
exec su-exec grafana /run.sh' > /startup.sh && \
    chmod +x /startup.sh

# Install su-exec for proper user switching
RUN apk add --no-cache su-exec

# Switch back to grafana user
USER 472

# Expose Grafana port
EXPOSE 3000

# Use our startup script
ENTRYPOINT ["/startup.sh"]