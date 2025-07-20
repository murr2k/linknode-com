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
- **Password**: linknode-admin-2024
- **Admin Token**: `linknode-20250720-7468d2699f48f7f91ee4abbeec90a25f`

## Configuration

- **Initial Bucket**: energy (30-day retention)
- **Internal URL**: http://linknode-influxdb.internal:8086
- **Volume**: 1GB persistent storage mounted at /var/lib/influxdb2

## Next Steps

1. Set the admin token in your other Fly apps:
   ```bash
   fly secrets set INFLUXDB_TOKEN='linknode-20250720-7468d2699f48f7f91ee4abbeec90a25f' --app linknode-eagle-monitor
   fly secrets set INFLUXDB_TOKEN='linknode-20250720-7468d2699f48f7f91ee4abbeec90a25f' --app linknode-grafana
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

## Troubleshooting

If you need to access InfluxDB directly:
```bash
fly ssh console -a linknode-influxdb
```

To check logs:
```bash
fly logs -a linknode-influxdb
```

To restart the service:
```bash
fly apps restart linknode-influxdb
```