#!/bin/bash

# Script to apply the selective storage fix for intermittent 0.000 W display issue

echo "Applying selective storage fix for EAGLE power monitoring..."

# Apply the new ConfigMap with selective storage logic
echo "1. Applying new Flask ConfigMap..."
kubectl apply -f k8s/configmap-flask-app-selective.yaml

# Update the Grafana dashboard
echo "2. Updating Grafana dashboard..."
kubectl apply -f k8s/grafana-dashboard-selective.yaml

# Restart the Flask deployment to pick up new code
echo "3. Restarting Flask deployment..."
kubectl rollout restart deployment/flask-app -n demo-app

# Wait for rollout to complete
echo "4. Waiting for rollout to complete..."
kubectl rollout status deployment/flask-app -n demo-app

# Check pod status
echo "5. Checking pod status..."
kubectl get pods -n demo-app | grep flask-app

echo ""
echo "Fix applied successfully!"
echo ""
echo "The system now stores InstantaneousDemand and CurrentSummation data in separate InfluxDB measurements:"
echo "- power_demand: Stores current power demand (kW)"
echo "- power_summation: Stores total energy delivered/received (kWh)"
echo ""
echo "This prevents CurrentSummation messages from overwriting power demand with 0."
echo ""
echo "Please check your Grafana dashboard at http://119.9.118.22:30300"
echo "You should no longer see intermittent 0.000 W readings."