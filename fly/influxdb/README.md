# InfluxDB Deployment on Fly.io

## Current Status

InfluxDB has been successfully deployed with the following configuration:

- **App Name**: linknode-influxdb
- **Region**: ord (Chicago)
- **Machine ID**: 3d8de92b053758
- **Status**: Running ✅

## Admin Credentials

- **Organization**: linknode
- **Username**: admin
- **Password**: (set via fly secrets)
- **Admin Token**: (generated during deployment - check fly secrets)

## Configuration

- **Initial Bucket**: energy (5-year retention)
- **Internal URL**: http://linknode-influxdb.internal:8086
- **Volume**: 1GB persistent storage mounted at /var/lib/influxdb2
- **Estimated data rate**: ~210 KB/day (~77 MB/year)

## Next Steps

1. Set the admin token in your other Fly apps:
   ```bash
   fly secrets set INFLUXDB_TOKEN='<your-influxdb-token>' --app linknode-eagle-monitor
   fly secrets set INFLUXDB_TOKEN='<your-influxdb-token>' --app linknode-grafana
   ```

2. Configure your applications to use InfluxDB:
   - URL: `http://linknode-influxdb.internal:8086`
   - Organization: `linknode`
   - Bucket: `energy`
   - Token: Use the INFLUXDB_TOKEN secret

## Files

- `Dockerfile`: Custom InfluxDB image with initialization
- `init-influxdb.sh`: Initialization script that generates admin token
- `fly.toml`: Fly.io configuration
- `deploy.sh`: Deployment script
- `verify-influxdb.sh`: Verification script (requires SSH access)

## Admin Operations

InfluxDB is not publicly accessible - admin operations must be performed via SSH from inside the container using the internal API.

### Authentication

First, retrieve the token from the container environment:

```bash
flyctl ssh console -a linknode-influxdb -C "printenv INFLUXDB_TOKEN"
```

Then use that token value in subsequent curl commands. The token is also stored as a Fly secret and can be viewed with `flyctl secrets list -a linknode-influxdb`.

### List Buckets

```bash
TOKEN="<your-token-here>"
flyctl ssh console -a linknode-influxdb -C "curl -s -H 'Authorization: Token $TOKEN' 'http://localhost:8086/api/v2/buckets?org=linknode'"
```

### Update Bucket Retention

First get the bucket ID from the list command above, then:

```bash
# Example: Set retention to 5 years (157680000 seconds)
TOKEN="<your-token-here>"
BUCKET_ID="f7a54245a68d857f"
flyctl ssh console -a linknode-influxdb -C "curl -s -X PATCH -H 'Authorization: Token $TOKEN' -H 'Content-Type: application/json' -d '{\"retentionRules\": [{\"type\": \"expire\", \"everySeconds\": 157680000}]}' 'http://localhost:8086/api/v2/buckets/$BUCKET_ID'"
```

Current bucket IDs:
- `energy`: `f7a54245a68d857f`
- `_monitoring`: `86302d3d2d685d53`
- `_tasks`: `7ea2f569e9196c5e`

### Check Storage Usage

```bash
flyctl ssh console -a linknode-influxdb -C "du -sh /var/lib/influxdb2/engine"
```

## Troubleshooting

If you need to access InfluxDB directly:
```bash
flyctl ssh console -a linknode-influxdb
```

To check logs:
```bash
flyctl logs -a linknode-influxdb
```

To restart the service:
```bash
flyctl apps restart linknode-influxdb
```