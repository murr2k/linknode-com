#!/bin/bash

# Cloudflare Tunnel Setup via API
# This creates a tunnel without needing browser login

set -e
source .env

# Configuration
TUNNEL_NAME="linknode-tunnel"
DOMAIN="linknode.com"
BACKEND_URL="http://119.9.118.22:32304"
ACCOUNT_ID="9facb8af1cf22a222cd876b841790ddd"
ZONE_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=${DOMAIN}" \
  -H "Authorization: Bearer ${CF_API_TOKEN}" | jq -r '.result[0].id')

echo "🚀 Setting up Cloudflare Tunnel via API"
echo "Domain: $DOMAIN"
echo "Zone ID: $ZONE_ID"
echo ""

# Generate a secret
TUNNEL_SECRET=$(openssl rand -base64 32)

# Create tunnel
echo "Creating tunnel..."
TUNNEL_CREATE=$(curl -s -X POST \
  "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/tunnels" \
  -H "Authorization: Bearer ${CF_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data "{\"name\":\"${TUNNEL_NAME}\",\"tunnel_secret\":\"${TUNNEL_SECRET}\"}")

# Debug response
echo "Tunnel creation response:"
echo "$TUNNEL_CREATE" | jq .

TUNNEL_ID=$(echo "$TUNNEL_CREATE" | jq -r '.result.id // empty')
TUNNEL_TOKEN=$(echo "$TUNNEL_CREATE" | jq -r '.result.token // empty')

if [ "$TUNNEL_ID" == "null" ]; then
  # Check if tunnel already exists
  echo "Checking existing tunnels..."
  EXISTING=$(curl -s -X GET \
    "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/tunnels" \
    -H "Authorization: Bearer ${CF_API_TOKEN}")
  
  TUNNEL_ID=$(echo "$EXISTING" | jq -r ".result[] | select(.name == \"${TUNNEL_NAME}\") | .id")
  
  if [ -n "$TUNNEL_ID" ]; then
    echo "✅ Using existing tunnel: $TUNNEL_ID"
    
    # Get the token (you'll need to have saved it from initial creation)
    echo "⚠️  Note: For existing tunnels, you need the original token to run it."
    echo "If you don't have it, delete the tunnel and recreate it."
  else
    echo "❌ Failed to create tunnel"
    echo "$TUNNEL_CREATE" | jq .
    exit 1
  fi
else
  echo "✅ Created tunnel: $TUNNEL_ID"
  echo ""
  echo "🔑 IMPORTANT: Save this token, you'll need it to run the tunnel:"
  echo "$TUNNEL_TOKEN"
  echo ""
  
  # Save token to file
  echo "$TUNNEL_TOKEN" > tunnel-token.txt
  echo "Token saved to: tunnel-token.txt"
fi

# Create DNS record for tunnel
echo ""
echo "Creating DNS CNAME record..."

# First check if record exists
EXISTING_DNS=$(curl -s -X GET \
  "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records?type=CNAME&name=${DOMAIN}" \
  -H "Authorization: Bearer ${CF_API_TOKEN}")

DNS_ID=$(echo "$EXISTING_DNS" | jq -r '.result[0].id')

if [ "$DNS_ID" != "null" ]; then
  # Update existing record
  curl -s -X PUT \
    "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records/${DNS_ID}" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "Content-Type: application/json" \
    --data "{\"type\":\"CNAME\",\"name\":\"${DOMAIN}\",\"content\":\"${TUNNEL_ID}.cfargotunnel.com\",\"proxied\":true}" \
    > /dev/null
  echo "✅ Updated DNS record"
else
  # Create new record
  curl -s -X POST \
    "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records" \
    -H "Authorization: Bearer ${CF_API_TOKEN}" \
    -H "Content-Type: application/json" \
    --data "{\"type\":\"CNAME\",\"name\":\"${DOMAIN}\",\"content\":\"${TUNNEL_ID}.cfargotunnel.com\",\"proxied\":true}" \
    > /dev/null
  echo "✅ Created DNS record"
fi

# Create config for the tunnel
echo ""
echo "Creating tunnel configuration..."

cat > tunnel-config.yml << EOF
url: ${BACKEND_URL}
tunnel: ${TUNNEL_ID}
credentials-file: tunnel-creds.json
EOF

# If we have a new token, create the credentials file
if [ -n "$TUNNEL_TOKEN" ] && [ "$TUNNEL_TOKEN" != "null" ]; then
  cat > tunnel-creds.json << EOF
{
  "AccountTag": "${ACCOUNT_ID}",
  "TunnelSecret": "$(echo "$TUNNEL_CREATE" | jq -r '.result.tunnel_secret')",
  "TunnelID": "${TUNNEL_ID}"
}
EOF
  echo "✅ Created tunnel credentials file"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To run the tunnel with the token:"
echo "  ~/bin/cloudflared tunnel run --token $TUNNEL_TOKEN"
echo ""
echo "Or if you have the credentials file:"
echo "  ~/bin/cloudflared tunnel --config tunnel-config.yml run"
echo ""
echo "Your site will be available at: https://${DOMAIN}"