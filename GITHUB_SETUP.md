# GitHub CI/CD Setup for Fly.io Deployments

This guide explains how to set up automated deployments from GitHub to Fly.io.

## Prerequisites

1. GitHub repository access
2. Fly.io account with deployed apps
3. Fly.io CLI installed locally

## Setting up GitHub Secrets

### 1. Get your Fly.io API Token

I've generated a deploy token for you. Use this token:
```
FlyV1 fm2_lJPECAAAAAAACXgyxBCdmBlo3wKQxkYD4v+XiMuUwrVodHRwczovL2FwaS5mbHkuaW8vdjGWAJLOABIpYR8Lk7lodHRwczovL2FwaS5mbHkuaW8vYWFhL3YxxDzAE6+vJHkj2lKRmK8UTIpjh0V5+OKPyWRG93kjqkcoB7jjo0sXnmPN2aa827s3F+Aoh4z7g2yntFy2d1LEToeNNJpiOe1lykxuoUsax/ZoFQSJzkTc0/9VFMlGony0vjerY1rkD9f/1SLjhJGmNWmdU3tlk7veT5T7OqpR3XTCI3Y6mSoAwu1pZ+c6Vg2SlAORgc4Ah6w/HwWRgqdidWlsZGVyH6J3Zx8BxCDa1NiG+ubiNfY09QfyBTg2vCUpZKHA5FP9/TDYYV1DRw==,fm2_lJPEToeNNJpiOe1lykxuoUsax/ZoFQSJzkTc0/9VFMlGony0vjerY1rkD9f/1SLjhJGmNWmdU3tlk7veT5T7OqpR3XTCI3Y6mSoAwu1pZ+c6VsQQVIvdW5nRtmyeXgt/ZtCUAMO5aHR0cHM6Ly9hcGkuZmx5LmlvL2FhYS92MZgEks5ofSK1zo4VKNMXzgARdJQKkc4AEXSUDMQQHpx01htYAEuwjI3Ohx+cEcQgMp8uqEQ9j/HnrzfjfX/8oaHRxS02S7CGsnLSiDBB8tI=
```

Alternatively, you can generate a new token with:
```bash
fly tokens create deploy
```

### 2. Add the Token to GitHub Secrets

1. Go to your GitHub repository: https://github.com/murr2k/rackspace-k8s-demo
2. Click on **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add the following secret:
   - **Name**: `FLY_API_TOKEN`
   - **Value**: Paste your Fly.io token from step 1

## How the CI/CD Pipeline Works

The pipeline is configured in `.github/workflows/deploy-fly.yml` and:

1. **Triggers on**:
   - Push to `main` branch when files in `fly/` directory change
   - Manual workflow dispatch (with option to deploy specific services)

2. **Deployment Order**:
   - InfluxDB (database must be ready first)
   - Eagle Monitor (data collector)
   - Grafana (visualization)
   - Web Interface (frontend)

3. **Features**:
   - Automatic deployment on push
   - Manual deployment option for specific services
   - Health checks after deployment
   - Deployment summary in GitHub Actions

## Usage

### Automatic Deployment

Simply push changes to the `main` branch:
```bash
git add .
git commit -m "Update web interface"
git push origin main
```

If changes are in the `fly/` directory, the deployment will trigger automatically.

### Manual Deployment

1. Go to **Actions** tab in GitHub
2. Select **Deploy to Fly.io** workflow
3. Click **Run workflow**
4. Choose which service to deploy (or 'all' for everything)
5. Click **Run workflow**

### Monitoring Deployments

1. Go to the **Actions** tab to see deployment progress
2. Click on a running workflow to see real-time logs
3. Check the summary for deployment URLs and status

## Local Development Workflow

### Quick Edits
```bash
# Make changes
vim fly/web/index.html

# Test locally if needed
cd fly/web
docker build -t test .
docker run -p 8080:80 test

# Commit and push
git add -A
git commit -m "Update landing page content"
git push origin main
```

### Larger Changes
```bash
# Create a feature branch
git checkout -b feature/new-dashboard

# Make changes
# ... edit files ...

# Commit changes
git add -A
git commit -m "Add new dashboard features"

# Push branch
git push origin feature/new-dashboard

# Create Pull Request on GitHub
# After review, merge to main to trigger deployment
```

## Troubleshooting

### Deployment Fails

1. Check GitHub Actions logs for errors
2. Verify Fly.io token is still valid:
   ```bash
   fly auth whoami
   ```
3. Check service logs:
   ```bash
   fly logs -a linknode-web
   ```

### Token Expired

If your Fly.io token expires:
1. Generate a new token: `fly auth token`
2. Update the GitHub secret with the new token

### Service-Specific Issues

Deploy individual services manually:
```bash
cd fly/grafana
fly deploy --remote-only
```

## Best Practices

1. **Test Locally First**: Use Docker to test changes before pushing
2. **Use Feature Branches**: Create PRs for review before merging to main
3. **Monitor Deployments**: Check the Actions tab after pushing
4. **Keep Secrets Secure**: Never commit tokens or passwords to the repository
5. **Document Changes**: Update relevant README files when making significant changes

## Quick Reference

- **Main Site**: https://linknode.com
- **Fly.io Dashboard**: https://fly.io/dashboard
- **GitHub Actions**: https://github.com/murr2k/rackspace-k8s-demo/actions
- **Fly.io Docs**: https://fly.io/docs/