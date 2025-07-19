#!/bin/bash

echo "=== Testing XML Power Monitor Locally ==="
echo ""

# Test data that EAGLE would send
cat > /tmp/eagle-instant-demand.xml << 'EOF'
<InstantaneousDemand>
  <DeviceMacId>0xd8d5b900a046</DeviceMacId>
  <MeterMacId>0x00135003007xxxxx</MeterMacId>
  <TimeStamp>0x5a6b4c7d</TimeStamp>
  <Demand>0x000002bc</Demand>
  <Multiplier>0x00000001</Multiplier>
  <Divisor>0x000003e8</Divisor>
  <DigitsRight>0x03</DigitsRight>
  <DigitsLeft>0x06</DigitsLeft>
  <SuppressLeadingZero>Y</SuppressLeadingZero>
</InstantaneousDemand>
EOF

cat > /tmp/eagle-summation.xml << 'EOF'
<CurrentSummationDelivered>
  <DeviceMacId>0xd8d5b900a046</DeviceMacId>
  <MeterMacId>0x00135003007xxxxx</MeterMacId>
  <TimeStamp>0x5a6b4c7e</TimeStamp>
  <SummationDelivered>0x000030d4</SummationDelivered>
  <Multiplier>0x00000001</Multiplier>
  <Divisor>0x000003e8</Divisor>
  <DigitsRight>0x03</DigitsRight>
  <DigitsLeft>0x06</DigitsLeft>
  <SuppressLeadingZero>Y</SuppressLeadingZero>
</CurrentSummationDelivered>
EOF

echo "Testing XML parsing locally..."
python3 -c "
import xml.etree.ElementTree as ET

def parse_hex_value(hex_string):
    if hex_string and hex_string.startswith('0x'):
        return int(hex_string, 16)
    return 0

# Test InstantaneousDemand
with open('/tmp/eagle-instant-demand.xml', 'r') as f:
    root = ET.fromstring(f.read())
    demand_raw = parse_hex_value(root.find('Demand').text)
    multiplier = parse_hex_value(root.find('Multiplier').text)
    divisor = parse_hex_value(root.find('Divisor').text)
    demand_kw = (demand_raw * multiplier) / divisor
    print(f'Demand: {demand_kw:.3f} kW (raw={demand_raw}, hex=0x{demand_raw:x})')

# Test CurrentSummationDelivered
with open('/tmp/eagle-summation.xml', 'r') as f:
    root = ET.fromstring(f.read())
    summ_raw = parse_hex_value(root.find('SummationDelivered').text)
    multiplier = parse_hex_value(root.find('Multiplier').text)
    divisor = parse_hex_value(root.find('Divisor').text)
    total_kwh = (summ_raw * multiplier) / divisor
    print(f'Total Delivered: {total_kwh:.3f} kWh (raw={summ_raw}, hex=0x{summ_raw:x})')
"

echo ""
echo "Expected values:"
echo "- Demand: 0x2bc = 700 decimal, /1000 = 0.700 kW"
echo "- Total: 0x30d4 = 12500 decimal, /1000 = 12.500 kWh"

# Clean up
rm -f /tmp/eagle-*.xml