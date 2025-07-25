# Migration to Fly.io Complete

This project has been successfully migrated from Kubernetes to Fly.io.

## What Changed
- **Platform**: Kubernetes → Fly.io
- **Configuration**: YAML manifests → fly.toml files
- **Deployment**: kubectl → fly deploy
- **Services**: K8s services → Fly.io apps

## Current Structure
```
/fly
├── web/           # Main web interface
├── eagle-monitor/ # Eagle-200 data receiver
├── grafana/       # Grafana dashboards
└── influxdb/      # Time-series database
```

## Archived Files
Legacy Kubernetes configurations have been moved to: `$(echo $ARCHIVE_DIR)`

## Deployment
To deploy services, use:
```bash
cd fly/<service>
fly deploy
```

Or use the GitHub Actions workflow for automated deployment.
