#!/bin/bash
# Deploy Security Fixes for Linknode
# Date: 2025-07-25

set -e

echo "================================================"
echo "Deploying Security Fixes for Linknode"
echo "================================================"

# Check if fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo "Error: fly CLI not found. Please install it first."
    exit 1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting deployment of security fixes...${NC}"

# Deploy Web Service with updated nginx config
echo -e "\n${GREEN}1. Deploying Web Service with security fixes...${NC}"
cd fly/web
fly deploy --strategy immediate
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Web service deployed successfully${NC}"
else
    echo -e "${RED}✗ Web service deployment failed${NC}"
    exit 1
fi

# Deploy Eagle Monitor with security headers
echo -e "\n${GREEN}2. Deploying Eagle Monitor with security headers...${NC}"
cd ../eagle-monitor
fly deploy --strategy immediate
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Eagle Monitor deployed successfully${NC}"
else
    echo -e "${RED}✗ Eagle Monitor deployment failed${NC}"
    exit 1
fi

cd ../..

echo -e "\n${YELLOW}Verifying security fixes...${NC}"

# Wait for services to stabilize
echo "Waiting 30 seconds for services to stabilize..."
sleep 30

# Verify security headers
echo -e "\n${GREEN}3. Checking security headers...${NC}"
HEADERS=$(curl -sI https://linknode.com | grep -E "(X-Content-Type-Options|X-Frame-Options|Strict-Transport-Security|Server)")
echo "$HEADERS"

# Test cloud metadata blocking
echo -e "\n${GREEN}4. Testing cloud metadata blocking...${NC}"
METADATA_TEST=$(curl -s -o /dev/null -w "%{http_code}" https://linknode.com/opc/v1/instance/)
if [ "$METADATA_TEST" == "403" ]; then
    echo -e "${GREEN}✓ Cloud metadata endpoint properly blocked (403 Forbidden)${NC}"
else
    echo -e "${RED}✗ Cloud metadata endpoint NOT blocked! Response: $METADATA_TEST${NC}"
fi

# Test admin endpoint protection
echo -e "\n${GREEN}5. Testing admin endpoint protection...${NC}"
ADMIN_TEST=$(curl -s -o /dev/null -w "%{http_code}" https://linknode.com/admin)
if [ "$ADMIN_TEST" == "404" ]; then
    echo -e "${GREEN}✓ Admin endpoint properly hidden (404 Not Found)${NC}"
else
    echo -e "${RED}✗ Admin endpoint NOT hidden! Response: $ADMIN_TEST${NC}"
fi

# Summary
echo -e "\n${YELLOW}================================================${NC}"
echo -e "${GREEN}Security fixes deployment complete!${NC}"
echo -e "${YELLOW}================================================${NC}"

echo -e "\nNext steps:"
echo "1. Run a full security scan to verify all vulnerabilities are fixed"
echo "2. Monitor security logs at /tmp/security_events.log"
echo "3. Check application logs for any issues: fly logs -a linknode-eagle-monitor"
echo "4. Review the SECURITY_IMPROVEMENTS.md for full details"

echo -e "\n${GREEN}Deployment completed at: $(date)${NC}"