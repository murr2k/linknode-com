#!/bin/bash

echo "=== Power Monitoring Diagnostics ==="
echo "Checking why data stopped showing..."
echo ""

# 1. Check Flask pod status
echo "1. Flask Pod Status:"
echo "-------------------"
kubectl get pods -n demo-app | grep flask-app
echo ""

# 2. Check recent Flask logs
echo "2. Recent Flask Logs (last 50 lines):"
echo "-------------------------------------"
kubectl logs -n demo-app deployment/flask-app --tail=50 | grep -E "(power|EAGLE|error|Error|Failed)"
echo ""

# 3. Check if Flask is still receiving requests
echo "3. Last 10 Power Data Requests:"
echo "--------------------------------"
kubectl logs -n demo-app deployment/flask-app --tail=100 | grep "Received power data request" | tail -10
echo ""

# 4. Check InfluxDB pod status
echo "4. InfluxDB Pod Status:"
echo "-----------------------"
kubectl get pods -n demo-app | grep influxdb
echo ""

# 5. Check if InfluxDB is accessible
echo "5. Testing InfluxDB Connection:"
echo "-------------------------------"
kubectl exec -n demo-app deployment/flask-app -- curl -s -I http://influxdb:8086/ping || echo "InfluxDB connection failed"
echo ""

# 6. Check Flask service endpoints
echo "6. Flask Service Endpoints:"
echo "---------------------------"
kubectl get endpoints -n demo-app flask-app
echo ""

# 7. Test the power data endpoint
echo "7. Testing Power Data Endpoint:"
echo "-------------------------------"
curl -s http://119.9.118.22:30500/api/power-data/test | jq . || echo "Endpoint test failed"
echo ""

# 8. Get latest power reading
echo "8. Latest Power Reading:"
echo "------------------------"
curl -s http://119.9.118.22:30500/api/power-data/latest | jq . || echo "Failed to get latest reading"
echo ""

# 9. Check memory/resource usage
echo "9. Pod Resource Usage:"
echo "---------------------"
kubectl top pods -n demo-app | grep -E "(flask-app|influxdb)" || echo "Metrics not available"
echo ""

# 10. Check for pod restarts
echo "10. Pod Restart Count:"
echo "----------------------"
kubectl get pods -n demo-app -o wide | grep -E "(flask-app|influxdb)"
echo ""

echo "=== Diagnosis Complete ==="
echo ""
echo "Common issues to check:"
echo "- EAGLE device may have stopped sending data (check EAGLE status)"
echo "- Flask pod may have crashed and restarted"
echo "- InfluxDB may be full or having issues"
echo "- Network connectivity issues"
echo ""
echo "To see full Flask logs: kubectl logs -n demo-app deployment/flask-app"
echo "To see full InfluxDB logs: kubectl logs -n demo-app deployment/influxdb"