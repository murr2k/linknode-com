# EAGLE XML Format Analysis

## Current JSON Issues

The EAGLE device sends JSON in a nested format that's causing parsing problems:
```json
{
  "timestamp": "1752948137000",
  "deviceGuid": "d8d5b900a046",
  "body": [{
    "timestamp": "1752948125000",
    "dataType": "InstantaneousDemand",
    "data": {
      "demand": 1.71,
      "units": "kW"
    }
  }]
}
```

Current code expects flat JSON but receives nested arrays, causing 0.0 kW readings.

## Potential XML Advantages

### 1. **More Predictable Structure**
XML from EAGLE devices typically follows a consistent schema:
```xml
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
```

### 2. **Direct Data Access**
- XML elements are directly accessible
- No nested arrays to navigate
- Each message type has its own root element

### 3. **Better Error Handling**
- XML parsing errors are more descriptive
- Schema validation possible
- Malformed data easier to detect

### 4. **Separate Message Types**
Each data type comes as a separate XML document:
- `<InstantaneousDemand>` - Power usage
- `<CurrentSummationDelivered>` - Total energy
- `<PriceCluster>` - Pricing info

## Implementation Comparison

### Current JSON Parsing (Problematic)
```python
# Complex nested structure parsing
if 'body' in data and isinstance(data['body'], list):
    for item in data['body']:
        data_type = item.get('dataType', '')
        item_data = item.get('data', {})
        if data_type == 'InstantaneousDemand':
            demand = float(item_data.get('demand', 0))
```

### XML Parsing (Cleaner)
```python
# Direct element access
root = ET.fromstring(xml_data)
if root.tag == 'InstantaneousDemand':
    demand_hex = root.find('Demand').text
    multiplier = int(root.find('Multiplier').text, 16)
    divisor = int(root.find('Divisor').text, 16)
    demand = int(demand_hex, 16) * multiplier / divisor
```

## Recommendation

**YES, switching to XML would be advantageous** because:

1. **Simpler parsing** - No nested arrays
2. **More reliable** - Consistent structure
3. **Better debugging** - Clear element names
4. **Less ambiguity** - Each message type is distinct
5. **Hexadecimal values** - More precise than floating point

## How to Switch

1. In EAGLE web interface:
   - Change "Format" from JSON to XML
   - Keep other settings the same

2. Update the Flask endpoint to handle XML
3. Convert hex values to decimal
4. Store in InfluxDB as before

Would you like me to create an XML parser for your EAGLE device?