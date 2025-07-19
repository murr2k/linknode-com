#!/bin/bash

# Secure Cloudflare automated setup for linknode.com
# This script prompts for the API token instead of hardcoding it

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
echo -e "${YELLOW}This script will configure Cloudflare to proxy your domain to ${BACKEND_URL}${NC}"
echo ""

# Check for required tools
for tool in curl jq openssl; do
    if ! command -v $tool &> /dev/null; then
        echo -e "${RED}❌ Required tool '$tool' is not installed${NC}"
        exit 1
    fi
done

# Get API token
echo -e "${BLUE}Please enter your Cloudflare API token:${NC}"
read -s CF_API_TOKEN
echo ""

if [ -z "$CF_API_TOKEN" ]; then
    echo -e "${RED}❌ API token cannot be empty${NC}"
    exit 1
fi

# Change to script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if worker.js exists
if [ ! -f "worker.js" ]; then
    echo -e "${RED}❌ worker.js not found in current directory${NC}"
    echo "Please run this script from the cloudflare-setup directory"
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
VERIFY=$(cf_api "user/tokens/verify")
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
    echo -e "${RED}❌ Domain ${DOMAIN} not found in your Cloudflare account${NC}"
    echo "Make sure you've:"
    echo "1. Added ${DOMAIN} to Cloudflare"
    echo "2. Changed nameservers at your registrar"
    exit 1
fi

echo -e "${GREEN}✅ Zone ID: ${ZONE_ID}${NC}"

echo -e "\n${BLUE}Step 3: Getting Account ID...${NC}"
ACCOUNT=$(cf_api "accounts")
ACCOUNT_ID=$(echo "$ACCOUNT" | jq -r '.result[0].id' 2>/dev/null)

if [ "$ACCOUNT_ID" == "null" ] || [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}❌ Could not get account ID${NC}"
    exit 1
fi

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
    echo -e "${GREEN}✅ Worker script uploaded successfully${NC}"
else
    echo -e "${RED}❌ Failed to upload worker${NC}"
    echo "$WORKER_CREATE" | jq . 2>/dev/null || echo "$WORKER_CREATE"
    exit 1
fi

echo -e "\n${BLUE}Step 5: Configuring DNS records...${NC}"

# Function to create/update DNS record
update_dns_record() {
    local record_type=$1
    local record_name=$2
    local record_content=$3
    
    # Get existing record
    local existing=$(cf_api "zones/${ZONE_ID}/dns_records?type=${record_type}&name=${record_name}")
    local record_id=$(echo "$existing" | jq -r '.result[0].id' 2>/dev/null)
    
    local data="{\"type\":\"${record_type}\",\"name\":\"${record_name}\",\"content\":\"${record_content}\",\"ttl\":1,\"proxied\":true}"
    
    if [ "$record_id" != "null" ] && [ -n "$record_id" ]; then
        echo "  Updating existing ${record_type} record..."
        local result=$(cf_api "zones/${ZONE_ID}/dns_records/${record_id}" "PUT" "$data")
    else
        echo "  Creating new ${record_type} record..."
        local result=$(cf_api "zones/${ZONE_ID}/dns_records" "POST" "$data")
    fi
    
    if echo "$result" | grep -q '"success":true'; then
        echo -e "  ${GREEN}✅ ${record_type} record configured${NC}"
    else
        echo -e "  ${RED}❌ Failed to configure ${record_type} record${NC}"
        return 1
    fi
}

# Configure DNS records
update_dns_record "A" "${DOMAIN}" "192.0.2.1"
update_dns_record "CNAME" "www.${DOMAIN}" "${DOMAIN}"

echo -e "\n${BLUE}Step 6: Creating Worker route...${NC}"

# Delete existing routes for this pattern
EXISTING_ROUTES=$(cf_api "zones/${ZONE_ID}/workers/routes")
ROUTE_IDS=$(echo "$EXISTING_ROUTES" | jq -r ".result[] | select(.pattern == \"*${DOMAIN}/*\") | .id" 2>/dev/null)

if [ -n "$ROUTE_IDS" ]; then
    echo "  Removing existing routes..."
    while IFS= read -r route_id; do
        cf_api "zones/${ZONE_ID}/workers/routes/${route_id}" "DELETE" > /dev/null
    done <<< "$ROUTE_IDS"
fi

# Create new route
ROUTE=$(cf_api "zones/${ZONE_ID}/workers/routes" "POST" \
    "{\"pattern\":\"*${DOMAIN}/*\",\"script\":\"${WORKER_NAME}\"}")

if echo "$ROUTE" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ Worker route configured${NC}"
else
    echo -e "${RED}❌ Failed to configure worker route${NC}"
    echo "$ROUTE" | jq . 2>/dev/null
fi

echo -e "\n${BLUE}Step 7: Configuring SSL settings...${NC}"

# Set SSL mode to Flexible
SSL=$(cf_api "zones/${ZONE_ID}/settings/ssl" "PATCH" '{"value":"flexible"}')
if echo "$SSL" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ SSL mode set to Flexible${NC}"
fi

# Enable Always Use HTTPS
HTTPS=$(cf_api "zones/${ZONE_ID}/settings/always_use_https" "PATCH" '{"value":"on"}')
if echo "$HTTPS" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ Always Use HTTPS enabled${NC}"
fi

# Get nameservers
echo -e "\n${BLUE}Step 8: Checking nameservers...${NC}"
NS_INFO=$(cf_api "zones/${ZONE_ID}")
NS1=$(echo "$NS_INFO" | jq -r '.result.name_servers[0]' 2>/dev/null)
NS2=$(echo "$NS_INFO" | jq -r '.result.name_servers[1]' 2>/dev/null)

echo -e "\n${GREEN}🎉 Setup Complete!${NC}"
echo -e "\n${YELLOW}Important Next Steps:${NC}"
echo -e "\n1. Update nameservers at your domain registrar (GoDaddy):"
echo -e "   ${BLUE}Nameserver 1:${NC} $NS1"
echo -e "   ${BLUE}Nameserver 2:${NC} $NS2"
echo -e "\n2. Wait for DNS propagation (usually 5-60 minutes)"
echo -e "\n3. Test your site:"
echo -e "   ${BLUE}https://${DOMAIN}${NC}"
echo -e "\n${BLUE}Check DNS propagation status:${NC}"
echo -e "https://dnschecker.org/#NS/${DOMAIN}"
echo -e "\n${GREEN}Your Kubernetes app will be accessible at https://${DOMAIN} once DNS propagates!${NC}"