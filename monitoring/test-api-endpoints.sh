#!/bin/bash

echo "🧪 Testing Power Monitoring API Endpoints..."
echo ""

# Test direct access first
echo "1️⃣ Testing Direct Access (HTTP):"
echo "   URL: http://119.9.118.22:30500/api/power-data/test"
curl -s http://119.9.118.22:30500/api/power-data/test | jq . || echo "Failed to connect"
echo ""

# Test via Cloudflare
echo "2️⃣ Testing via Cloudflare (HTTPS):"
echo "   URL: https://linknode.com/api/power-data/test"
curl -s https://linknode.com/api/power-data/test | jq . || echo "Failed to connect"
echo ""

# Test POST request with sample data
echo "3️⃣ Testing POST with sample EAGLE data:"
echo "   Sending sample power data..."

SAMPLE_DATA='{
  "DeviceMacId": "0xd8d5b9000000test",
  "MeterMacId": "0x00135003007test",
  "TimeStamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
  "Demand": 3500,
  "CurrentSummationDelivered": 12345.678,
  "CurrentSummationReceived": 0.0,
  "Multiplier": 1,
  "Divisor": 1000
}'

echo "   Direct POST:"
curl -s -X POST http://119.9.118.22:30500/api/power-data \
  -H "Content-Type: application/json" \
  -d "$SAMPLE_DATA" | jq . || echo "Failed"
echo ""

echo "   Cloudflare POST:"
curl -s -X POST https://linknode.com/api/power-data \
  -H "Content-Type: application/json" \
  -d "$SAMPLE_DATA" | jq . || echo "Failed"
echo ""

# Check latest reading
echo "4️⃣ Checking latest reading:"
echo "   URL: https://linknode.com/api/power-data/latest"
curl -s https://linknode.com/api/power-data/latest | jq . || echo "No data yet"
echo ""

echo "✅ Test complete!"
echo ""
echo "📝 If Cloudflare tests fail with 404:"
echo "   1. Run: cd /home/murr2k/projects/rackspace/demo-app/cloudflare-setup"
echo "   2. Run: ./update-worker.sh"
echo "   3. Follow the instructions to update your Cloudflare Worker"