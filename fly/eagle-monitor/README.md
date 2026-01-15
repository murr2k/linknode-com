# Eagle-200 XML Monitor for Fly.io

This service receives XML POST data from an Eagle-200 energy monitor device and stores it in InfluxDB.

## Features

- Accepts XML POST requests at `/eagle` endpoint
- Parses Eagle-200 XML format for power and energy data
- Writes data to InfluxDB with proper timestamps
- Provides statistics endpoint at `/api/stats`
- Health check endpoint at `/health`
- Minimal resource usage (256MB RAM)

## Configuration

The Eagle-200 device should be configured to POST data to:
```
http://linknode-eagle-monitor.fly.dev/eagle
```

## Deployment

1. Deploy the monitor:
   ```bash
   ./deploy.sh
   ```

2. Configure your Eagle-200 device to send data to the endpoint above.

## API Endpoints

- `POST /eagle` - Receives XML data from Eagle-200
- `GET /` - Service information
- `GET /api/stats` - Monitor statistics
- `GET /health` - Health check

## Environment Variables

- `INFLUXDB_URL` - InfluxDB URL (default: http://linknode-influxdb.internal:8086)
- `INFLUXDB_TOKEN` - Authentication token (set as secret)
- `INFLUXDB_ORG` - Organization name (default: linknode)
- `INFLUXDB_BUCKET` - Bucket name (default: energy)

## Data Format

The monitor handles several types of Eagle-200 messages:

1. **InstantaneousDemand** - Current power consumption in watts
2. **CurrentSummationDelivered** - Total energy consumed in kWh
3. **PriceCluster** - Current electricity rate from utility
4. **MessageCluster** - Text messages from utility
5. **TimeCluster** - Time synchronization
6. **NetworkInfo** - Network status

Data is stored in InfluxDB with:
- Measurement: `energy_monitor`
- Tags: `device_mac`, `meter_mac`, `message_type`
- Fields: `power_w` (watts), `energy_delivered_kwh`, `price_per_kwh`, etc.

## Data Flow & Rainforest Cloud Repackaging

The Eagle device does not send data directly to Linknode. Instead:

```
Eagle-200 (Cloud ID: 00a046)
    → Rainforest Cloud (rainforestautomation.com)
        → Repackaged XML forwarded to configured upload destinations
            → Linknode /eagle endpoint
```

**Important:** Rainforest's cloud repackages the XML data before forwarding it to upload
destinations. The `DeviceMacId` in the forwarded XML is NOT the Eagle's Cloud ID, but
rather identifiers assigned by Rainforest's internal systems.

### Observed Device MAC Schema

Rainforest forwards data using two different DeviceMacId values, but **only one is actively
reporting meter data**:

| Device MAC | Message Types | Activity |
|------------|---------------|----------|
| `d8d5b9000000ef68` | message_cluster | **Dormant** - Only forwards utility text messages (~450/day) |
| `d8d5b9000000ef69` | instantaneous_demand, current_summation_delivered, message_cluster, price_cluster | **Active** - Primary data source |

**Observed report rates (ef69):**

| Message Type | Rate | Count/24h |
|--------------|------|-----------|
| instantaneous_demand (power_w) | ~1 every 9 seconds | ~9,700 |
| current_summation_delivered (energy_kwh) | ~1 every 27 seconds | ~3,200 |
| price_cluster (price_per_kwh) | ~1 every 65 seconds | ~1,300 |

Both device MACs read from the same utility meter (`meter_mac: 0007810000a4505c`), but
`ef68` is essentially inactive for power/energy data - it only forwards `message_cluster`
(utility text messages). **No filtering is required** since `ef69` is the sole source of
meter readings.

### Why Two Device MACs?

Per the [EAGLE-200 Local API Manual](https://rainforestautomation.com), the Eagle-200 contains
**two independent Zigbee radios** (see page 10):

1. **Utility HAN Radio** - Connects to the smart meter via Zigbee SEP protocol
2. **Control Network Radio** - Acts as coordinator for subdevices (smart plugs, thermostats)

Each radio has its own MAC address. When Rainforest's cloud forwards XML data, the
`<DeviceMacId>` field reflects which internal radio handled the data:

| Identifier | MAC Address | Purpose | Status |
|------------|-------------|---------|--------|
| Cloud ID (Ethernet) | `d8d5b9000000a046` | Device identification, Local API auth | - |
| Zigbee Radio 1 (HAN) | `d8d5b9000000ef68` | Utility HAN - meter communication | Dormant (messages only) |
| Zigbee Radio 2 (Control) | `d8d5b9000000ef69` | Control Network - subdevice control | **Active** (all meter data) |

In practice, `ef69` (Control Network radio) handles all meter data forwarding, while `ef68`
(HAN radio) only forwards utility text messages. This means **no query aggregation or
filtering is needed** - all power/energy data comes from a single source.

### Query Considerations

Since `ef69` is the sole source of meter data, queries are straightforward:

```flux
// Get current power (no aggregation needed)
from(bucket: "energy")
  |> filter(fn: (r) => r._field == "power_w")
  |> last()

// Get energy consumption over time range
from(bucket: "energy")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._field == "power_w")
  |> integral(unit: 1h)

// Get current electricity rate
from(bucket: "energy")
  |> filter(fn: (r) => r._field == "price_per_kwh")
  |> last()
```

**Note:** Historical data may contain records from both device MACs. If querying older data
where both were active, use `|> group()` to aggregate or filter to `ef69`.