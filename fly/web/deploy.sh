#!/bin/bash
# Deploy script for linknode-web that generates dynamic build info

set -e

cd "$(dirname "$0")"

# Get git information
COMMIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
COMMIT_FULL=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -u +%Y-%m-%d)
BUILD_TIME=$(date -u +%H:%M:%S)

# Get version from git tags or generate one
VERSION=$(git describe --tags --always 2>/dev/null || echo "v1.0.0-${COMMIT_SHA}")

# Count commits for build number (fallback for manual deploys)
BUILD_NUMBER=$(git rev-list --count HEAD 2>/dev/null || echo "0")

# Get deployer info
DEPLOYER=$(git config user.name 2>/dev/null || echo "manual")

echo "Generating build-info.json..."

cat > build-info.json << EOF
{
  "version": "${VERSION}",
  "buildDate": "${BUILD_DATE}",
  "buildTime": "${BUILD_TIME}",
  "commit": "${COMMIT_SHA}",
  "commitFull": "${COMMIT_FULL}",
  "branch": "${BRANCH}",
  "buildNumber": "${BUILD_NUMBER}",
  "environment": "production",
  "deployedBy": "${DEPLOYER}"
}
EOF

echo "Build info:"
cat build-info.json
echo ""

echo "Deploying to Fly.io..."
flyctl deploy --remote-only "$@"

echo ""
echo "Deployment complete!"
echo "View at: https://linknode.com"
