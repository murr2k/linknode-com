#!/bin/bash

echo "=== Live Grafana Dashboard Update Methods ==="
echo ""

# Method 1: Direct API update (fastest)
echo "Method 1: Update via Grafana API (no restart needed)"
echo "-----------------------------------------------------"
echo "This updates the dashboard immediately without any restart:"
echo ""

# Get the dashboard JSON from ConfigMap
DASHBOARD_JSON=$(kubectl get configmap grafana-dashboard-power -n demo-app -o jsonpath='{.data.power-monitoring\.json}')

# Update via Grafana API
echo "Updating dashboard via API..."
kubectl exec -n demo-app deployment/grafana -- curl -X POST \
  -H "Content-Type: application/json" \
  -d "{\"dashboard\": $DASHBOARD_JSON, \"overwrite\": true}" \
  http://admin:admin@localhost:3000/api/dashboards/db

echo ""
echo "✓ Dashboard updated live! Just refresh your browser."
echo ""

# Method 2: ConfigMap update only
echo "Method 2: Update ConfigMap + Reload (no pod restart)"
echo "----------------------------------------------------"
echo "kubectl apply -f k8s/grafana-dashboard-xyz.yaml"
echo ""
echo "Then force Grafana to reload:"
echo "kubectl exec -n demo-app deployment/grafana -- kill -HUP 1"
echo ""

# Method 3: Through UI
echo "Method 3: Update through Grafana UI"
echo "-----------------------------------"
echo "1. Go to your dashboard"
echo "2. Click gear icon ⚙️ → Settings"
echo "3. Go to 'JSON Model' tab"
echo "4. Paste new JSON and click 'Save changes'"
echo "5. Click 'Save dashboard'"
echo ""

echo "Current dashboard URL: http://119.9.118.22:30300/d/power-monitoring/"