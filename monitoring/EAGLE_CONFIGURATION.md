# EAGLE Device Configuration Guide

This guide explains how to configure your Rainforest Automation EAGLE-200 device to send power monitoring data to the Kubernetes monitoring stack.

## Prerequisites

- EAGLE device connected to your smart meter
- Access to the EAGLE web interface
- The monitoring stack deployed and running

## Configuration Steps

### 1. Access EAGLE Web Interface

1. Connect to your EAGLE device's web interface (typically at `http://eagle-XXXXXX.local` or its IP address)
2. Log in with your credentials

### 2. Navigate to Upload Destinations

1. Go to **Settings** → **Cloud** → **Upload Destinations**
2. Click **Add Upload Destination**

### 3. Configure the Upload Destination

Enter the following settings:

#### For Production (via Cloudflare - Recommended)
- **Label**: `Kubernetes Power Monitor`
- **Protocol**: `HTTPS`
- **Hostname**: `linknode.com`
- **URL**: `/api/power-data`
- **Port**: `443`
- **Username**: (leave blank)
- **Password**: (leave blank)
- **Format**: `JSON`

#### For Testing (Direct Access)
- **Label**: `K8s Monitor Direct`
- **Protocol**: `HTTP`
- **Hostname**: `119.9.118.22`
- **URL**: `/api/power-data`
- **Port**: `30500`
- **Username**: (leave blank)
- **Password**: (leave blank)
- **Format**: `JSON`

### 4. Save and Test

1. Click **Save** to save the configuration
2. The status should show "Initializing" and then "OK"
3. Check the monitoring dashboard to verify data is being received

## Expected JSON Format

The EAGLE device sends data in the following format:

```json
{
    "DeviceMacId": "0xd8d5b9000000xxxx",
    "MeterMacId": "0x00135003007xxxxx",
    "TimeStamp": "2024-01-15T10:30:00Z",
    "Demand": 1234,
    "CurrentSummation": 12345678,
    "CurrentSummationDelivered": 12345678,
    "CurrentSummationReceived": 0,
    "Multiplier": 1,
    "Divisor": 1000,
    "DigitsRight": 3,
    "DigitsLeft": 6,
    "SuppressLeadingZero": "Y"
}
```

## Monitoring Dashboard Access

Once configured, you can view your power data at:

1. **API Status**: https://linknode.com/api/power-data/test
2. **Latest Reading**: https://linknode.com/api/power-data/latest
3. **Grafana Dashboard**: http://119.9.118.22:30300
   - Username: `admin`
   - Password: `admin`

## Troubleshooting

### No Data Appearing

1. Check EAGLE status shows "OK" for the upload destination
2. Verify network connectivity from EAGLE to the internet
3. Check Flask app logs: `kubectl logs -l app=demo-app-monitoring -n demo-app`
4. Test with curl:
   ```bash
   curl -X POST https://linknode.com/api/power-data \
     -H "Content-Type: application/json" \
     -d '{"DeviceMacId":"test","Demand":1000,"Multiplier":1,"Divisor":1000}'
   ```

### Authentication Errors

The current setup doesn't require authentication. If you see auth errors, ensure username/password fields are empty in EAGLE config.

### Connection Timeouts

- Try using the direct HTTP endpoint for testing
- Check if your firewall allows outbound HTTPS/HTTP connections
- Verify the Kubernetes services are running: `kubectl get svc -n demo-app`

## Data Retention

By default, InfluxDB is configured to retain data for 30 days. To modify retention:

```bash
kubectl exec -it deploy/influxdb -n demo-app -- influx bucket update \
  --id $(influx bucket list | grep power_metrics | awk '{print $1}') \
  --retention 90d
```

## Security Considerations

For production use, consider:

1. Adding authentication to the API endpoint
2. Using HTTPS exclusively (already enabled via Cloudflare)
3. Implementing rate limiting
4. Adding input validation for the JSON data

## Support

For issues or questions:
1. Check application logs: `kubectl logs -f -l app=demo-app-monitoring -n demo-app`
2. Verify InfluxDB status: `kubectl logs -f -l app=influxdb -n demo-app`
3. Test the endpoint manually using the provided test script