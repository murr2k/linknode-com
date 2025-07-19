#!/bin/bash

echo "=== Refreshing Grafana Dashboard (No Restart) ==="
echo ""

# Method: Update ConfigMap and trigger reload
echo "1. Applying dashboard ConfigMap..."
kubectl apply -f k8s/grafana-dashboard-stable.yaml

echo ""
echo "2. Triggering dashboard reload..."
# Delete and recreate the provisioning config to force reload
kubectl delete configmap grafana-dashboard-provisioning -n demo-app 2>/dev/null || true
kubectl create configmap grafana-dashboard-provisioning -n demo-app \
  --from-literal=dashboards.yaml='apiVersion: 1
providers:
  - name: "default"
    folder: ""
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards'

echo ""
echo "3. Forcing provisioning reload..."
kubectl exec -n demo-app deployment/grafana -- sh -c "touch /var/lib/grafana/dashboards/power-monitoring.json"

echo ""
echo "✅ Dashboard will refresh within 10 seconds!"
echo "   Just wait a moment and refresh your browser."
echo "   No need to log out or restart anything."
echo ""
echo "If it doesn't update, you can manually reload by:"
echo "1. Going to: http://119.9.118.22:30300/dashboards"
echo "2. Click on 'Power Line Monitoring'"
echo "3. The dashboard will be updated"