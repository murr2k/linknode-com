# Eagle-200 Device Configuration Guide

## Overview
This guide explains how to configure your Eagle-200 energy monitor to send data to the Linknode monitoring system with Basic Authentication.

## Authentication Setup

### 1. Set Authentication Credentials in Fly.io

First, set the Basic Auth credentials that your Eagle device will use:

```bash
# Set the password (username is 'eagle' by default)
fly secrets set EAGLE_PASSWORD=your-secure-password-here --app linknode-eagle-monitor

# Optional: Change the username (default is 'eagle')
fly secrets set EAGLE_USERNAME=your-username --app linknode-eagle-monitor
```

### 2. Configure Eagle-200 Device

In your Eagle-200 web interface, add a new upload destination:

1. **Label**: `Linknode Monitor` (or any name you prefer)

2. **Protocol**: `HTTPS`

3. **Hostname**: `linknode-eagle-monitor.fly.dev`

4. **URL**: `/eagle`

5. **Port**: `443` (default HTTPS port)

6. **Username**: `eagle` (or the username you set)

7. **Password**: The password you set in step 1

8. **Format**: `XML (Raw)` or `XML (Simple)`
   - Raw XML provides more detailed data
   - Simple XML provides basic power readings

## Example Configuration

```
Label: Linknode Monitor
Protocol: HTTPS
Hostname: linknode-eagle-monitor.fly.dev
URL: /eagle
Port: 443
Username: eagle
Password: [your-secure-password]
Format: XML (Raw)
```

## Testing the Connection

After configuring, the Eagle device should start sending data immediately. You can verify it's working by:

1. **Check the Eagle device status** - It should show "Last Updated: Less than a minute ago"

2. **Check the monitor logs**:
   ```bash
   fly logs --app linknode-eagle-monitor
   ```
   You should see entries like:
   ```
   INFO - Received Eagle XML data
   INFO - Successfully wrote 1 point to InfluxDB
   ```

3. **Check the API stats** (requires API key):
   ```bash
   curl https://linknode-eagle-monitor.fly.dev/api/stats
   ```

## Security Notes

- Always use HTTPS protocol for secure data transmission
- Use a strong password (long, random string)
- The Basic Auth credentials are only for the Eagle device
- API endpoints (/api/*) still require API keys for access

## Troubleshooting

### "Authentication required" error
- Verify the username and password match what you set in Fly.io
- Check that EAGLE_PASSWORD is set: `fly secrets list --app linknode-eagle-monitor`

### No data appearing
- Verify the Eagle device shows "Connected" status
- Check the hostname is exactly: `linknode-eagle-monitor.fly.dev`
- Ensure the URL is exactly: `/eagle`
- Check logs for any error messages

### Rate limiting
- The system allows 60 requests per minute per device
- If you see rate limit errors, check if the Eagle is configured to send data too frequently

## API Access (for other applications)

While the Eagle device uses Basic Auth, other applications accessing the API should use API keys:

```bash
# Set an API key for programmatic access
fly secrets set EAGLE_API_KEY=your-api-key-here --app linknode-eagle-monitor

# Use it in requests
curl -H "X-API-Key: your-api-key-here" https://linknode-eagle-monitor.fly.dev/api/stats
```