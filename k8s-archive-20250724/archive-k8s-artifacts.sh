#!/bin/bash
# Archive legacy Kubernetes artifacts after migration to Fly.io

echo "🗄️  Archiving legacy Kubernetes artifacts..."

# Create archive directory with timestamp
ARCHIVE_DIR="k8s-archive-$(date +%Y%m%d)"
mkdir -p "$ARCHIVE_DIR"

# Create a README in the archive
cat > "$ARCHIVE_DIR/README.md" << 'EOF'
# Archived Kubernetes Configuration Files

These files were archived after the migration from Kubernetes to Fly.io.

**Archive Date**: $(date +"%Y-%m-%d")
**Reason**: Project migrated from Kubernetes to Fly.io platform

## Migration Details
- The project was originally deployed on Kubernetes
- Migrated to Fly.io for simpler deployment and management
- These files are kept for historical reference only

## Current Deployment
The application is now deployed on Fly.io with the following services:
- linknode-web
- linknode-eagle-monitor  
- linknode-grafana
- linknode-influxdb

See `/fly` directory for current deployment configurations.
EOF

# Move k8s directory to archive
if [ -d "k8s" ]; then
    echo "Moving k8s directory to archive..."
    mv k8s "$ARCHIVE_DIR/"
    echo "✅ Kubernetes files archived to $ARCHIVE_DIR/k8s"
else
    echo "⚠️  k8s directory not found"
fi

# Archive any other K8s related files in root
K8S_FILES=$(find . -maxdepth 1 -name "*k8s*" -o -name "*kubernetes*" | grep -v "$ARCHIVE_DIR")
if [ -n "$K8S_FILES" ]; then
    echo "Found additional K8s files to archive:"
    echo "$K8S_FILES"
    for file in $K8S_FILES; do
        mv "$file" "$ARCHIVE_DIR/"
        echo "  Moved: $file"
    done
fi

# Create a migration summary
cat > "FLY_MIGRATION_COMPLETE.md" << 'EOF'
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
EOF

echo ""
echo "📋 Summary:"
echo "  - Kubernetes artifacts archived to: $ARCHIVE_DIR"
echo "  - Migration documentation created: FLY_MIGRATION_COMPLETE.md"
echo "  - Original k8s directory removed"
echo ""
echo "✅ Cleanup complete!"