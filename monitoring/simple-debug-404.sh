#!/bin/bash

echo "🔍 Simple EAGLE 404 Debug"
echo "========================"
echo ""

# Test 1: Direct HTTP access
echo "1️⃣ Testing Direct HTTP Access to Monitoring Service..."
echo "URL: http://119.9.118.22:30500/api/power-data/test"
echo "Response:"
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" http://119.9.118.22:30500/api/power-data/test)
echo "$response" | head -n -1
http_code=$(echo "$response" | tail -n 1 | cut -d: -f2)
echo "Status Code: $http_code"
echo ""

# Test 2: Cloudflare HTTPS
echo "2️⃣ Testing Cloudflare HTTPS Route..."
echo "URL: https://linknode.com/api/power-data/test"
echo "Response:"
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -L https://linknode.com/api/power-data/test)
echo "$response" | head -n -1
http_code=$(echo "$response" | tail -n 1 | cut -d: -f2)
echo "Status Code: $http_code"
echo ""

# Test 3: Check if Cloudflare is routing to tunnel
echo "3️⃣ Checking Cloudflare Redirect Behavior..."
echo "Following redirects for: https://linknode.com/api/power-data/test"
curl -s -I -L https://linknode.com/api/power-data/test | grep -E "(HTTP|Location)" | head -5
echo ""

# Test 4: Check root page
echo "4️⃣ Checking if Cloudflare Worker is Active..."
echo "URL: https://linknode.com/"
has_power_api=$(curl -s https://linknode.com/ | grep -c "Power Monitoring API")
if [ "$has_power_api" -gt 0 ]; then
    echo "✅ Updated worker detected (found 'Power Monitoring API' text)"
else
    echo "❌ Old worker detected (no 'Power Monitoring API' text found)"
    echo "   You need to update your Cloudflare Worker!"
fi
echo ""

# Test 5: Direct POST test
echo "5️⃣ Testing POST Request Directly..."
echo "Sending EAGLE-format data to: http://119.9.118.22:30500/api/power-data"
post_response=$(curl -s -X POST http://119.9.118.22:30500/api/power-data \
  -H "Content-Type: application/json" \
  -d '{"DeviceMacId":"test","Demand":1000,"Multiplier":1,"Divisor":1000}' \
  -w "\nHTTP_CODE:%{http_code}")
echo "$post_response" | head -n -1
post_code=$(echo "$post_response" | tail -n 1 | cut -d: -f2)
echo "Status Code: $post_code"
echo ""

# Diagnosis
echo "📊 Diagnosis:"
echo "------------"
if [ "$http_code" = "000" ]; then
    echo "❌ Direct access failed - monitoring service may not be deployed"
    echo "   Solution: Deploy the monitoring stack first"
elif [ "$http_code" = "404" ]; then
    echo "❌ Direct access returns 404 - API endpoint not found"
    echo "   Solution: Check if Flask app is running with monitoring endpoints"
elif [ "$http_code" = "200" ]; then
    echo "✅ Direct access works!"
    if [ "$has_power_api" -eq 0 ]; then
        echo "❌ But Cloudflare Worker needs updating"
        echo "   Solution: Update worker.js in Cloudflare dashboard"
    else
        echo "✅ Cloudflare Worker appears to be updated"
        echo "   The issue might be with EAGLE's specific request format"
    fi
fi
echo ""

# Alternative configurations
echo "🔧 Alternative EAGLE Configurations to Try:"
echo "------------------------------------------"
echo "1. Direct HTTP (if HTTPS fails):"
echo "   Protocol: HTTP"
echo "   Hostname: 119.9.118.22"
echo "   Port: 30500"
echo "   URL: /api/power-data"
echo ""
echo "2. Via Cloudflare Tunnel:"
echo "   Protocol: HTTPS"
echo "   Hostname: daniel-holidays-diesel-gross.trycloudflare.com"
echo "   Port: 443"
echo "   URL: /api/power-data"
echo ""
echo "3. Check EAGLE logs for the exact error"
echo "   - Look for the full URL it's trying to access"
echo "   - Check if it's adding extra path components"