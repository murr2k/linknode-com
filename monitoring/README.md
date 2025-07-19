# Power Line Monitoring Dashboard

Real-time power consumption monitoring system for EAGLE smart meter devices, built on Kubernetes with InfluxDB and Grafana.

## 🚀 Features

- **Real-time Power Monitoring**: Displays current power demand in kilowatts
- **Energy Consumption Tracking**: Total kWh consumed over time
- **Historical Graphs**: Visualize power usage patterns
- **EAGLE Device Compatible**: Supports Rainforest Automation EAGLE-200 JSON format
- **Scalable Architecture**: Runs on Kubernetes with auto-scaling capabilities

## 📊 Architecture

```
EAGLE Device → Flask API → InfluxDB → Grafana Dashboard
     ↓             ↓           ↓            ↓
  JSON POST   Parse & Store  Time-Series  Visualize
```

## 🛠️ Components

1. **Flask API** (`/api/power-data`)
   - Receives JSON data from EAGLE devices
   - Parses both InstantaneousDemand and CurrentSummation data
   - Returns empty 200 OK for EAGLE compatibility

2. **InfluxDB**
   - Time-series database for power metrics
   - 30-day data retention
   - Stores demand (kW) and consumption (kWh)

3. **Grafana**
   - Real-time dashboard with power gauge
   - Energy consumption counter
   - Historical usage graphs

## 📋 Setup Instructions

### 1. Deploy the Stack

```bash
cd monitoring
./deploy-monitoring.sh
```

### 2. Configure EAGLE Device

In your EAGLE web interface, add an upload destination:

- **Protocol**: HTTP
- **Hostname**: 119.9.118.22
- **URL**: /api/power-data
- **Port**: 30500
- **Format**: JSON

### 3. Access Dashboards

- **Grafana**: http://119.9.118.22:30300 (admin/admin)
- **API Status**: http://119.9.118.22:30500
- **Latest Reading**: http://119.9.118.22:30500/api/power-data/latest

## 🔧 EAGLE Data Format

The system handles the EAGLE JSON format:

```json
{
  "timestamp": "1752934862000",
  "deviceGuid": "d8d5b900a046",
  "body": [{
    "timestamp": "1752934824000",
    "dataType": "InstantaneousDemand",
    "data": {
      "demand": 0.696,
      "units": "kW"
    }
  }]
}
```

## 📈 Grafana Dashboard

The Power Line Monitoring dashboard includes:

1. **Current Power Demand Gauge**
   - Real-time power usage in kW
   - Color-coded thresholds (green < 3kW, yellow 3-5kW, red > 5kW)

2. **Total Energy Consumed**
   - Cumulative kWh counter
   - 24-hour total consumption

3. **Power Demand Over Time**
   - Time-series graph
   - 1-hour rolling window
   - Auto-refresh every 5 seconds

## 🧪 Testing

Send test data to verify the system:

```bash
python3 test-eagle-data.py --url http://119.9.118.22:30500 --count 5
```

## 🔍 Troubleshooting

### No Data in Dashboard
1. Check EAGLE status shows "OK"
2. Verify API endpoint: `curl http://119.9.118.22:30500/api/power-data/test`
3. Check Flask logs: `kubectl logs -l app=demo-app-monitoring -n demo-app`

### EAGLE Shows Error(404)
- Ensure all fields are filled (Protocol, Hostname, URL, Port)
- Try direct HTTP connection first before HTTPS

### Dashboard Import Issues
- Manually import from: `monitoring/power-dashboard.json`
- Select InfluxDB as the data source

## 📝 Version History

- **v1.0.0** - Initial release with EAGLE JSON format support
- **v1.1.0** - Fixed parser for nested EAGLE data structure

## 🤝 Contributing

This is part of the Rackspace Kubernetes Demo project showcasing AI-augmented development capabilities.