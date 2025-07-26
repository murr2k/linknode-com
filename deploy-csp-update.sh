#!/bin/bash
# Deploy CSP Update for Linknode
# Date: 2025-07-25

set -e

echo "================================================"
echo "Deploying Enhanced CSP Configuration"
echo "================================================"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting CSP update deployment...${NC}"

# Deploy Web Service with enhanced CSP
echo -e "\n${GREEN}Deploying Web Service with enhanced CSP...${NC}"
cd fly/web
fly deploy --strategy immediate

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Web service deployed successfully${NC}"
else
    echo -e "${RED}✗ Web service deployment failed${NC}"
    exit 1
fi

cd ../..

echo -e "\n${YELLOW}Waiting for service to stabilize...${NC}"
sleep 15

echo -e "\n${GREEN}Verifying CSP implementation...${NC}"

# Check CSP headers
echo -e "\n${GREEN}1. Checking Content-Security-Policy header:${NC}"
CSP=$(curl -sI https://linknode.com | grep -i "^content-security-policy:" | head -1)
if [ -n "$CSP" ]; then
    echo -e "${GREEN}✓ CSP header found:${NC}"
    echo "  $CSP" | fold -w 100 -s | sed 's/^/  /'
else
    echo -e "${RED}✗ CSP header not found!${NC}"
fi

# Check CSP Report-Only header
echo -e "\n${GREEN}2. Checking Content-Security-Policy-Report-Only header:${NC}"
CSP_RO=$(curl -sI https://linknode.com | grep -i "^content-security-policy-report-only:")
if [ -n "$CSP_RO" ]; then
    echo -e "${GREEN}✓ CSP Report-Only header found (for testing stricter policy):${NC}"
    echo "  $CSP_RO" | fold -w 100 -s | sed 's/^/  /'
else
    echo "  No Report-Only header (this is optional)"
fi

# Test CSP report endpoint
echo -e "\n${GREEN}3. Testing CSP report endpoint:${NC}"
REPORT_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST https://linknode.com/csp-report)
if [ "$REPORT_CODE" == "204" ]; then
    echo -e "${GREEN}✓ CSP report endpoint properly configured (204 No Content)${NC}"
else
    echo -e "  CSP report endpoint returned: $REPORT_CODE"
fi

# Test that site still works
echo -e "\n${GREEN}4. Testing site functionality:${NC}"
SITE_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://linknode.com)
if [ "$SITE_CODE" == "200" ]; then
    echo -e "${GREEN}✓ Site is accessible (200 OK)${NC}"
else
    echo -e "${RED}✗ Site returned unexpected code: $SITE_CODE${NC}"
fi

echo -e "\n${YELLOW}================================================${NC}"
echo -e "${GREEN}CSP deployment complete!${NC}"
echo -e "${YELLOW}================================================${NC}"

echo -e "\nCSP Configuration Summary:"
echo "- Enhanced CSP with specific directives for each resource type"
echo "- Report-Only header for testing stricter policies"
echo "- CSP violation reporting endpoint at /csp-report"
echo "- Temporary 'unsafe-inline' for compatibility (can be removed after testing)"

echo -e "\nNext steps:"
echo "1. Monitor CSP violations in the logs"
echo "2. Test all site functionality"
echo "3. Gradually move to stricter CSP by removing 'unsafe-inline'"
echo "4. Update Report-Only policy based on violation reports"

echo -e "\n${GREEN}Deployment completed at: $(date)${NC}"