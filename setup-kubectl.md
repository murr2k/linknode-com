# Configure kubectl for Rackspace Kubernetes

To configure kubectl to connect to your Kubernetes cluster, you need to:

## Option 1: Download kubeconfig from Rackspace Control Panel

1. Log into your Rackspace Cloud Control Panel
2. Navigate to your Kubernetes cluster
3. Click "Download kubeconfig" or "Access" 
4. Save the file as `~/.kube/config`

## Option 2: Use Rackspace CLI

If you have the Rackspace CLI installed:
```bash
# List your clusters
rack orchestration cluster list

# Get kubeconfig for your cluster
rack orchestration cluster kubeconfig <cluster-name> > ~/.kube/config
```

## Option 3: Manual Configuration

If you have the cluster details, create `~/.kube/config`:

```yaml
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: <base64-encoded-ca-cert>
    server: https://<your-cluster-endpoint>
  name: rackspace-k8s
contexts:
- context:
    cluster: rackspace-k8s
    user: rackspace-k8s-user
  name: rackspace-k8s
current-context: rackspace-k8s
kind: Config
preferences: {}
users:
- name: rackspace-k8s-user
  user:
    client-certificate-data: <base64-encoded-client-cert>
    client-key-data: <base64-encoded-client-key>
```

## After Configuration

Test the connection:
```bash
kubectl cluster-info
kubectl get nodes
kubectl get pods -n demo-app
```

## Common Issues

1. **Connection refused on localhost:8080**: kubectl is trying to connect to a local cluster. This means no kubeconfig is set.

2. **Unable to connect to the server**: Check if the cluster endpoint is reachable and credentials are valid.

3. **Unauthorized**: The credentials in kubeconfig may be expired or invalid.

## Need Help?

If you have the kubeconfig file somewhere else, you can:
- Copy it to `~/.kube/config`
- Or use: `export KUBECONFIG=/path/to/your/kubeconfig`
- Or use: `kubectl --kubeconfig=/path/to/kubeconfig get pods`