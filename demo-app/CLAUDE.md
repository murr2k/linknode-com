# Project State - Rackspace K8s Energy Monitoring Demo

## Current Status (As of January 2025)
This project implements a complete energy monitoring solution using Eagle-200 XML data, deployed on Rackspace Kubernetes infrastructure.

## Key Achievements
1. **Eagle-200 XML Support**: Successfully implemented XML parsing for Rainforest Automation Eagle-200 devices
   - Handles InstantaneousDemand, CurrentSummation, and PriceCluster messages
   - Properly parses the `<rainforest>` wrapper element
   - Stores data in InfluxDB with proper timestamps

2. **Grafana Dashboard**: Created comprehensive energy monitoring dashboard with:
   - Real-time power gauge (0-10kW range with proper visibility)
   - 24-hour usage statistics and cost calculations
   - Time series visualizations
   - Weekly usage heatmap
   - Hourly consumption breakdown

3. **Infrastructure**: Fully deployed on Rackspace K8s cluster
   - InfluxDB on port 30086
   - Grafana on port 30300
   - Eagle monitoring endpoint on port 30500
   - LoadBalancer IP: 119.9.118.22

## Recent Fixes
- Fixed XML parsing to handle `<rainforest>` wrapper element
- Corrected Flux query syntax errors in Grafana dashboard
- Fixed gauge visibility issues (color contrast and sizing)
- Corrected energy calculations (proper time factor for kWh conversion)
- Simplified gauge thresholds to 0, 5000W, 10000W

## Known Configuration
- InfluxDB Organization: "rackspace"
- InfluxDB Bucket: "power_metrics"
- InfluxDB Token: "mytoken"
- Grafana admin credentials: admin/admin
- Dashboard UID: "eagle-energy-monitor"

## File Locations
- Main monitoring code: `/k8s/configmap-eagle-xml.yaml`
- Deployment config: `/k8s/deployment-eagle-monitoring.yaml`
- Service config: `/k8s/service-eagle-monitoring.yaml`
- Dashboard JSON: Available in multiple versions in project root
- CI/CD Pipeline: `.github/workflows/deploy.yml`

## GitHub Repository
- URL: https://github.com/murr2k/rackspace-k8s-demo
- Main branch deploys automatically via GitHub Actions

## Next Steps for Contributors
1. Consider adding data retention policies for InfluxDB
2. Implement alerting for abnormal power consumption
3. Add support for multiple Eagle devices
4. Create mobile-responsive dashboard views
5. Add export functionality for energy reports

## Testing Commands
```bash
# Check pod status
kubectl get pods -n monitoring

# View logs
kubectl logs -f deployment/eagle-monitoring -n monitoring

# Test endpoint
curl -X POST http://119.9.118.22:30500 -H "Content-Type: text/xml" -d @test-eagle.xml

# Access Grafana
open http://119.9.118.22:30300
```

## Important Notes
- The Eagle device must be configured for XML/RAW format
- The monitoring service expects XML wrapped in `<rainforest>` tags
- All timestamps are handled in UTC
- Power values are in watts, converted to kWh for energy calculations