#!/bin/bash

echo "=== Applying Clean Dashboard ==="
echo ""

# Apply the clean dashboard
echo "1. Applying clean dashboard configuration..."
kubectl apply -f k8s/grafana-dashboard-clean.yaml

# Restart Grafana to pick up changes
echo ""
echo "2. Restarting Grafana to apply changes..."
kubectl rollout restart deployment/grafana -n demo-app

# Wait for rollout
echo ""
echo "3. Waiting for Grafana to restart..."
kubectl rollout status deployment/grafana -n demo-app --timeout=60s

echo ""
echo "=== Dashboard Updated ==="
echo ""
echo "Changes made:"
echo "✓ Filtered out test devices (test, unknown, test-device)"
echo "✓ Simplified stat panels to show single values"
echo "✓ Separated Min/Max/Average into individual panels"
echo "✓ Added cost rate calculation panel"
echo "✓ Fixed 'Today's Consumption' to show daily usage"
echo "✓ Cleaned up all queries to use group() for single values"
echo ""
echo "Access your clean dashboard at: http://119.9.118.22:30300"
echo "Login with your Grafana credentials"