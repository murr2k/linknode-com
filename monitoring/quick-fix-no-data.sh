#!/bin/bash

echo "=== Quick Fix for No Data Issue ==="
echo ""

# 1. First, let's check current status
echo "1. Checking current system status..."
echo "------------------------------------"
curl -s http://119.9.118.22:30500/api/power-data/test | jq . 2>/dev/null || echo "Flask endpoint not responding"
echo ""

# 2. Restart Flask deployment
echo "2. Restarting Flask deployment..."
echo "---------------------------------"
kubectl rollout restart deployment/flask-app -n demo-app
echo "Waiting for rollout..."
kubectl rollout status deployment/flask-app -n demo-app --timeout=60s
echo ""

# 3. Check new pod status
echo "3. New pod status:"
echo "------------------"
kubectl get pods -n demo-app | grep flask-app
echo ""

# 4. Test endpoint again
echo "4. Testing endpoint after restart:"
echo "----------------------------------"
sleep 5
curl -s http://119.9.118.22:30500/api/power-data/test | jq . 2>/dev/null || echo "Still not responding"
echo ""

# 5. Send a test data point
echo "5. Sending test data to verify system..."
echo "-----------------------------------------"
curl -X POST http://119.9.118.22:30500/api/power-data \
  -H "Content-Type: application/json" \
  -d '{
    "deviceGuid": "test-device",
    "body": [{
      "dataType": "InstantaneousDemand",
      "timestamp": "'$(date +%s000)'",
      "data": {
        "demand": 1.234
      }
    }]
  }' -v 2>&1 | grep "< HTTP"
echo ""

# 6. Check if test data was stored
echo "6. Checking for latest data:"
echo "----------------------------"
sleep 2
curl -s http://119.9.118.22:30500/api/power-data/latest | jq . 2>/dev/null || echo "No data found"
echo ""

echo "=== Quick Fix Complete ==="
echo ""
echo "Next steps:"
echo "1. Check EAGLE device web interface - is status still 'OK'?"
echo "2. Power cycle EAGLE device if needed"
echo "3. Re-enter the upload URL in EAGLE settings:"
echo "   - Protocol: HTTP"
echo "   - Hostname: 119.9.118.22"
echo "   - Port: 30500"
echo "   - Path: /api/power-data"
echo "4. Save settings and check status"
echo ""
echo "To monitor incoming data:"
echo "kubectl logs -n demo-app deployment/flask-app -f | grep 'Received power data'"