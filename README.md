# Rackspace Kubernetes Demo

A modern, interactive Kubernetes demo application showcasing cloud-native deployment on Rackspace's managed Kubernetes platform.

![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white)
![Nginx](https://img.shields.io/badge/nginx-%23009639.svg?style=for-the-badge&logo=nginx&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

## 🚀 Live Demo

**Public URLs**:
- **Custom Domain**: https://linknode.com
- **Direct Access**: http://119.9.118.22:32304
- **Cloudflare Tunnel**: https://supply-motherboard-relation-features.trycloudflare.com

## 📋 Features

- **Modern Web Interface**: Animated gradients, floating particles, and interactive elements
- **Kubernetes Native**: Demonstrates key K8s concepts including:
  - Deployments and ReplicaSets
  - Services (ClusterIP, NodePort, LoadBalancer)
  - ConfigMaps for configuration management
  - Horizontal Pod Autoscaling (HPA)
  - Health checks and probes
  - Resource limits and requests
- **Secure Access Options**: 
  - SSH tunnel access for development
  - NodePort for cost-effective public access
  - LoadBalancer support (optional)
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
│   ├── app.py               # Flask application (if using Python)
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile           # Container definition
├── k8s/                      # Kubernetes manifests
│   ├── namespace.yaml       # Namespace definition
│   ├── configmap.yaml       # App configuration
│   ├── configmap-nginx.yaml # Nginx HTML content
│   ├── deployment.yaml      # Main deployment
│   ├── deployment-nginx.yaml# Nginx deployment
│   ├── service.yaml         # Service definition
│   └── hpa.yaml            # Horizontal Pod Autoscaler
├── wsl-access.sh            # WSL2 port-forward script
├── ssh-tunnel-setup.sh      # SSH tunnel setup
├── start-secure-access.sh   # Quick start script
├── check-ports.sh           # Port availability checker
├── nodeport-access.md       # NodePort documentation
├── secure-access.md         # SSH access guide
└── README-WSL.md           # WSL-specific instructions
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

---

🌟 If you find this demo helpful, please consider giving it a star on GitHub!