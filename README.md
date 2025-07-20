# Rackspace Kubernetes Demo

A modern, interactive Kubernetes demo application showcasing cloud-native deployment on Rackspace's managed Kubernetes platform.

![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white)
![Nginx](https://img.shields.io/badge/nginx-%23009639.svg?style=for-the-badge&logo=nginx&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

## 🚀 Live Demo

**Public URLs**:
- **Custom Domain**: https://linknode.com
- **Direct Access**: http://119.9.118.22:30898
- **Cloudflare Tunnel**: https://daniel-holidays-diesel-gross.trycloudflare.com

**Monitoring Stack**:
- **Grafana Dashboard**: http://119.9.118.22:30300
- **Eagle XML Endpoint**: http://119.9.118.22:30500 (accepts XML data)

### What's Special About This Demo?

This entire Kubernetes platform was **built in under 24 hours** using AI-augmented development, showcasing:
- Enterprise-grade infrastructure deployed at record speed
- Production-ready patterns and best practices
- Live auto-scaling and self-healing capabilities
- Professional marketing content integrated seamlessly

Visit the live demo to see both the technical capabilities and learn about AI-augmented development services.

## 📋 Features

- **Modern Interactive Web Interface**: 
  - Animated gradients and floating particles
  - Live power consumption widget with real-time updates
  - Embedded Grafana dashboard (no login required!)
  - API status indicators for monitoring services
  - Real-time pod/connection counter
- **Kubernetes Native**: Demonstrates key K8s concepts including:
  - Deployments and ReplicaSets
  - Services (ClusterIP, NodePort, LoadBalancer)
  - ConfigMaps for configuration management
  - Horizontal Pod Autoscaling (HPA)
  - Health checks and probes
  - Resource limits and requests
- **Real-time Power Monitoring**:
  - Eagle-200 smart meter integration (XML format)
  - Live power consumption dashboard (Grafana)
  - Public dashboard access (no authentication needed)
  - Time-series data storage (InfluxDB)
  - XML data ingestion endpoint
  - Automatic dashboard updates via CI/CD
  - Fallback to simulated data when APIs unavailable
- **Secure Access Options**: 
  - SSH tunnel access for development
  - NodePort for cost-effective public access
  - LoadBalancer support (optional)
  - Public dashboards with read-only access
- **WSL2 Compatible**: Optimized for Windows Subsystem for Linux

## 🛠️ Prerequisites

- Kubernetes cluster (tested on v1.31.1)
- kubectl CLI tool
- Valid kubeconfig file
- Docker (for building custom images)

## 📦 Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/murr2k/rackspace-k8s-demo.git
   cd rackspace-k8s-demo
   ```

2. **Deploy to Kubernetes**
   ```bash
   # Create namespace
   kubectl apply -f k8s/namespace.yaml
   
   # Deploy all resources
   kubectl apply -f k8s/
   ```

3. **Access the application**
   
   For NodePort (public access):
   ```bash
   kubectl get svc -n demo-app
   # Access at http://<NODE-IP>:<NODE-PORT>
   ```
   
   For local access:
   ```bash
   ./wsl-access.sh
   # Access at http://localhost:8090
   ```

## 📁 Project Structure

```
rackspace-k8s-demo/
├── app/                      # Application source code
│   ├── app.py               # Flask application
│   ├── power_monitor.py     # Power monitoring endpoints
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile           # Container definition
├── k8s/                      # Kubernetes manifests
│   ├── namespace.yaml       # Namespace definition
│   ├── configmap.yaml       # App configuration
│   ├── configmap-nginx-fixed.yaml # Enhanced interactive webpage
│   ├── configmap-monitoring-xml.yaml # Eagle XML monitoring code
│   ├── configmap-grafana-*.yaml # Grafana configurations
│   ├── deployment.yaml      # Main deployment
│   ├── deployment-nginx.yaml# Nginx deployment
│   ├── deployment-monitoring-xml.yaml # Eagle monitoring stack
│   ├── service.yaml         # Service definition
│   ├── hpa.yaml            # Horizontal Pod Autoscaler
│   ├── influxdb.yaml       # Time-series database
│   ├── grafana-anonymous-complete.yaml # Public Grafana setup
│   └── grafana-dashboard-*.yaml # Dashboard configs
├── monitoring/              # Monitoring utilities
│   ├── diagnose-no-data.sh # Troubleshooting script
│   └── *.md                # Documentation
├── .github/workflows/       # CI/CD pipelines
│   ├── deploy.yml          # Main deployment
│   └── deploy-monitoring.yml # Monitoring deployment
├── wsl-access.sh           # WSL2 port-forward script
├── ssh-tunnel-setup.sh     # SSH tunnel setup
└── README.md              # This file
```

## 🔧 Configuration

### Service Types

The demo supports three service types:

1. **ClusterIP** (default) - Internal access only
2. **NodePort** - Public access on high port (30000-32767)
3. **LoadBalancer** - Public access with dedicated IP

To change service type:
```bash
kubectl patch svc demo-app-service -n demo-app -p '{"spec":{"type":"NodePort"}}'
```

### Scaling

Manual scaling:
```bash
kubectl scale deployment demo-app -n demo-app --replicas=5
```

Auto-scaling is configured via HPA:
- Min replicas: 2
- Max replicas: 10
- Target CPU: 70%
- Target Memory: 80%

## 🔒 Security

- No default public exposure (ClusterIP)
- SSH-only access option available
- Resource limits enforced
- Non-root container user
- Health checks configured

## 💰 Cost Optimization

- **NodePort**: $0/month (uses existing infrastructure)
- **ClusterIP + Port Forward**: $0/month (most secure)
- **LoadBalancer**: ~$10-25/month (not recommended for demos)

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Murray Kopit**
- GitHub: [@murr2k](https://github.com/murr2k)
- Email: murr2k@gmail.com

## 🙏 Acknowledgments

- Rackspace for the Kubernetes platform
- The Kubernetes community
- All contributors and testers

## 📊 Power Monitoring Dashboard

This demo includes a real-time power monitoring system integrated with EAGLE smart meters:

### Features
- **Real-time Data**: Updates every 5 seconds
- **Grafana Dashboard**: Beautiful visualizations at http://119.9.118.22:30300
- **XML API**: Accepts XML data from Eagle-200 devices
- **Time-series Storage**: InfluxDB for historical data
- **Auto-deployment**: Dashboard updates via CI/CD pipeline

### Eagle-200 Configuration
Configure your Eagle-200 device to send data to:
- Cloud Provider: Other
- Protocol: XML/RAW
- Hostname: 119.9.118.22
- Port: 30500
- URL: /
- Format: XML_RAW

### Dashboard Metrics
- Current power gauge (0-10kW range)
- 24-hour total usage and cost
- Power consumption time series
- Min/Max/Average statistics  
- Weekly usage heatmap
- Hourly consumption breakdown
- Estimated monthly cost

### Interactive Web Features
The demo webpage includes several live widgets:

1. **Live Power Widget**:
   - Real-time power consumption display
   - Updates every 5 seconds from Eagle-200
   - Shows current watts, 24h usage, and estimated cost
   - Falls back to simulated data if API unavailable

2. **Embedded Grafana Dashboard**:
   - Public dashboard - no login required!
   - Shows power consumption graph
   - Fully interactive with time range selection
   - Direct link: http://119.9.118.22:30300/d/eagle-energy/eagle-energy-monitor?orgId=1

3. **API Status Indicators**:
   - InfluxDB API health
   - Grafana service status  
   - Eagle XML endpoint availability
   - Visual indicators (green = online, red = offline)

4. **Real-time Metrics**:
   - Active pod count
   - Total connections
   - Auto-refreshing statistics

5. **Enterprise Showcase Section**:
   - Learn about AI-augmented development
   - See how this platform was built in <24 hours
   - Interactive animations and modern UI design

## 🚀 CI/CD Pipeline

The project includes GitHub Actions workflows for automated deployment:

1. **Main Deployment** (`deploy.yml`):
   - Deploys application and monitoring stack
   - Updates Grafana dashboards live (no restart)
   - Triggered on push to `main` branch

2. **Monitoring Deployment** (`deploy-monitoring.yml`):
   - Dedicated workflow for monitoring updates
   - Live dashboard updates without service interruption

### Automated Updates
- Push changes to `k8s/grafana-dashboard-*.yaml`
- Pipeline automatically deploys within minutes
- Dashboards update live - just refresh your browser!

---

🌟 If you find this demo helpful, please consider giving it a star on GitHub!
