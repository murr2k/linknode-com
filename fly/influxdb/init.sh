#!/bin/sh
set -e

# Check if InfluxDB is already initialized
if [ ! -f /var/lib/influxdb2/.influxdbv2 ]; then
    echo "Initializing InfluxDB..."
    
    # Set up initial configuration
    export INFLUXD_INIT_MODE=setup
    export INFLUXD_INIT_USERNAME=admin
    export INFLUXD_INIT_PASSWORD=${INFLUXDB_ADMIN_PASSWORD}
    export INFLUXD_INIT_ORG=linknode
    export INFLUXD_INIT_BUCKET=energy
    export INFLUXD_INIT_RETENTION=30d
    
    # Start InfluxDB in setup mode
    influxd &
    INFLUX_PID=$!
    
    # Wait for InfluxDB to be ready
    echo "Waiting for InfluxDB to be ready..."
    until influx ping 2>/dev/null; do
        sleep 1
    done
    
    # Create the energy bucket with 30-day retention
    influx bucket create \
        --name energy \
        --org linknode \
        --retention 30d \
        --description "Energy monitoring data with 30-day retention" || true
    
    # Create an admin token
    ADMIN_TOKEN=$(influx auth create \
        --org linknode \
        --description "Admin token for linknode" \
        --read-buckets \
        --write-buckets \
        --read-tasks \
        --write-tasks \
        --read-orgs \
        --write-orgs \
        --json | jq -r '.token')
    
    # Store the token as a Fly secret (output to stdout for manual configuration)
    echo "==================================================================================="
    echo "IMPORTANT: Save this admin token and set it as a Fly secret:"
    echo ""
    echo "fly secrets set INFLUXDB_TOKEN='$ADMIN_TOKEN' --app linknode-influxdb"
    echo ""
    echo "Also set this token in your other Fly apps that need to access InfluxDB:"
    echo "fly secrets set INFLUXDB_TOKEN='$ADMIN_TOKEN' --app linknode-eagle-monitor"
    echo "fly secrets set INFLUXDB_TOKEN='$ADMIN_TOKEN' --app linknode-grafana"
    echo "==================================================================================="
    
    # Stop the setup instance
    kill $INFLUX_PID
    wait $INFLUX_PID 2>/dev/null || true
    
    echo "InfluxDB initialization complete!"
else
    echo "InfluxDB already initialized, skipping setup..."
fi

# Start InfluxDB normally
exec influxd