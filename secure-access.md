# Secure SSH-Only Access to Kubernetes Application

## Overview
The demo application is now configured for SSH-only access. There is no public endpoint - all access must go through SSH tunnels.

## Access Methods

### Method 1: Direct SSH Tunnel (Recommended)

1. **On the Kubernetes host**, start the port forwarder:
   ```bash
   cd /home/murr2k/projects/rackspace/demo-app
   ./ssh-tunnel-setup.sh
   ```

2. **From your local machine**, create an SSH tunnel:
   ```bash
   ssh -L 8081:localhost:8081 user@your-kubernetes-host
   ```

3. **Access the application** at: http://localhost:8081

### Method 2: One-Command SSH Tunnel

Run this single command from your local machine:
```bash
ssh -t -L 8080:localhost:8080 user@your-kubernetes-host \
  "export KUBECONFIG=/home/murr2k/projects/rackspace/kubeconfig.yaml && \
   kubectl port-forward -n demo-app svc/demo-app-service 8081:80"
```

### Method 3: Background SSH Tunnel

For long-running access, use background mode:
```bash
# Start tunnel in background
ssh -f -N -L 8080:localhost:8080 user@your-kubernetes-host

# On the host, run port-forward
ssh user@your-kubernetes-host
export KUBECONFIG=/home/murr2k/projects/rackspace/kubeconfig.yaml
kubectl port-forward -n demo-app svc/demo-app-service 8081:80 &
```

## Security Benefits

1. **No Public Exposure**: Application is not accessible from the internet
2. **SSH Authentication**: Access requires valid SSH credentials
3. **Encrypted Traffic**: All traffic goes through SSH encryption
4. **Audit Trail**: SSH access can be logged and monitored
5. **No LoadBalancer Costs**: No external load balancer resources

## Multiple Users

To allow multiple users to access simultaneously, use different local ports:

- User 1: `ssh -L 8081:localhost:8081 ...`
- User 2: `ssh -L 8082:localhost:8081 ...`
- User 3: `ssh -L 8083:localhost:8081 ...`

## Troubleshooting

### Port Already in Use
If you get "bind: address already in use", either:
- Use a different local port: `ssh -L 9090:localhost:8081 ...`
- Kill the existing process: `lsof -ti:8081 | xargs kill -9`

### Connection Refused
Ensure kubectl port-forward is running on the host:
```bash
ps aux | grep port-forward
```

### SSH Connection Issues
Check SSH connectivity:
```bash
ssh -v user@your-kubernetes-host
```

## Stopping Access

1. Stop the port-forward: Press `Ctrl+C` in the terminal running kubectl
2. Close SSH tunnel: Exit the SSH session or kill the SSH process
3. Optional: Scale down the deployment:
   ```bash
   kubectl scale deployment demo-app -n demo-app --replicas=0
   ```