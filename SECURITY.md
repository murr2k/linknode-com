# Security Notice

## Credential Management

This project uses demonstration credentials in some YAML files for ease of setup. For production use, please follow these security practices:

### Current Demo Credentials

The following files contain demo credentials that should be changed for production:

1. **InfluxDB** (`k8s/influxdb.yaml`):
   - Username: `admin`
   - Password: `supersecretpassword` (CHANGE THIS)
   - Token: `my-super-secret-auth-token` (CHANGE THIS)

2. **Grafana** (`k8s/grafana.yaml`):
   - Username: `admin`
   - Password: `admin` (CHANGE THIS)

### Production Security Recommendations

1. **Use Kubernetes Secrets**:
   ```bash
   kubectl create secret generic influxdb-auth \
     --from-literal=admin-password='your-secure-password' \
     --from-literal=admin-token='your-secure-token' \
     -n demo-app
   ```

2. **Update Deployments** to reference secrets:
   ```yaml
   env:
   - name: INFLUXDB_ADMIN_PASSWORD
     valueFrom:
       secretKeyRef:
         name: influxdb-auth
         key: admin-password
   ```

3. **Never Commit Real Credentials**:
   - Use `.gitignore` to exclude secret files
   - Use environment variables for sensitive data
   - Use secret management tools (e.g., Sealed Secrets, Vault)

4. **Rotate Credentials Regularly**:
   - Change default passwords immediately after deployment
   - Implement credential rotation policies

### Secure Access

- The monitoring endpoints are currently open for demo purposes
- For production, implement:
  - API authentication
  - Network policies
  - TLS/HTTPS encryption
  - Rate limiting

### Reporting Security Issues

If you discover a security vulnerability, please report it to murr2k@gmail.com