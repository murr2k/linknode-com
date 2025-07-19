# Finding Your Power Line Monitoring Dashboard

Since Grafana says it already exists, let's find it:

## Method 1: Dashboard List
1. Click **Dashboards** in the left sidebar (four squares icon)
2. You should see "Power Line Monitoring" in the list
3. Click on it to open

## Method 2: Search
1. Click the **Search** icon (magnifying glass) in the left sidebar
2. Type "power" or "energy" or "eagle"
3. The dashboard should appear in results

## Method 3: Browse Folders
1. Go to **Dashboards** → **Browse**
2. Look in the "General" or "Default" folder
3. Find "Power Line Monitoring"

## Method 4: Direct Links
Try these direct URLs:
- http://119.9.118.22:30300/dashboards
- http://119.9.118.22:30300/d/power-monitoring/power-line-monitoring

## If You Still Can't Find It:

Check provisioned dashboards:
1. Go to **Administration** → **Provisioning** → **Dashboards**
2. Look for dashboards from the "default" provider

## Dashboard Not Showing Data?

If you find the dashboard but it's empty:
1. Check the time range (top right) - set to "Last 1 hour"
2. Verify the data source is "InfluxDB"
3. Click the refresh button (circular arrow)

The dashboard exists - it's just a matter of finding it in the Grafana interface!