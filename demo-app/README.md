# Rackspace K8s Demo - Energy Monitoring Application

A comprehensive energy monitoring solution deployed on Rackspace Kubernetes infrastructure, featuring real-time power monitoring, data visualization, and automated CI/CD deployment.

## Features

### Power Monitoring
- **Real-time Eagle-200 XML Support**: Receives and processes XML data from Rainforest Automation Eagle-200 energy monitors
- **Instantaneous Power Readings**: Captures real-time power consumption in watts
- **Energy Usage Tracking**: Calculates total energy consumption (kWh) over various time periods
- **Cost Estimation**: Provides energy cost calculations based on configurable rates

### Data Visualization (Grafana Dashboard)
- **Public Access Dashboard**: No login required! Embedded directly in webpage
- **Current Power Gauge**: Real-time power display with 0-10kW range
- **24-Hour Statistics**: Total usage, cost, average, minimum, and maximum values
- **Time Series Graphs**: Power consumption trends over customizable periods
- **Weekly Heatmap**: Visual representation of usage patterns
- **Hourly Usage Bars**: Detailed 24-hour consumption breakdown
- **Monthly Cost Estimation**: Projected monthly expenses based on current usage

### Interactive Web Interface
- **Live Power Widget**: Real-time power display with 5-second updates
- **Embedded Grafana**: Public dashboard integrated into main webpage
- **API Status Indicators**: Visual health checks for all services
- **Real-time Metrics**: Pod count and connection statistics
- **Fallback Support**: Simulated data when APIs are unavailable

### Infrastructure
- **Kubernetes Deployment**: Fully containerized microservices architecture
- **InfluxDB Time Series Database**: Efficient storage of power metrics
- **Grafana Dashboards**: Professional-grade data visualization
- **Automated CI/CD**: GitHub Actions pipeline for continuous deployment

## Development Environment Setup

### Prerequisites
- Kubernetes cluster (Rackspace managed or equivalent)
- kubectl configured with cluster access
- GitHub account with repository access
- Domain with Cloudflare DNS management (optional for external access)

### Infrastructure Components

#### 1. Rackspace Kubernetes Cluster
```bash
# Cluster endpoint (example)
kubectl config set-cluster rackspace-k8s --server=https://your-cluster-endpoint

# Configure credentials
kubectl config set-credentials rackspace-user --token=your-token

# Set context
kubectl config set-context rackspace --cluster=rackspace-k8s --user=rackspace-user
kubectl config use-context rackspace
```

#### 2. External Access Configuration
- **LoadBalancer IP**: 119.9.118.22 (assigned by Rackspace)
- **Services Exposed**:
  - InfluxDB: Port 30086 (NodePort)
  - Grafana: Port 30300 (NodePort)  
  - Eagle Monitoring: Port 30500 (NodePort)

#### 3. Cloudflare DNS Setup (Optional)
For domain-based access, configure A records:
```
influxdb.yourdomain.com -> 119.9.118.22
grafana.yourdomain.com  -> 119.9.118.22
eagle.yourdomain.com    -> 119.9.118.22
```

### GitHub Repository Structure
```
linknode-com/
├── .github/
│   └── workflows/
│       └── deploy.yml              # CI/CD pipeline
├── k8s/
│   ├── namespace.yaml              # Kubernetes namespace
│   ├── influxdb.yaml               # InfluxDB deployment and service
│   ├── grafana.yaml                # Grafana deployment and service
│   ├── configmap-monitoring-xml.yaml   # Power monitoring code
│   ├── deployment-monitoring-xml.yaml  # Monitoring deployment
│   └── grafana-dashboard-*.yaml    # Various dashboard configurations
└── demo-app/
    ├── eagle-xml-configmap.yaml    # Eagle XML monitoring code
    ├── eagle-xml-deployment.yaml   # Eagle monitoring deployment
    ├── eagle-xml-service.yaml      # Eagle monitoring service
    └── power_monitor_eagle_xml.py  # Eagle XML parser implementation
```

### CI/CD Pipeline Configuration

The GitHub Actions workflow automatically deploys changes to the Kubernetes cluster:

```yaml
# .github/workflows/deploy.yml
name: Deploy to Kubernetes

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Configure kubectl
      run: |
        echo "${{ secrets.KUBE_CONFIG }}" | base64 -d > kubeconfig
        echo "KUBECONFIG=$PWD/kubeconfig" >> $GITHUB_ENV
    
    - name: Deploy to Kubernetes
      run: |
        kubectl apply -f k8s/
```

Required GitHub Secrets:
- `KUBE_CONFIG`: Base64-encoded kubeconfig file

### Setting Up the Development Environment

1. **Clone the Repository**
   ```bash
   git clone https://github.com/murr2k/linknode-com.git
   cd linknode-com
   ```

2. **Configure Kubernetes Access**
   ```bash
   # Get kubeconfig from Rackspace
   # Save to ~/.kube/config or set KUBECONFIG environment variable
   kubectl get nodes  # Verify access
   ```

3. **Deploy Infrastructure**
   ```bash
   # Create namespace
   kubectl apply -f k8s/namespace.yaml
   
   # Deploy all components
   kubectl apply -f k8s/
   ```

4. **Access Services**
   - Main Demo Page: http://119.9.118.22:30898
   - InfluxDB: http://119.9.118.22:30086
   - Grafana: http://119.9.118.22:30300 (admin/admin)
   - Public Dashboard: http://119.9.118.22:30300/public-dashboards/51a5565681464739ba4b2569e0949ffe
   - Eagle Endpoint: http://119.9.118.22:30500

5. **Configure Eagle-200 Device**
   - Set Cloud Provider: Other
   - Protocol: XML/RAW
   - Hostname: 119.9.118.22
   - Port: 30500
   - URL: /
   - Format: XML_RAW

### Local Development

1. **Python Environment** (for Eagle monitoring development)
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install flask influxdb-client
   ```

2. **Test Eagle XML Parser**
   ```bash
   cd demo-app
   python power_monitor_eagle_xml.py
   ```

3. **Update ConfigMap and Deploy**
   ```bash
   # Edit the monitoring code
   vim demo-app/eagle-xml-configmap.yaml
   
   # Deploy changes
   kubectl apply -f demo-app/eagle-xml-configmap.yaml
   kubectl rollout restart deployment/eagle-monitoring -n monitoring
   ```

### Monitoring and Debugging

1. **Check Pod Status**
   ```bash
   kubectl get pods -n demo-app
   kubectl logs -f deployment/eagle-xml-monitor -n demo-app
   ```

2. **Verify Data Flow**
   ```bash
   # Check InfluxDB for data
   kubectl exec -it deployment/influxdb -n demo-app -- influx query \
     'from(bucket: "power_metrics") |> range(start: -1h) |> last()' \
     --org rackspace --token my-super-secret-auth-token
   ```

3. **Access Grafana Dashboard**
   - Navigate to http://119.9.118.22:30300
   - Login with admin/admin
   - Go to Dashboards → Eagle Energy Monitor

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test locally with kubectl
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

The CI/CD pipeline will automatically deploy merged changes to the production cluster.

## Architecture Overview

```
┌─────────────────┐     XML Data      ┌──────────────────────┐
│   Eagle-200     │ ─────────────────▶ │  Eagle Monitoring    │
│ Energy Monitor  │                    │    (Flask App)       │
└─────────────────┘                    └──────────┬───────────┘
                                                  │
                                                  │ Metrics
                                                  ▼
                                       ┌──────────────────────┐
                                       │     InfluxDB         │
                                       │  (Time Series DB)    │
                                       └──────────┬───────────┘
                                                  │
                                                  │ Queries
                                                  ▼
                                       ┌──────────────────────┐
                                       │      Grafana         │
                                       │   (Visualization)    │
                                       └──────────────────────┘
```

## Troubleshooting

### No Data in Grafana
1. Verify Eagle is sending data: `kubectl logs -f deployment/eagle-monitoring -n monitoring`
2. Check InfluxDB has data: Use influx CLI as shown above
3. Verify Grafana datasource configuration

### Pod Crashes
1. Check logs: `kubectl logs deployment/eagle-monitoring -n monitoring --previous`
2. Verify ConfigMap is properly formatted
3. Check resource limits and requests

### Connection Issues
1. Verify NodePort services are accessible
2. Check firewall rules allow traffic on ports 30086, 30300, 30500
3. Confirm LoadBalancer IP is active

## License

This project is licensed under the MIT License - see the LICENSE file for details.