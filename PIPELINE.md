# CI/CD Pipeline Documentation

This project includes automated deployment pipelines for pushing changes to your Rackspace Kubernetes cluster.

## 🚀 Deployment Options

### Option 1: GitHub Actions (Recommended)

Automatically deploys to Rackspace when you push changes to the `main` branch.

#### Setup Instructions:

1. **Generate the kubeconfig secret**:
   ```bash
   ./scripts/prepare-kubeconfig-secret.sh
   ```

2. **Add secret to GitHub**:
   - Go to: https://github.com/murr2k/linknode-com/settings/secrets/actions
   - Click "New repository secret"
   - Name: `KUBECONFIG`
   - Value: Paste the base64 string from step 1

3. **Push changes**:
   ```bash
   git add .
   git commit -m "Update application"
   git push origin main
   ```

The pipeline will automatically:
- ✅ Deploy when you push to `main`
- ✅ Only run when files in `k8s/` or `app/` change
- ✅ Show deployment URL in the Actions summary
- ✅ Restart pods to pick up ConfigMap changes

#### Monitoring Deployments:
- View runs: https://github.com/murr2k/linknode-com/actions
- Each deployment shows the application URL
- Failed deployments show error details

### Option 2: Local Deployment Script

For quick deployments from your local machine.

#### Usage:
```bash
# Deploy with default kubeconfig location
./scripts/deploy-local.sh

# Deploy with custom kubeconfig
KUBECONFIG=/path/to/kubeconfig.yaml ./scripts/deploy-local.sh
```

The script will:
- ✅ Verify cluster connection
- ✅ Apply all Kubernetes manifests
- ✅ Restart deployment for ConfigMap changes
- ✅ Wait for rollout completion
- ✅ Display the application URL

## 📁 Pipeline Files

```
.github/workflows/
└── deploy.yml          # GitHub Actions workflow

scripts/
├── deploy-local.sh     # Local deployment script
└── prepare-kubeconfig-secret.sh  # Secret preparation helper
```

## 🔒 Security Considerations

1. **Kubeconfig Storage**:
   - Never commit kubeconfig to the repository
   - Use GitHub Secrets for Actions
   - Keep local kubeconfig secure

2. **Access Control**:
   - Only users with repository write access can trigger deployments
   - GitHub Actions uses encrypted secrets
   - Local deployments require kubeconfig access

## 🔧 Customization

### Modify Deployment Trigger

Edit `.github/workflows/deploy.yml`:
```yaml
on:
  push:
    branches: [ main, develop ]  # Add more branches
```

### Add Build Steps

For custom Docker images, add to the workflow:
```yaml
- name: Build and push Docker image
  run: |
    docker build -t myregistry/demo-app:${{ github.sha }} ./app
    docker push myregistry/demo-app:${{ github.sha }}
```

### Environment Variables

Add deployment-specific configs:
```yaml
env:
  KUBE_NAMESPACE: production
  REPLICAS: 5
```

## 🚨 Troubleshooting

### GitHub Actions Fails

1. Check the Actions tab for error logs
2. Verify the `KUBECONFIG` secret is set correctly
3. Ensure the kubeconfig is still valid

### Local Deployment Fails

1. Check cluster connectivity:
   ```bash
   kubectl cluster-info
   ```

2. Verify kubeconfig path:
   ```bash
   echo $KUBECONFIG
   ```

3. Check namespace exists:
   ```bash
   kubectl get ns demo-app
   ```

## 📈 Best Practices

1. **Test Locally First**: Use `deploy-local.sh` before pushing
2. **Review Changes**: Check the diff before deploying
3. **Monitor Deployments**: Watch the GitHub Actions logs
4. **Rollback Plan**: Keep previous manifests for quick rollback

## 🔄 Continuous Deployment Flow

```
Developer → Git Push → GitHub Actions → Kubernetes API → Rackspace Cluster
    ↓                                                            ↓
Local Test ← Application URL ← Deployment Status ← Updated Pods
```

Your pipeline is now ready for continuous deployment! 🎉