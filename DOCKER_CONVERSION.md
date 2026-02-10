# WeatherPi Docker Conversion Summary

## Changes Made

This project has been containerized for Docker deployment with support for environment variables. Below is a summary of all changes.

### New Files Created

1. **`Dockerfile`**
   - Multi-stage Python 3.12 container
   - Installs I2C and sensor dependencies
   - Includes healthcheck
   - Optimized for Raspberry Pi deployment

2. **`docker-compose.yml`**
   - Complete container orchestration configuration
   - Includes I2C device mapping for sensor access
   - Environment variables for all configuration
   - Optional MySQL service (commented out)
   - Logging configuration
   - Restart policies

3. **`.env.sample`**
   - Template for Docker environment variables
   - Documented all available configuration options
   - MQTT broker configuration templates
   - Database and calibration offset examples

4. **`.dockerignore`**
   - Excludes unnecessary files from Docker build
   - Reduces image size and build time

5. **`DOCKER_SETUP.md`**
   - Comprehensive Docker deployment guide
   - Quick start instructions
   - Detailed configuration reference
   - Troubleshooting section
   - Production recommendations

### Modified Files

1. **`readings.py`**
   - Added environment variable support alongside config file
   - New `load_config()` function that:
     - Checks environment variables first
     - Falls back to config file if env vars not set
     - Maintains backward compatibility
   - Updated docstring to document new capability
   - Environment variables override config file settings

## Key Features

✅ **Environment Variable Configuration**: All settings can now be provided via Docker environment variables
✅ **Backward Compatible**: Still supports `readings.ini` config file as fallback
✅ **Docker Ready**: Pre-configured for deployment on Raspberry Pi and other platforms
✅ **Security**: No hardcoded secrets in image
✅ **Flexible**: Support for single or multiple MQTT brokers
✅ **Database Optional**: Can work with or without MySQL storage
✅ **I2C Support**: Properly configured for hardware sensor access

## Quick Deployment

### Option 1: Docker Run

```bash
docker build -t weatherpi:latest .

docker run -d \
  --name weatherpi \
  --privileged \
  --device /dev/i2c-1:/dev/i2c-1 \
  -e MQTT_BROKERS='[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]' \
  -e MQTT_TOPIC="Weatherstation/" \
  -e MQTT_REFRESH=300 \
  weatherpi:latest
```

### Option 2: Docker Compose (Recommended)

```bash
# Edit configuration
cp .env.sample .env
# Update .env with your MQTT broker and database settings

# Start
docker-compose up -d

# View logs
docker-compose logs -f weatherpi

# Stop
docker-compose down
```

## Configuration

### Minimal Configuration (MQTT only)

```bash
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]
```

### Full Configuration (MQTT + Database + Calibration)

```bash
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]
MQTT_TOPIC=Weatherstation/
MQTT_REFRESH=300
DB_USE_SQL=True
DB_SERVER=mysql.local
DB_NAME=weatherpi
DB_USERNAME=weatherpi_user
DB_PASSWORD=secure_password
CAL_TEMPERATURE=0.5
CAL_PRESSURE=-2.0
CAL_HUMIDITY=1.0
CAL_LUX=100
```

## Hardware Requirements

- **I2C Access**: `--privileged` flag or device mapping to `/dev/i2c-1`
- **GPIO Access**: Typically not needed for this application
- **Network**: Connection to MQTT broker (and MySQL if database enabled)

## Troubleshooting

See `DOCKER_SETUP.md` for detailed troubleshooting guide, including:
- I2C connection issues
- MQTT broker connectivity
- Sensor initialization problems
- Database connection failures

## Backward Compatibility

The application remains backward compatible:
- If no environment variables set, it uses `readings.ini`
- You can mix config file and environment variables
- Environment variables always take precedence

## Migration from Config File

To migrate from a config file setup:

1. Extract your `readings.ini` values
2. Copy `.env.sample` to `.env`
3. Update `.env` with values from `readings.ini`
4. In docker-compose.yml, uncomment `env_file: - .env`
5. Run `docker-compose up -d`

Example conversion:
```ini
[broker]
brokers = [{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]
topic = Weatherstation/
refresh = 300
```

Becomes:
```bash
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]
MQTT_TOPIC=Weatherstation/
MQTT_REFRESH=300
```

## Next Steps

1. **Test locally**: Run docker-compose.yml on your Raspberry Pi
2. **Monitor logs**: Check `docker logs weatherpi` for any issues
3. **Verify readings**: Check MQTT broker for published messages
4. **Backup configuration**: Keep your `.env` file safe
5. **Production hardening**: See recommendations in `DOCKER_SETUP.md`

## Questions or Issues?

Refer to:
- `DOCKER_SETUP.md` - Complete Docker guide
- `readings.py` - Application source code
- `.env.sample` - Configuration template
