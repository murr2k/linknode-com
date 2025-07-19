#!/bin/bash

echo "🔍 EAGLE 404 Debug Script"
echo "========================="
echo ""

# Step 1: Check if services are running
echo "1️⃣ Checking Kubernetes Services..."
echo "-----------------------------------"
kubectl get svc -n demo-app | grep -E "(demo-app-monitoring|influxdb|grafana)"
echo ""

echo "2️⃣ Checking Pod Status..."
echo "-------------------------"
kubectl get pods -n demo-app | grep -E "(demo-app-monitoring|influxdb|grafana)"
echo ""

# Step 2: Test direct access
echo "3️⃣ Testing Direct Access (bypassing Cloudflare)..."
echo "------------------------------------------------"
echo "Testing: http://119.9.118.22:30500/api/power-data/test"
curl -v -s http://119.9.118.22:30500/api/power-data/test 2>&1 | grep -E "(HTTP|404|200|{)"
echo ""

# Step 3: Test Cloudflare routing
echo "4️⃣ Testing Cloudflare Route..."
echo "-----------------------------"
echo "Testing: https://linknode.com/api/power-data/test"
curl -v -s https://linknode.com/api/power-data/test 2>&1 | grep -E "(HTTP|404|200|{|Location)"
echo ""

# Step 4: Check what paths Cloudflare is seeing
echo "5️⃣ Testing Cloudflare Root..."
echo "----------------------------"
echo "Testing: https://linknode.com/"
curl -s https://linknode.com/ | grep -o "Power Monitoring API" | head -1
echo ""

# Step 5: Check Flask app logs
echo "6️⃣ Recent Flask App Logs..."
echo "---------------------------"
kubectl logs -n demo-app -l app=demo-app-monitoring --tail=20 | grep -E "(api/power-data|Error|POST|GET)"
echo ""

# Step 6: Test with exact EAGLE format
echo "7️⃣ Testing with EAGLE-format POST..."
echo "-----------------------------------"
EAGLE_DATA='{
  "DeviceMacId": "0xd8d5b9000000test",
  "MeterMacId": "0x00135003007test",
  "TimeStamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
  "Demand": 1234,
  "CurrentSummationDelivered": 12345.678,
  "CurrentSummationReceived": 0,
  "Multiplier": 1,
  "Divisor": 1000
}'

echo "Direct POST to monitoring service:"
curl -X POST http://119.9.118.22:30500/api/power-data \
  -H "Content-Type: application/json" \
  -d "$EAGLE_DATA" \
  -w "\nHTTP Status: %{http_code}\n" \
  -s
echo ""

echo "🤔 Diagnostics Summary:"
echo "---------------------"
echo "- If direct access (Step 3) returns 404: The Flask app isn't deployed correctly"
echo "- If direct access works but Cloudflare (Step 4) returns 404: Worker needs updating"
echo "- If both return 404: The monitoring service needs to be deployed"
echo ""
echo "📝 Next Steps:"
echo "1. If services aren't running: cd monitoring && ./deploy-monitoring.sh"
echo "2. If Cloudflare returns 404: Update the worker in Cloudflare dashboard"
echo "3. Share the output of this script for further debugging"