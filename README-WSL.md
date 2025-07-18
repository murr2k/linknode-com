# Accessing the Kubernetes Demo App from WSL2

Since you're using WSL2, you don't need SSH tunnels! WSL2 shares localhost with Windows.

## Quick Start

### Option 1: Direct Access (Simplest)

1. **In WSL terminal**, run:
   ```bash
   cd /home/murr2k/projects/rackspace/demo-app
   ./wsl-access.sh
   ```

2. **In Windows browser**, go to:
   ```
   http://localhost:8090
   ```

That's it! No SSH needed.

### Option 2: Background Process

Run in background to free up your terminal:
```bash
cd /home/murr2k/projects/rackspace/demo-app
nohup ./wsl-access.sh > port-forward.log 2>&1 &
```

To stop:
```bash
pkill -f "kubectl port-forward"
```

### Option 3: PowerShell Direct

From PowerShell, run WSL command directly:
```powershell
wsl -d Ubuntu -e bash -c "cd /home/murr2k/projects/rackspace/demo-app && ./wsl-access.sh"
```

## Troubleshooting

### Port Already in Use
```bash
# Check what's using the port
lsof -i :8090

# Kill any existing port-forwards
pkill -f "kubectl port-forward"
```

### Can't Access from Windows
Make sure the script uses `--address=0.0.0.0` flag (already configured).

### Alternative Ports
Edit `wsl-access.sh` and change 8090 to any available port:
- 9090
- 3000
- 5000
- 8888

## Security Note

This setup is secure because:
- The Kubernetes app has no public endpoint
- Access requires being on your local machine
- The port-forward only listens on localhost
- No credentials are exposed