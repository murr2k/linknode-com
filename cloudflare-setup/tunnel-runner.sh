#!/bin/bash

# Cloudflare Tunnel Runner Script
# This runs a tunnel using a pre-existing configuration

CLOUDFLARED_BIN="$HOME/bin/cloudflared"
TUNNEL_NAME="linknode-tunnel"
BACKEND_URL="http://119.9.118.22:32304"

echo "🚀 Cloudflare Tunnel Runner for linknode.com"
echo ""

# Check if we have a saved token
if [ -f "tunnel-token.txt" ]; then
    TOKEN=$(cat tunnel-token.txt)
    if [ -n "$TOKEN" ]; then
        echo "✅ Found saved tunnel token"
        echo ""
        echo "Starting tunnel with token..."
        echo "Your site will be available at: https://linknode.com"
        echo ""
        echo "Press Ctrl+C to stop"
        echo "="*50
        exec $CLOUDFLARED_BIN tunnel run --token "$TOKEN"
    fi
fi

# Check if we have a config file
if [ -f "$HOME/.cloudflared/config.yml" ]; then
    echo "✅ Found tunnel configuration"
    echo ""
    echo "Starting tunnel..."
    echo "Your site will be available at: https://linknode.com"
    echo ""
    echo "Press Ctrl+C to stop"
    echo "="*50
    exec $CLOUDFLARED_BIN tunnel run $TUNNEL_NAME
fi

# Otherwise, create a quick connector tunnel
echo "No saved configuration found."
echo ""
echo "Creating a Cloudflare Tunnel connector..."
echo "This will open a browser for authentication."
echo ""

# Create a connector that will set up everything
$CLOUDFLARED_BIN tunnel create linknode-tunnel || true

# Create config
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << EOF
tunnel: linknode-tunnel
credentials-file: $HOME/.cloudflared/linknode-tunnel.json

ingress:
  - hostname: linknode.com
    service: $BACKEND_URL
  - hostname: www.linknode.com
    service: $BACKEND_URL
  - service: http_status:404
EOF

echo ""
echo "Now run: $CLOUDFLARED_BIN tunnel route dns linknode-tunnel linknode.com"
echo "Then run this script again to start the tunnel"