#!/bin/bash

echo "🚀 Deploying Power Line Monitoring Stack..."

# Set namespace
NAMESPACE="demo-app"

# Ensure namespace exists
echo "📦 Ensuring namespace exists..."
kubectl create namespace $NAMESPACE 2>/dev/null || echo "Namespace already exists"

# Deploy InfluxDB
echo "📊 Deploying InfluxDB..."
kubectl apply -f ../k8s/influxdb.yaml

# Wait for InfluxDB to be ready
echo "⏳ Waiting for InfluxDB to be ready..."
kubectl wait --for=condition=ready pod -l app=influxdb -n $NAMESPACE --timeout=120s

# Deploy Flask app with monitoring endpoints
echo "🐍 Deploying Flask monitoring app..."
kubectl apply -f ../k8s/configmap-flask-app.yaml
kubectl apply -f ../k8s/deployment-flask-monitoring.yaml

# Deploy Grafana
echo "📈 Deploying Grafana..."
kubectl apply -f ../k8s/grafana.yaml

# Wait for all pods to be ready
echo "⏳ Waiting for all pods to be ready..."
kubectl wait --for=condition=ready pod -l app=demo-app-monitoring -n $NAMESPACE --timeout=120s
kubectl wait --for=condition=ready pod -l app=grafana -n $NAMESPACE --timeout=120s

# Get service information
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📍 Access Points:"
echo "-------------------"

# Get cluster IP
CLUSTER_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}')

echo "🔌 Power Data API Endpoints:"
echo "  - Direct: http://$CLUSTER_IP:30500/api/power-data"
echo "  - Via Domain: https://linknode.com/api/power-data"
echo ""
echo "📊 Grafana Dashboard:"
echo "  - Direct: http://$CLUSTER_IP:30300"
echo "  - Login: admin / admin"
echo ""
echo "🧪 Test Endpoints:"
echo "  - API Test: http://$CLUSTER_IP:30500/api/power-data/test"
echo "  - Latest Reading: http://$CLUSTER_IP:30500/api/power-data/latest"
echo ""
echo "⚡ EAGLE Device Configuration:"
echo "  - Protocol: HTTPS (or HTTP for testing)"
echo "  - Hostname: linknode.com (or $CLUSTER_IP)"
echo "  - URL: /api/power-data"
echo "  - Port: 443 (or 30500 for direct)"
echo "  - Format: JSON"
echo ""
echo "📝 To view logs:"
echo "  - Flask app: kubectl logs -f -l app=demo-app-monitoring -n $NAMESPACE"
echo "  - InfluxDB: kubectl logs -f -l app=influxdb -n $NAMESPACE"
echo "  - Grafana: kubectl logs -f -l app=grafana -n $NAMESPACE"