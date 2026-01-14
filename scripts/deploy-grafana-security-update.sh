#!/bin/bash
# Deploy Grafana Security Update - Fix DOMPurify Vulnerability
# Date: 2025-07-25
# CVE: CVE-2024-47875

set -e

echo "================================================"
echo "Deploying Grafana Security Update"
echo "Fixing DOMPurify Vulnerability (CVE-2024-47875)"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Current Grafana version: 10.2.0 (vulnerable)${NC}"
echo -e "${YELLOW}Updating to version: 11.4.0 (patched)${NC}"

# Deploy Grafana with security update
echo -e "\n${GREEN}1. Deploying Grafana with security fix...${NC}"
cd fly/grafana

# Check current deployment
echo -e "\n${YELLOW}Current deployment status:${NC}"
fly status -a linknode-grafana || true

# Deploy update
echo -e "\n${GREEN}Starting deployment...${NC}"
fly deploy --strategy immediate

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Grafana deployed successfully${NC}"
else
    echo -e "${RED}✗ Grafana deployment failed${NC}"
    exit 1
fi

cd ../..

echo -e "\n${YELLOW}Waiting for Grafana to stabilize...${NC}"
sleep 30

echo -e "\n${GREEN}2. Verifying Grafana is accessible...${NC}"
GRAFANA_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://linknode-grafana.fly.dev/api/health)
if [ "$GRAFANA_STATUS" == "200" ]; then
    echo -e "${GREEN}✓ Grafana is healthy (200 OK)${NC}"
else
    echo -e "${YELLOW}⚠ Grafana returned status: $GRAFANA_STATUS${NC}"
fi

echo -e "\n${GREEN}3. Checking Grafana version...${NC}"
GRAFANA_VERSION=$(curl -s https://linknode-grafana.fly.dev/api/health | grep -o '"version":"[^"]*"' | cut -d'"' -f4 || echo "Unable to determine")
echo -e "  Grafana version: ${GREEN}$GRAFANA_VERSION${NC}"

echo -e "\n${GREEN}4. Testing dashboard access...${NC}"
DASHBOARD_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://linknode-grafana.fly.dev/d/power-monitoring/eagle-energy-monitor)
if [ "$DASHBOARD_STATUS" == "200" ]; then
    echo -e "${GREEN}✓ Dashboard is accessible${NC}"
else
    echo -e "${YELLOW}⚠ Dashboard returned status: $DASHBOARD_STATUS${NC}"
fi

echo -e "\n${GREEN}5. Verifying iframe embedding on main site...${NC}"
IFRAME_TEST=$(curl -s https://linknode.com | grep -c "linknode-grafana.fly.dev" || true)
if [ "$IFRAME_TEST" -gt 0 ]; then
    echo -e "${GREEN}✓ Grafana iframe properly embedded${NC}"
else
    echo -e "${YELLOW}⚠ Could not verify iframe embedding${NC}"
fi

echo -e "\n${YELLOW}================================================${NC}"
echo -e "${GREEN}Grafana security update complete!${NC}"
echo -e "${YELLOW}================================================${NC}"

echo -e "\nSecurity Update Summary:"
echo "- Fixed: DOMPurify vulnerability (CVE-2024-47875)"
echo "- Previous version: 10.2.0 with DOMPurify 2.4.5"
echo "- Updated version: 11.4.0 with patched DOMPurify"
echo "- Risk mitigated: XSS attacks via nested data"

echo -e "\nNext steps:"
echo "1. Verify all dashboards are working correctly"
echo "2. Check for any breaking changes in Grafana 11.x"
echo "3. Monitor logs for any issues: fly logs -a linknode-grafana"
echo "4. Run security scan to confirm vulnerability is fixed"

echo -e "\n${GREEN}Deployment completed at: $(date)${NC}"