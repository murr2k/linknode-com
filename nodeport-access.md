# NodePort Public Access

Your Kubernetes demo is now publicly accessible via NodePort!

## 🌐 Access URL
```
http://119.9.118.22:32091
```

## Details
- **Node IP**: 119.9.118.22 (Rackspace node)
- **NodePort**: 32091 (automatically assigned)
- **Service Type**: NodePort
- **Cost**: FREE - No additional charges

## How NodePort Works
1. Kubernetes opens port 32091 on the node
2. Traffic to this port is forwarded to your pods
3. Works with any pod replica automatically

## Security Considerations
- The application is now publicly accessible
- Anyone with the URL can view the demo
- No authentication is configured
- Traffic is unencrypted (HTTP)

## To Disable Public Access
If you want to remove public access later:
```bash
kubectl patch svc demo-app-service -n demo-app -p '{"spec":{"type":"ClusterIP"}}'
```

## Alternative Access Methods Still Available
- **Local**: http://localhost:8090 (via port-forward)
- **Public**: http://119.9.118.22:32091 (via NodePort)

## Sharing the Demo
You can now share this URL with others:
- Colleagues can access it directly
- No SSH or kubectl required
- Works from any browser

## Cost Savings
- ✅ No LoadBalancer fees
- ✅ Uses existing node IP
- ✅ No additional infrastructure
- ✅ Estimated savings: $10-25/month vs LoadBalancer