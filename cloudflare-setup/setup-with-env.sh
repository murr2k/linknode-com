#!/bin/bash

# Cloudflare automated setup that reads API token from .env file
# This keeps your credentials secure and out of the script

set -e

# Configuration
DOMAIN="linknode.com"
BACKEND_URL="http://119.9.118.22:32304"
WORKER_NAME="linknode-proxy"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Cloudflare Automated Setup for ${DOMAIN}${NC}"
echo ""

# Change to script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found${NC}"
    echo "Please create a .env file with your Cloudflare API token:"
    echo ""
    echo "CF_API_TOKEN=your-api-token-here"
    echo "CF_EMAIL=your-email@example.com"
    exit 1
fi

# Load environment variables
source .env

# Verify token is set
if [ -z "$CF_API_TOKEN" ]; then
    echo -e "${RED}❌ CF_API_TOKEN not found in .env file${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Loaded API credentials from .env${NC}"
echo -e "Email: ${CF_EMAIL}"
echo ""

# Check for required tools
for tool in curl jq openssl; do
    if ! command -v $tool &> /dev/null; then
        echo -e "${RED}❌ Required tool '$tool' is not installed${NC}"
        exit 1
    fi
done

# Check if worker.js exists
if [ ! -f "worker.js" ]; then
    echo -e "${RED}❌ worker.js not found${NC}"
    exit 1
fi

# Function to make API calls
cf_api() {
    local endpoint=$1
    local method=${2:-GET}
    local data=${3:-}
    
    if [ -n "$data" ]; then
        curl -s -X "$method" \
            "https://api.cloudflare.com/client/v4/$endpoint" \
            -H "Authorization: Bearer $CF_API_TOKEN" \
            -H "Content-Type: application/json" \
            --data "$data"
    else
        curl -s -X "$method" \
            "https://api.cloudflare.com/client/v4/$endpoint" \
            -H "Authorization: Bearer $CF_API_TOKEN" \
            -H "Content-Type: application/json"
    fi
}

echo -e "${BLUE}Step 1: Verifying API token...${NC}"
# First get account ID for verification
ACCOUNT_CHECK=$(cf_api "accounts")
ACCOUNT_ID=$(echo "$ACCOUNT_CHECK" | jq -r '.result[0].id' 2>/dev/null)
if [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" == "null" ]; then
    VERIFY=$(cf_api "user/tokens/verify")
else
    VERIFY=$(cf_api "accounts/${ACCOUNT_ID}/tokens/verify")
fi
if echo "$VERIFY" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ API token is valid${NC}"
else
    echo -e "${RED}❌ API token verification failed${NC}"
    echo "$VERIFY" | jq . 2>/dev/null || echo "$VERIFY"
    exit 1
fi

echo -e "\n${BLUE}Step 2: Getting Zone ID for ${DOMAIN}...${NC}"
ZONES=$(cf_api "zones?name=${DOMAIN}")
ZONE_ID=$(echo "$ZONES" | jq -r '.result[0].id' 2>/dev/null)

if [ "$ZONE_ID" == "null" ] || [ -z "$ZONE_ID" ]; then
    echo -e "${RED}❌ Domain ${DOMAIN} not found${NC}"
    echo "Have you added ${DOMAIN} to Cloudflare yet?"
    exit 1
fi

echo -e "${GREEN}✅ Zone ID: ${ZONE_ID}${NC}"

echo -e "\n${BLUE}Step 3: Getting Account ID...${NC}"
ACCOUNT=$(cf_api "accounts")
ACCOUNT_ID=$(echo "$ACCOUNT" | jq -r '.result[0].id' 2>/dev/null)
echo -e "${GREEN}✅ Account ID: ${ACCOUNT_ID}${NC}"

echo -e "\n${BLUE}Step 4: Uploading Worker script...${NC}"

# Create multipart form data
BOUNDARY="----FormBoundary$(openssl rand -hex 16)"
TEMP_FILE=$(mktemp)

cat > "$TEMP_FILE" <<EOF
------${BOUNDARY}
Content-Disposition: form-data; name="worker.js"; filename="worker.js"
Content-Type: application/javascript

$(cat worker.js)
------${BOUNDARY}
Content-Disposition: form-data; name="metadata"

{"main_module":"worker.js"}
------${BOUNDARY}--
EOF

# Upload worker
WORKER_CREATE=$(curl -s -X PUT \
    "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/scripts/${WORKER_NAME}" \
    -H "Authorization: Bearer $CF_API_TOKEN" \
    -H "Content-Type: multipart/form-data; boundary=----${BOUNDARY}" \
    --data-binary "@$TEMP_FILE")

rm -f "$TEMP_FILE"

if echo "$WORKER_CREATE" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ Worker script uploaded${NC}"
else
    echo -e "${RED}❌ Failed to upload worker${NC}"
    echo "$WORKER_CREATE" | jq . 2>/dev/null || echo "$WORKER_CREATE"
    exit 1
fi

echo -e "\n${BLUE}Step 5: Configuring DNS records...${NC}"

# Update A record
update_dns_record() {
    local record_type=$1
    local record_name=$2
    local record_content=$3
    
    local existing=$(cf_api "zones/${ZONE_ID}/dns_records?type=${record_type}&name=${record_name}")
    local record_id=$(echo "$existing" | jq -r '.result[0].id' 2>/dev/null)
    
    local data="{\"type\":\"${record_type}\",\"name\":\"${record_name}\",\"content\":\"${record_content}\",\"ttl\":1,\"proxied\":true}"
    
    if [ "$record_id" != "null" ] && [ -n "$record_id" ]; then
        echo "  Updating ${record_type} record..."
        cf_api "zones/${ZONE_ID}/dns_records/${record_id}" "PUT" "$data" > /dev/null
    else
        echo "  Creating ${record_type} record..."
        cf_api "zones/${ZONE_ID}/dns_records" "POST" "$data" > /dev/null
    fi
    echo -e "  ${GREEN}✅ ${record_type} record configured${NC}"
}

update_dns_record "A" "${DOMAIN}" "192.0.2.1"
update_dns_record "CNAME" "www.${DOMAIN}" "${DOMAIN}"

echo -e "\n${BLUE}Step 6: Creating Worker route...${NC}"

# Remove existing routes
EXISTING_ROUTES=$(cf_api "zones/${ZONE_ID}/workers/routes")
ROUTE_IDS=$(echo "$EXISTING_ROUTES" | jq -r ".result[] | select(.pattern == \"*${DOMAIN}/*\") | .id" 2>/dev/null)

if [ -n "$ROUTE_IDS" ]; then
    while IFS= read -r route_id; do
        cf_api "zones/${ZONE_ID}/workers/routes/${route_id}" "DELETE" > /dev/null
    done <<< "$ROUTE_IDS"
fi

# Create new route
ROUTE=$(cf_api "zones/${ZONE_ID}/workers/routes" "POST" \
    "{\"pattern\":\"*${DOMAIN}/*\",\"script\":\"${WORKER_NAME}\"}")

echo -e "${GREEN}✅ Worker route configured${NC}"

echo -e "\n${BLUE}Step 7: Configuring SSL...${NC}"

cf_api "zones/${ZONE_ID}/settings/ssl" "PATCH" '{"value":"flexible"}' > /dev/null
echo -e "${GREEN}✅ SSL mode set to Flexible${NC}"

cf_api "zones/${ZONE_ID}/settings/always_use_https" "PATCH" '{"value":"on"}' > /dev/null
echo -e "${GREEN}✅ Always Use HTTPS enabled${NC}"

# Get nameservers
NS_INFO=$(cf_api "zones/${ZONE_ID}")
NS1=$(echo "$NS_INFO" | jq -r '.result.name_servers[0]' 2>/dev/null)
NS2=$(echo "$NS_INFO" | jq -r '.result.name_servers[1]' 2>/dev/null)

echo -e "\n${GREEN}🎉 Setup Complete!${NC}"
echo -e "\n${YELLOW}Update your nameservers at GoDaddy:${NC}"
echo -e "  ${BLUE}Nameserver 1:${NC} $NS1"
echo -e "  ${BLUE}Nameserver 2:${NC} $NS2"
echo -e "\n${BLUE}Your site will be available at:${NC}"
echo -e "  https://${DOMAIN}"
echo -e "\n${YELLOW}DNS propagation check:${NC}"
echo -e "  https://dnschecker.org/#NS/${DOMAIN}"