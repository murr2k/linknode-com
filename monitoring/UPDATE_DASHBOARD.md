# Update Grafana Dashboard

## Current Dashboard Analysis

The current dashboard has some panels that could be better utilized. Here's an improved version that makes better use of the data from your EAGLE device.

## Enhanced Dashboard Features

The new dashboard (`improved-dashboard.json`) includes:

1. **Current Power Demand** (Gauge)
   - Shows real-time power consumption
   - Color-coded thresholds (green < 3kW, yellow 3-5kW, red > 5kW)
   - Shows threshold values on the gauge

2. **Total Energy Delivered** (Stat)
   - Shows cumulative energy from the grid
   - This is the actual meter reading

3. **24h Consumption** (Pie Chart)
   - Shows daily energy usage
   - Calculated from the difference in readings

4. **Power Demand Over Time** (Time Series)
   - 1-hour rolling window
   - Shows mean, max, min in legend
   - Red threshold line at 5kW

5. **Power Demand Range** (Stats)
   - Shows min/max power in last hour
   - Color-coded (green for min, red for max)

6. **Average Power Consumption** (State Timeline)
   - Shows 5-min, 15-min, and 1-hour averages
   - Color-coded by consumption level

## How to Update

### Option 1: Import the Enhanced Dashboard

1. Go to Grafana: http://119.9.118.22:30300
2. Click **Dashboards** → **New** → **Import**
3. Upload the file: `monitoring/improved-dashboard.json`
4. Select **InfluxDB** as the data source
5. Click **Import**

### Option 2: Update Existing Dashboard

1. Open your current dashboard
2. Click the gear icon (⚙️) → **Settings**
3. Go to **JSON Model**
4. Replace with contents from `improved-dashboard.json`
5. Save the dashboard

## Removing Unused Indicators

The enhanced dashboard removes:
- Unused table view (replaced with more useful visualizations)
- Redundant net consumption (using actual delivered/received values)
- Static text panels

## Additional Customization Ideas

Based on your EAGLE data, you could add:

1. **Cost Calculator**
   - Multiply kWh by your electricity rate
   - Show daily/monthly cost estimates

2. **Peak Detection**
   - Alert when power exceeds certain thresholds
   - Track peak usage times

3. **Solar Integration** (if applicable)
   - Show power received (solar generation)
   - Net metering visualization

4. **Usage Patterns**
   - Heatmap of usage by hour/day
   - Weekly usage comparison

Would you like me to implement any of these additional features?