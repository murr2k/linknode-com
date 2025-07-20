#!/bin/bash
set -e

# This script runs on first startup when the directory is empty
if [ ! -f /var/lib/influxdb2/.influxdbv2/configs ]; then
    echo "First run - initializing InfluxDB..."
    
    # Start influxd in background
    influxd &
    INFLUX_PID=$!
    
    # Wait for it to be ready
    echo "Waiting for InfluxDB to start..."
    until influx ping; do
        sleep 1
    done
    
    echo "Setting up InfluxDB..."
    
    # Use environment variables for setup
    influx setup \
        --username admin \
        --password adminpassword123 \
        --token linknode-token-20250720 \
        --org linknode \
        --bucket energy \
        --retention 720h \
        --force
    
    echo "InfluxDB setup complete!"
    echo "Admin token: linknode-token-20250720"
    
    # Stop the background influxd
    kill $INFLUX_PID
    wait $INFLUX_PID
fi

echo "Starting InfluxDB..."
exec influxd