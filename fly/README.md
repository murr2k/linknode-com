# Fly.io Deployment Structure

This directory contains the configuration files and Dockerfiles needed to deploy the Rackspace energy monitoring system on Fly.io.

## Directory Structure

```
fly/
├── influxdb/          # InfluxDB time-series database
│   ├── Dockerfile     # InfluxDB container configuration
│   ├── fly.toml       # Fly.io app configuration
│   └── init.sh        # Database initialization script
│
├── eagle-monitor/     # Eagle-200 monitoring service
│   ├── Dockerfile     # Python app container
│   ├── fly.toml       # Fly.io app configuration
│   ├── app.py         # Main Flask application
│   └── requirements.txt
│
├── grafana/           # Grafana visualization
│   ├── Dockerfile     # Grafana container configuration
│   ├── fly.toml       # Fly.io app configuration
│   ├── grafana.ini    # Grafana configuration
│   ├── provisioning/  # Auto-provisioning configs
│   │   ├── dashboards/
│   │   └── datasources/
│   └── dashboards/    # Dashboard JSON files
│
└── web/               # Static web interface
    ├── Dockerfile     # Nginx container
    ├── fly.toml       # Fly.io app configuration
    ├── nginx.conf     # Nginx configuration
    └── html/          # Static files
```

## Required Files for Each Service

### InfluxDB Service
- **Dockerfile**: Based on influxdb:2.7-alpine
- **fly.toml**: App config with persistent volume for data
- **init.sh**: Create bucket, retention policy, and API token

### Eagle Monitor Service
- **Dockerfile**: Python 3.11 with Flask
- **fly.toml**: App config with environment variables
- **app.py**: Copy from main app directory
- **requirements.txt**: Python dependencies

### Grafana Service
- **Dockerfile**: Based on grafana/grafana:10.2.0
- **fly.toml**: App config with persistent volume
- **grafana.ini**: Main configuration
- **provisioning/**: Datasource and dashboard configs

### Web Service
- **Dockerfile**: Nginx Alpine
- **fly.toml**: App config for static hosting
- **nginx.conf**: Routing configuration
- **html/**: Static HTML/CSS/JS files

## Deployment Order

1. Deploy InfluxDB first (data store)
2. Deploy Eagle Monitor (data collector)
3. Deploy Grafana (visualization)
4. Deploy Web interface (user frontend)

## Environment Variables

Each service will need specific environment variables configured in their respective fly.toml files:

- **InfluxDB**: DOCKER_INFLUXDB_INIT_* variables
- **Eagle Monitor**: INFLUXDB_URL, INFLUXDB_TOKEN, EAGLE_IP, EAGLE_USERNAME, EAGLE_PASSWORD
- **Grafana**: GF_* configuration variables
- **Web**: API endpoints for other services