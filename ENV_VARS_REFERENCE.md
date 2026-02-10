# WeatherPi Docker Environment Variables Quick Reference

## Overview
Configuration is provided via environment variables instead of `readings.ini`. Set these when running Docker or in `.env` file with docker-compose.

## MQTT Configuration (Required)

**MQTT_BROKERS** (Required)
- Format: JSON-encoded broker array
- Example: `[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]`
- Multiple brokers: Add more objects to the array separated by commas
- Default: None (must be set)

**MQTT_TOPIC** (Optional)
- MQTT topic prefix for sensor published messages
- Example: `Weatherstation/`
- Default: `Weatherstation/`

**MQTT_REFRESH** (Optional)
- Seconds between sensor reads and MQTT publishes
- Example: `300` (5 minutes)
- Default: `300`

## Database Configuration (Optional)

**DB_USE_SQL** (Optional)
- Enable MySQL database logging
- Values: `true`, `false`, `yes`, `no`, `1`, `0`
- Default: `false`

**DB_SERVER** (Optional, required if DB_USE_SQL=true)
- MySQL server hostname or IP address
- Example: `mysql.local` or `192.168.1.100`
- Default: Empty string

**DB_NAME** (Optional, required if DB_USE_SQL=true)
- MySQL database name
- Example: `weatherpi`
- Default: Empty string

**DB_USERNAME** (Optional, required if DB_USE_SQL=true)
- MySQL username
- Example: `weatherpi_user`
- Default: Empty string

**DB_PASSWORD** (Optional, required if DB_USE_SQL=true)
- MySQL password
- Example: `secure_password_here`
- Default: Empty string

## Sensor Calibration (Optional)

All calibration offsets are added to raw sensor readings.

**CAL_TEMPERATURE** (Optional)
- Temperature offset in degrees Celsius
- Example: `2.5` or `-0.5`
- Default: `0.0`

**CAL_PRESSURE** (Optional)
- Pressure offset in hectopascals (hPa)
- Example: `-5.0` or `2.0`
- Default: `0.0`

**CAL_HUMIDITY** (Optional)
- Humidity offset in percentage points
- Example: `1.0` or `-2.5`
- Default: `0.0`

**CAL_LUX** (Optional)
- Light intensity offset in lux
- Example: `100` or `-50.0`
- Default: `0.0`

## Usage Examples

### Example 1: Minimal Setup (Docker Run)
```bash
docker run -d --name weatherpi --privileged --device /dev/i2c-1:/dev/i2c-1 \
  -e MQTT_BROKERS='[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]' \
  weatherpi:latest
```

### Example 2: With Calibration (Docker Run)
```bash
docker run -d --name weatherpi --privileged --device /dev/i2c-1:/dev/i2c-1 \
  -e MQTT_BROKERS='[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]' \
  -e MQTT_TOPIC="WeatherStation/" \
  -e MQTT_REFRESH=300 \
  -e CAL_TEMPERATURE=1.5 \
  -e CAL_HUMIDITY=-1.0 \
  weatherpi:latest
```

### Example 3: Complete Setup (Docker Compose - in .env file)
```bash
# MQTT
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]
MQTT_TOPIC=Weatherstation/
MQTT_REFRESH=300

# Database
DB_USE_SQL=true
DB_SERVER=mysql.local
DB_NAME=weatherpi
DB_USERNAME=weatherpi_user
DB_PASSWORD=secure_password

# Calibration
CAL_TEMPERATURE=0.5
CAL_PRESSURE=-2.0
CAL_HUMIDITY=1.0
CAL_LUX=100
```

### Example 4: Multiple MQTT Brokers
```bash
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt1.local", "brokerport": 1883, "brokerusername": "user1", "brokerpassword": "pass1"}, {"py/object": "__main__.broker", "brokerfqdn": "mqtt2.local", "brokerport": 8883, "brokerusername": "user2", "brokerpassword": "pass2"}]
```

### Example 5: TLS MQTT (Port 8883)
```bash
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.example.com", "brokerport": 8883, "brokerusername": "user", "brokerpassword": "pass"}]
```

## Tips & Notes

1. **Escaping JSON**: When using command line, be careful with quotes:
   - Bash: Use single outer quotes for JSON
   - sh: May need to escape quotes differently
   - Use `.env` file with docker-compose for easier formatting

2. **Environment Variable Precedence**: Environment variables override config file values if both exist

3. **Docker Compose**: Use `env_file: .env` to load from file instead of inline

4. **Case Sensitivity**: All variable names are case-sensitive

5. **No Defaults Needed**: Only set variables you want to change from defaults

6. **Special Characters in Passwords**: May need URL encoding or proper escaping in shell

## See Also
- `DOCKER_SETUP.md` - Complete Docker deployment guide
- `.env.sample` - Full configuration template
- `DOCKER_CONVERSION.md` - Migration and conversion notes
