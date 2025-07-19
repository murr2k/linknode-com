# EAGLE Configuration Debug

Looking at your EAGLE interface, I see:

**Current Configuration:**
- Label: Linknode
- URL: `/api/power-data`
- Format: JSON
- Status: Error (404)

**Issue:** You only have the URL path, but no hostname/protocol configured.

## Correct EAGLE Configuration

You need to configure ALL fields in the EAGLE upload destination:

### Option 1: Direct HTTP (Recommended for Testing)
- **Label**: Linknode Direct
- **Protocol**: HTTP
- **Hostname**: 119.9.118.22
- **URL**: /api/power-data
- **Port**: 30500
- **Username**: (leave empty)
- **Password**: (leave empty)
- **Format**: JSON

### Option 2: Via HTTPS (After Cloudflare Update)
- **Label**: Linknode HTTPS
- **Protocol**: HTTPS
- **Hostname**: linknode.com
- **URL**: /api/power-data
- **Port**: 443
- **Username**: (leave empty)
- **Password**: (leave empty)
- **Format**: JSON

### Option 3: Via Cloudflare Tunnel
- **Label**: Linknode Tunnel
- **Protocol**: HTTPS
- **Hostname**: daniel-holidays-diesel-gross.trycloudflare.com
- **URL**: /api/power-data
- **Port**: 443
- **Username**: (leave empty)
- **Password**: (leave empty)
- **Format**: JSON

## Steps to Fix:

1. Click "Add Upload Destination" (or edit the existing one)
2. Make sure to fill in ALL fields:
   - Protocol (HTTP or HTTPS)
   - Hostname (the IP or domain)
   - URL (the path)
   - Port (30500 for HTTP, 443 for HTTPS)
3. Save the configuration

The key issue is that EAGLE needs the complete endpoint information, not just the URL path.