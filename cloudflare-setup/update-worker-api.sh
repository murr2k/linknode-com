#!/bin/bash

echo "🔒 Cloudflare Worker API Update Script"
echo "====================================="
echo ""
echo "⚠️  SECURITY NOTICE: This script will use your Cloudflare API token."
echo "   Make sure to keep your token secure and never commit it to git."
echo ""

# Set your API token (passed as environment variable for security)
if [ -z "$CF_API_TOKEN" ]; then
    echo "❌ Error: CF_API_TOKEN environment variable not set"
    echo ""
    echo "Usage: CF_API_TOKEN='your-token-here' ./update-worker-api.sh"
    echo ""
    echo "For security, we don't store tokens in scripts."
    exit 1
fi

# Your account and zone details
ACCOUNT_EMAIL="your-email@example.com"  # Update this
ZONE_ID=""  # We'll fetch this
WORKER_NAME="linknode-com"  # Update if different

echo "📋 Step 1: Getting Zone ID for linknode.com..."
ZONE_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=linknode.com" \
     -H "Authorization: Bearer $CF_API_TOKEN" \
     -H "Content-Type: application/json")

ZONE_ID=$(echo "$ZONE_RESPONSE" | jq -r '.result[0].id // empty')

if [ -z "$ZONE_ID" ]; then
    echo "❌ Error: Could not fetch zone ID"
    echo "Response: $ZONE_RESPONSE"
    exit 1
fi

echo "✅ Zone ID: $ZONE_ID"
echo ""

echo "📋 Step 2: Updating Worker Script..."

# Read the worker.js file
WORKER_SCRIPT=$(cat worker.js | jq -Rs .)

# Create the API payload
cat > worker-update.json <<EOF
{
  "script": $WORKER_SCRIPT
}
EOF

# Update the worker
UPDATE_RESPONSE=$(curl -s -X PUT "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/workers/routes" \
     -H "Authorization: Bearer $CF_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d @worker-update.json)

# Clean up
rm -f worker-update.json

# Check response
SUCCESS=$(echo "$UPDATE_RESPONSE" | jq -r '.success // false')

if [ "$SUCCESS" = "true" ]; then
    echo "✅ Worker updated successfully!"
    echo ""
    echo "🧪 Testing the endpoint..."
    sleep 3
    TEST_RESPONSE=$(curl -s -w "\\nHTTP_CODE:%{http_code}" https://linknode.com/api/power-data/test)
    echo "$TEST_RESPONSE"
else
    echo "❌ Error updating worker"
    echo "Response: $UPDATE_RESPONSE"
fi

echo ""
echo "🔒 Security reminder: Clear your terminal history if you entered the token directly"
echo "   Run: history -c"