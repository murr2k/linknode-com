#!/bin/bash

# Cloudflare Tunnel Setup Script
set -e

# Configuration
TUNNEL_NAME="linknode-tunnel"
HOSTNAME="linknode.com"
BACKEND_URL="http://119.9.118.22:32304"
CLOUDFLARED_BIN="$HOME/bin/cloudflared"

echo "🚀 Setting up Cloudflare Tunnel for $HOSTNAME"
echo ""

# Check if cloudflared exists
if [ ! -f "$CLOUDFLARED_BIN" ]; then
    echo "❌ cloudflared not found at $CLOUDFLARED_BIN"
    echo "Please run: wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O ~/bin/cloudflared && chmod +x ~/bin/cloudflared"
    exit 1
fi

# Create config directory
mkdir -p ~/.cloudflared

# Check if we need to login
if [ ! -f ~/.cloudflared/cert.pem ]; then
    echo "📝 First time setup - you'll need to login to Cloudflare"
    echo "A browser window will open. Please login and select your domain."
    echo ""
    read -p "Press Enter to continue..."
    $CLOUDFLARED_BIN tunnel login
fi

# Check if tunnel already exists
EXISTING_TUNNEL=$($CLOUDFLARED_BIN tunnel list 2>/dev/null | grep "$TUNNEL_NAME" || true)

if [ -z "$EXISTING_TUNNEL" ]; then
    echo "🔧 Creating new tunnel: $TUNNEL_NAME"
    $CLOUDFLARED_BIN tunnel create $TUNNEL_NAME
else
    echo "✅ Tunnel $TUNNEL_NAME already exists"
fi

# Get tunnel ID
TUNNEL_ID=$($CLOUDFLARED_BIN tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
echo "🆔 Tunnel ID: $TUNNEL_ID"

# Create config file
CONFIG_FILE="$HOME/.cloudflared/config.yml"
echo "📄 Creating config file: $CONFIG_FILE"

cat > "$CONFIG_FILE" << EOF
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: $HOSTNAME
    service: $BACKEND_URL
  - hostname: www.$HOSTNAME
    service: $BACKEND_URL
  - service: http_status:404
EOF

echo "🌐 Setting up DNS routes..."

# Remove existing DNS routes if any
echo "Cleaning up any existing DNS routes..."
$CLOUDFLARED_BIN tunnel route dns --overwrite-dns $TUNNEL_NAME $HOSTNAME || true
$CLOUDFLARED_BIN tunnel route dns --overwrite-dns $TUNNEL_NAME www.$HOSTNAME || true

echo ""
echo "✅ Tunnel setup complete!"
echo ""
echo "To run the tunnel:"
echo "  $CLOUDFLARED_BIN tunnel run $TUNNEL_NAME"
echo ""
echo "To run in background:"
echo "  nohup $CLOUDFLARED_BIN tunnel run $TUNNEL_NAME > tunnel.log 2>&1 &"
echo ""
echo "To install as a systemd service (requires sudo):"
echo "  sudo $CLOUDFLARED_BIN service install"
echo "  sudo systemctl start cloudflared"