# Rackspace K8s Demo Project State
Last Updated: 2025-07-20

## Overview
This project implements a complete energy monitoring solution with real-time power consumption tracking, deployed on Rackspace Kubernetes infrastructure. It features an interactive web interface with live widgets, public Grafana dashboards, and Eagle-200 XML data ingestion.

## Current Architecture

### Services and Endpoints
- **Main Demo Page**: http://119.9.118.22:30898
- **Grafana Dashboard**: http://119.9.118.22:30300
- **Eagle XML Endpoint**: http://119.9.118.22:30500
- **Public Dashboard**: http://119.9.118.22:30300/public-dashboards/69ea815afaa245248a2f1a81491ca3f1

### Kubernetes Resources
All resources are in the `demo-app` namespace:

#### Deployments
1. **demo-app** (2 replicas) - Main web interface with nginx
2. **eagle-xml-monitor** (1 replica) - Eagle XML data ingestion service
3. **grafana** (1 replica) - Metrics visualization with anonymous access
4. **influxdb** (1 replica) - Time-series database for power metrics

#### Services
- **demo-app-service**: NodePort 30898 - Web interface
- **grafana**: NodePort 30300 - Grafana UI
- **eagle-xml-monitor**: NodePort 30500 - Eagle data endpoint
- **influxdb**: ClusterIP (internal only) - Database

#### ConfigMaps
- **nginx-config**: Enhanced webpage with live widgets
- **eagle-xml-code**: Eagle monitoring service with stats API
- **grafana-ini**: Grafana configuration for public access
- **grafana-datasources-public-v2**: InfluxDB datasource config
- **grafana-dashboards-public**: Dashboard provisioning
- **grafana-dashboard-permissions**: Public dashboard config
- **grafana-dashboard-eagle-xml**: Eagle monitoring dashboard

## Key Features Implemented

### 1. Interactive Web Interface
- Live power consumption widget (updates every 5 seconds)
- Real-time 24h statistics (min/max/avg/cost)
- Embedded Grafana dashboard (no login required)
- API status indicators for all services
- Real-time pod count display
- Fallback to simulated data when APIs unavailable

### 2. Eagle-200 XML Support
- Parses XML data wrapped in `<rainforest>` tags
- Handles InstantaneousDemand messages
- Correct power calculation: (demand * multiplier / divisor) * 1000
- Fixed timestamp parsing for proper data storage
- Stores data in InfluxDB with proper retention

### 3. Public Grafana Access
- Anonymous authentication enabled
- Public dashboard sharing configured
- CORS headers for API access
- Embedded iframe support without login
- Dashboard auto-refresh every 5 seconds

### 4. Statistics API
- Endpoint: `/api/stats` on Eagle service
- Returns 24h min/max/avg and current power
- Calculates electricity cost at $0.12/kWh
- CORS enabled for browser access

## Recent Fixes Applied
1. Fixed power calculation unit conversion (kW to W)
2. Fixed timestamp parsing (Eagle epoch adjustment)
3. Enabled public Grafana dashboard access
4. Added real-time statistics API
5. Fixed CI/CD pipeline to preserve configurations

## Configuration Details

### InfluxDB
- Token: `my-super-secret-auth-token`
- Organization: `rackspace`
- Bucket: `power_metrics`
- Retention: 30 days

### Grafana
- Admin: admin/admin
- Anonymous access: Enabled as Viewer
- Public dashboard token: `69ea815afaa245248a2f1a81491ca3f1`

### Eagle-200 Configuration
- Cloud Provider: Other
- Protocol: XML/RAW
- Hostname: 119.9.118.22
- Port: 30500
- URL: /api/eagle
- Format: XML_RAW

## CI/CD Pipeline
GitHub Actions workflow (`deploy.yml`) configured to:
- Deploy on push to main branch
- Use enhanced configurations when available
- Preserve public dashboard settings
- Deploy Eagle monitoring with stats API

## Migration Considerations for New Host

### Requirements
1. Kubernetes cluster (tested on v1.31.1)
2. LoadBalancer or NodePort service support
3. Persistent storage for InfluxDB (optional)
4. External IP or domain for public access

### Key Files to Migrate
1. All files in `/k8s/` directory
2. ConfigMaps with "-fixed", "-stats", or "-public" suffixes
3. GitHub Actions workflow for CI/CD
4. Eagle device configuration

### Environment Variables
- INFLUXDB_URL: Internal service URL
- INFLUXDB_TOKEN: Authentication token
- INFLUXDB_ORG: Organization name
- INFLUXDB_BUCKET: Data bucket name

### Challenges to Consider
1. Service exposure method (NodePort vs LoadBalancer)
2. Persistent volume claims for data retention
3. Domain/SSL configuration if needed
4. Firewall rules for Eagle device access
5. Resource limits based on new host capacity

## Current Metrics
- Average Power Consumption: ~708W
- Daily Cost: ~$2.04
- Data Points: Updated every 5-10 seconds
- Retention: 30 days of historical data