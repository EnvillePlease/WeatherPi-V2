# WeatherPi Docker Deployment Guide

This guide explains how to run WeatherPi as a Docker container and configure it using environment variables instead of config files.

## Quick Start

### 1. Basic Deployment (with environment variables)

```bash
# Build the Docker image
docker build -t weatherpi:latest .

# Run the container with required environment variables
docker run -d \
  --name weatherpi \
  --privileged \
  --device /dev/i2c-1:/dev/i2c-1 \
  -e MQTT_BROKERS='[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]' \
  -e MQTT_TOPIC="Weatherstation/" \
  -e MQTT_REFRESH=300 \
  weatherpi:latest
```

### 2. Using Docker Compose (Recommended)

```bash
# Copy and edit the environment file
cp .env.sample .env
# Edit .env with your MQTT broker details and calibration values

# Start the container
docker-compose up -d

# View logs
docker-compose logs -f weatherpi

# Stop the container gracefully (30 second timeout for clean shutdown)
docker-compose stop

# Stop and remove the container
docker-compose down
```

## Configuration

Configuration is handled through **environment variables** instead of the `readings.ini` file. This is ideal for Docker deployments.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKERS` | *Required* | JSON-formatted broker configuration (see below) |
| `MQTT_TOPIC` | `Weatherstation/` | MQTT topic prefix for publishing |
| `MQTT_REFRESH` | `300` | Sensor read/publish interval (seconds) |
| `DB_USE_SQL` | `False` | Enable MySQL database storage (`True` or `False`) |
| `DB_SERVER` | Empty | MySQL server hostname/IP |
| `DB_NAME` | Empty | MySQL database name |
| `DB_USERNAME` | Empty | MySQL username |
| `DB_PASSWORD` | Empty | MySQL password |
| `CAL_TEMPERATURE` | `0.0` | Temperature calibration offset (°C) |
| `CAL_PRESSURE` | `0.0` | Pressure calibration offset (hPa) |
| `CAL_HUMIDITY` | `0.0` | Humidity calibration offset (%) |
| `CAL_LUX` | `0.0` | Light intensity calibration offset (lux) |

### MQTT Broker Configuration

The `MQTT_BROKERS` variable must be a jsonpickle-encoded string containing broker connection details:

**Single Broker:**
```
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.example.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]
```

**Multiple Brokers:**
```
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt1.local", "brokerport": 1883, "brokerusername": "user1", "brokerpassword": "pass1"}, {"py/object": "__main__.broker", "brokerfqdn": "mqtt2.local", "brokerport": 1883, "brokerusername": "user2", "brokerpassword": "pass2"}]
```

**With TLS (port 8883):**
```
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.example.local", "brokerport": 8883, "brokerusername": "user", "brokerpassword": "pass"}]
```

## Hardware Access

The container requires access to I2C devices for sensor communication.

### Raspberry Pi I2C Setup

1. **Privileged Mode + Device Mapping** (Recommended for docker-compose):
```yaml
privileged: true
devices:
  - /dev/i2c-1:/dev/i2c-1
```

2. **Host Network Mode** (Alternative):
```yaml
network_mode: host
devices:
  - /dev/i2c-1:/dev/i2c-1
```

3. **Docker CLI**:
```bash
docker run --privileged --device /dev/i2c-1:/dev/i2c-1 ...
```

## Database Integration (Optional)

To enable MySQL data logging:

1. Set `DB_USE_SQL=True`
2. Configure database connection variables
3. Ensure MySQL table exists:

```sql
CREATE TABLE Readings (
    ReadingID INT AUTO_INCREMENT PRIMARY KEY,
    ReadingTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Temperature FLOAT NOT NULL,
    Pressure FLOAT NOT NULL,
    Humidity FLOAT NOT NULL,
    Lux FLOAT,
    AmbientLux FLOAT
);
```

Or use `docker-compose.yml` with included MySQL service (uncommented).

## Calibration

Adjust sensor readings with per-sensor calibration offsets:

```bash
docker run -d \
  --device /dev/i2c-1:/dev/i2c-1 \
  -e CAL_TEMPERATURE=2.5 \
  -e CAL_PRESSURE=-5.0 \
  -e CAL_HUMIDITY=1.0 \
  -e CAL_LUX=100 \
  weatherpi:latest
```

## Troubleshooting

### Container fails with I2C errors
- Verify `--privileged` flag is set
- Check `/dev/i2c-1` exists on host: `ls -la /dev/i2c-1`
- Ensure I2C is enabled on Raspberry Pi: `raspi-config` → Interface Options → I2C

### MQTT connection fails
- Verify broker hostname and port are correct
- Check network connectivity: `docker exec weatherpi ping mqtt.example.local`
- Verify credentials
- Check broker logs for authentication failures

### No sensor readings
- Verify sensors are connected to I2C bus
- Test with `i2cdetect -y 1` on host
- Check logs: `docker logs weatherpi`

### Fallback to Config File

If environment variables are not set, the app falls back to `readings.ini`:

```bash
docker run -v /path/to/readings.ini:/app/readings.ini weatherpi:latest python readings.py -c /app/readings.ini
```

## Building for Different Architectures

```bash
# For Raspberry Pi (ARM)
docker buildx build --platform linux/arm/v7 -t weatherpi:latest .

# For ARM64 (Raspberry Pi 4)
docker buildx build --platform linux/arm64 -t weatherpi:latest .

# For x86_64 (Testing on desktop)
docker buildx build --platform linux/amd64 -t weatherpi:latest .
```

## Logs

View container logs:
```bash
docker logs weatherpi
docker logs -f weatherpi          # Follow logs
docker logs --tail 50 weatherpi   # Last 50 lines
```

Or with docker-compose:
```bash
docker-compose logs weatherpi
docker-compose logs -f weatherpi
```

## Graceful Shutdown

The application implements proper signal handling for clean shutdown. When stopping the container:

```bash
# Docker Compose (30 second grace period)
docker-compose stop weatherpi

# Docker (default 10 second timeout)
docker stop weatherpi

# Docker with explicit timeout
docker stop -t 30 weatherpi
```

The `docker-compose.yml` is configured with `stop_grace_period: 30s` to allow:
- Completion of the current sensor reading cycle
- Clean disconnection from MQTT brokers
- Proper closing of database connections
- Logging of shutdown progress

**Important:** Use `docker-compose stop` or `docker stop`, not `docker-compose kill` or `docker kill`, to ensure graceful shutdown.

## Production Recommendations

1. **Use a reverse proxy** for MQTT if exposing remotely
2. **Secure credentials** with Docker secrets or a secrets management system
3. **Enable log rotation** to prevent disk space issues
4. **Use `restart: unless-stopped`** for automatic recovery
5. **Monitor container health** with healthchecks (add to docker-compose.yml if needed)
6. **Regularly update** the base Python image and dependencies
7. **Always use graceful shutdown** (`docker-compose stop`, not `kill`) to ensure clean connection termination
8. **Monitor shutdown logs** to verify clean disconnection from MQTT and database resources
