#!/bin/bash

# Quick Cloudflare Tunnel - No login required!
# This creates a temporary tunnel with a random subdomain

BACKEND_URL="http://119.9.118.22:32304"
CLOUDFLARED_BIN="$HOME/bin/cloudflared"

echo "🚀 Starting Quick Cloudflare Tunnel"
echo "This will create a temporary public URL for your app"
echo ""
echo "Backend: $BACKEND_URL"
echo ""
echo "Starting tunnel... (Press Ctrl+C to stop)"
echo "=" * 50
echo ""

# Run the tunnel
# This will output a URL like: https://random-name.trycloudflare.com
$CLOUDFLARED_BIN tunnel --url $BACKEND_URL