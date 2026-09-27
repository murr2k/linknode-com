#!/bin/bash
set -e

echo "Deploying Eagle-200 XML Monitor to Fly.io..."

# Check if app exists
if fly apps list | grep -q "linknode-eagle-monitor"; then
    echo "App already exists, deploying update..."
else
    echo "Creating new app..."
    fly apps create linknode-eagle-monitor --org personal
fi

# Secrets (EAGLE_PASSWORD, SLACK_WEBHOOK_URL, PUSHOVER_*) are set once with
# fly secrets set; readings live in SQLite on the eagle_data volume, which must
# exist before the first deploy:
#   fly volumes create eagle_data -a linknode-eagle-monitor -r ord -s 1 --snapshot-retention 14

# Deploy the app
echo "Deploying application..."
fly deploy --app linknode-eagle-monitor

# Show status
echo "Deployment complete!"
fly status --app linknode-eagle-monitor