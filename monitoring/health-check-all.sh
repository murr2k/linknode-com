#!/bin/bash
# health-check-all.sh - Monitor all Linknode services
# Usage: ./health-check-all.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Exit code tracking
EXIT_CODE=0

check_service() {
  local name=$1
  local url=$2
  local check_cmd=$3
  
  printf "%-20s" "Checking $name..."
  
  if eval "$check_cmd" 2>/dev/null; then
    echo -e "${GREEN}✅ Healthy${NC}"
    return 0
  else
    echo -e "${RED}❌ Unhealthy${NC}"
    EXIT_CODE=1
    return 1
  fi
}

echo "==================================="
echo "Linknode Services Health Check"
echo "==================================="
echo ""

# Run health checks
check_service "InfluxDB" \
  "http://linknode-influxdb.fly.dev:8086/ping" \
  "curl -sf http://linknode-influxdb.fly.dev:8086/ping -m 10"

check_service "Eagle Monitor" \
  "https://linknode-eagle-monitor.fly.dev/health" \
  "curl -sf https://linknode-eagle-monitor.fly.dev/health -m 10"

check_service "Grafana" \
  "https://linknode-grafana.fly.dev/api/health" \
  "curl -sf https://linknode-grafana.fly.dev/api/health -m 10"

check_service "Web Interface" \
  "https://linknode-web.fly.dev/" \
  "curl -sf https://linknode-web.fly.dev/ -m 10 | grep -q Linknode"

echo ""
echo "==================================="

if [ $EXIT_CODE -eq 0 ]; then
  echo -e "${GREEN}All services are healthy!${NC}"
else
  echo -e "${RED}Some services are unhealthy!${NC}"
  echo -e "${YELLOW}Check the logs above for details.${NC}"
fi

exit $EXIT_CODE