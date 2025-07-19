#!/bin/bash

echo "=== Eagle XML Monitoring Service Deployment Verification ==="
echo

echo "1. Checking ConfigMap..."
kubectl get configmap eagle-xml-code -n demo-app

echo -e "\n2. Checking Deployment..."
kubectl get deployment eagle-xml-monitor -n demo-app

echo -e "\n3. Checking Service..."
kubectl get service eagle-xml-monitor -n demo-app

echo -e "\n4. Checking Pod Status..."
kubectl get pods -n demo-app -l app=eagle-xml-monitor

echo -e "\n5. Service Endpoints:"
echo "   - NodePort: 30500"
echo "   - Internal Port: 5000"
echo "   - Endpoints:"
echo "     - /health"
echo "     - /api/eagle"
echo "     - /api/eagle/"
echo "     - /eagle"
echo "     - /eagle/"
echo "     - /api/eagle/status"
echo "     - /eagle/status"

echo -e "\n6. To test the service:"
echo "   kubectl port-forward -n demo-app service/eagle-xml-monitor 5000:5000"
echo "   curl http://localhost:5000/api/eagle"

echo -e "\n=== Deployment Complete ===\n"