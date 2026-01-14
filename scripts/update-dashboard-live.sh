#!/bin/bash

# Script to update Grafana dashboard live without restart

echo "Updating Grafana dashboard live..."

# First, get Grafana admin password
GRAFANA_PASSWORD=$(kubectl get secret -n demo-app grafana-admin -o jsonpath='{.data.password}' 2>/dev/null | base64 -d || echo "admin")

# Extract dashboard JSON from ConfigMap
kubectl get configmap grafana-dashboard-power -n demo-app -o json | \
  jq -r '.data["power-monitoring.json"]' > /tmp/dashboard.json

# Update dashboard via Grafana API
kubectl exec -n demo-app deployment/grafana -- sh -c "
  curl -X POST \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json' \
    -u admin:${GRAFANA_PASSWORD} \
    -d '{\"dashboard\": $(cat), \"overwrite\": true, \"folderId\": 0}' \
    http://localhost:3000/api/dashboards/db
" < /tmp/dashboard.json

echo ""
echo "✅ Dashboard updated! Just refresh your browser - no need to log out."
echo "   URL: http://119.9.118.22:30300/d/power-monitoring/"

# Clean up
rm -f /tmp/dashboard.json