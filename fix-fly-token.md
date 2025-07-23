# Fix Fly.io CI/CD Token Issue

## Problem
The GitHub Actions workflow is failing because the FLY_API_TOKEN in GitHub secrets doesn't have access to all the required apps. The authentication verification shows it can only see `linknode-grafana` but not the other apps (linknode-influxdb, linknode-eagle-monitor, linknode-web).

## Solution
You need to update the FLY_API_TOKEN in GitHub secrets with a token that has access to all apps.

### Step 1: Generate a new token with full access
Run this command locally (where you're authenticated with access to all apps):
```bash
flyctl auth token
```

This will generate a token with full access to all your apps.

### Step 2: Update GitHub Secret
1. Copy the entire token output (it will start with `FlyV1`)
2. Go to: https://github.com/murr2k/rackspace-k8s-demo/settings/secrets/actions
3. Click on `FLY_API_TOKEN`
4. Click "Update secret"
5. Paste the new token
6. Click "Update secret"

### Step 3: Test the deployment
The CI/CD pipeline should now work correctly and deploy to all Fly.io apps.

## Alternative: Use Organization Token
If the apps are in an organization, you might need to generate an organization-specific token:
```bash
flyctl tokens create org -o YOUR_ORG_NAME
```

## What Changed in the Code
1. Added FLY_API_TOKEN environment variable to all deployment steps
2. Added authentication verification step to help diagnose token issues
3. Fixed InfluxDB fly.toml to include required service ports