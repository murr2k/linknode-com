# Eagle-200 XML Monitor for Fly.io

This service receives XML POST data from an Eagle-200 energy monitor device and stores it in InfluxDB.

## Features

- Accepts XML POST requests at `/eagle` endpoint
- Parses Eagle-200 XML format for power and energy data
- Writes data to InfluxDB with proper timestamps
- Provides statistics endpoint at `/api/stats`
- Health check endpoint at `/health`
- Minimal resource usage (256MB RAM)

## Configuration

The Eagle-200 device should be configured to POST data to:
```
http://linknode-eagle-monitor.fly.dev/eagle
```

## Deployment

1. Deploy the monitor:
   ```bash
   ./deploy.sh
   ```

2. Configure your Eagle-200 device to send data to the endpoint above.

## API Endpoints

- `POST /eagle` - Receives XML data from Eagle-200
- `GET /` - Service information
- `GET /api/stats` - Monitor statistics
- `GET /health` - Health check

## Environment Variables

- `INFLUXDB_URL` - InfluxDB URL (default: http://linknode-influxdb.internal:8086)
- `INFLUXDB_TOKEN` - Authentication token (set as secret)
- `INFLUXDB_ORG` - Organization name (default: linknode)
- `INFLUXDB_BUCKET` - Bucket name (default: energy)

## Data Format

The monitor handles two types of Eagle-200 messages:

1. **InstantaneousDemand** - Current power consumption in watts
2. **CurrentSummationDelivered** - Total energy consumed in kWh

Data is stored in InfluxDB with:
- Measurement: `energy_monitor`
- Tags: `device_mac`, `meter_mac`, `message_type`
- Fields: `power_w` (watts) or `energy_kwh` (kilowatt-hours)