#!/bin/bash

echo "🔍 Testing All Possible EAGLE Endpoints"
echo "======================================"
echo ""

# Test data similar to EAGLE
EAGLE_DATA='{
  "DeviceMacId": "0xd8d5b9000000test",
  "MeterMacId": "0x00135003007test",
  "TimeStamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
  "Demand": 2500,
  "CurrentSummationDelivered": 12345.678,
  "CurrentSummationReceived": 0,
  "Multiplier": 1,
  "Divisor": 1000
}'

echo "1️⃣ Testing Direct HTTP Endpoint"
echo "URL: http://119.9.118.22:30500/api/power-data"
response=$(curl -s -w "\n==STATUS==%{http_code}==\n==HEADERS==%{content_type}==\n==SIZE==%{size_download}==" \
  -X POST http://119.9.118.22:30500/api/power-data \
  -H "Content-Type: application/json" \
  -d "$EAGLE_DATA")
status=$(echo "$response" | grep -oP '(?<===STATUS==)\d+')
size=$(echo "$response" | grep -oP '(?<===SIZE==)\d+')
echo "Status: $status, Response size: $size bytes"
echo ""

echo "2️⃣ Testing via Cloudflare (linknode.com)"
echo "URL: https://linknode.com/api/power-data"
response=$(curl -s -w "\n==STATUS==%{http_code}==" \
  -X POST https://linknode.com/api/power-data \
  -H "Content-Type: application/json" \
  -d "$EAGLE_DATA")
status=$(echo "$response" | grep -oP '(?<===STATUS==)\d+')
echo "Status: $status"
echo ""

echo "3️⃣ Testing via Cloudflare Tunnel"
echo "URL: https://daniel-holidays-diesel-gross.trycloudflare.com/api/power-data"
response=$(curl -s -w "\n==STATUS==%{http_code}==" \
  -X POST https://daniel-holidays-diesel-gross.trycloudflare.com/api/power-data \
  -H "Content-Type: application/json" \
  -d "$EAGLE_DATA")
status=$(echo "$response" | grep -oP '(?<===STATUS==)\d+')
echo "Status: $status"
echo ""

echo "4️⃣ Checking What EAGLE Sees"
echo "The 404 error suggests EAGLE might be:"
echo "- Missing protocol/hostname in config"
echo "- Using a different URL path"
echo "- Sending to the wrong port"
echo ""

echo "5️⃣ Testing Various URL Patterns EAGLE Might Use"
for path in "/api/power-data" "/api/eagle/upload" "/upload" "/data"; do
    echo -n "Testing $path: "
    status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://119.9.118.22:30500$path" \
      -H "Content-Type: application/json" -d "$EAGLE_DATA")
    echo "HTTP $status"
done
echo ""

echo "📋 EAGLE Configuration Checklist:"
echo "================================"
echo "✓ Protocol: HTTP (not HTTPS for direct)"
echo "✓ Hostname: 119.9.118.22"
echo "✓ URL: /api/power-data"
echo "✓ Port: 30500"
echo "✓ Format: JSON"
echo ""
echo "❌ Common mistakes:"
echo "- Leaving hostname blank"
echo "- Using HTTPS with HTTP port"
echo "- Including http:// in hostname field"
echo "- Wrong port number"