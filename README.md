# WeatherPi V2

A Raspberry Pi-based weather station that reads environmental sensors via I2C and publishes data to MQTT brokers with optional MySQL database storage.

## Features

✅ **Multi-sensor Support**: Temperature, Pressure, Humidity, and Light (Lux) readings  
✅ **MQTT Integration**: Publish to single or multiple MQTT brokers  
✅ **Database Logging**: Optional MySQL storage for historical data  
✅ **Sensor Calibration**: Per-sensor calibration offsets  
✅ **Docker Ready**: Fully containerized with Docker and Docker Compose support  
✅ **Flexible Configuration**: Environment variables or config file (`readings.ini`)  
✅ **Backward Compatible**: Supports existing config file deployments  
✅ **Hardware Healthcheck**: Built-in I2C sensor verification  
✅ **Graceful Shutdown**: Proper signal handling for clean container stops  

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/EnvillePlease/WeatherPi-V2.git
cd WeatherPi-V2

# Copy and edit environment file
cp .env.sample .env
# Edit .env with your MQTT broker details

# Start the container
docker-compose up -d

# View logs
docker-compose logs -f weatherpi

# Stop the container gracefully (waits up to 30s for clean shutdown)
docker-compose stop

# Stop and remove the container
docker-compose down
```

### Option 2: Docker Run

```bash
# Build the image
docker build -t weatherpi:latest .

# Run with environment variables
docker run -d \
  --name weatherpi \
  --privileged \
  --device /dev/i2c-1:/dev/i2c-1 \
  -e MQTT_BROKERS='[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]' \
  -e MQTT_TOPIC="Weatherstation/" \
  -e MQTT_REFRESH=300 \
  weatherpi:latest
```

### Option 3: Traditional Python (Non-Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and edit configuration
cp CNSoft.WeatherPi.Readings.V2/readings.ini.sample CNSoft.WeatherPi.Readings.V2/readings.ini
# Edit readings.ini with your settings

# Run the application
python CNSoft.WeatherPi.Readings.V2/readings.py -c CNSoft.WeatherPi.Readings.V2/readings.ini
```

## Configuration

### Environment Variables (Docker)

Configuration via environment variables is ideal for Docker deployments. See the full reference below or check `.env.sample` for a complete template.

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MQTT_BROKERS` | JSON-formatted broker configuration | See examples below |

#### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_TOPIC` | `Weatherstation/` | MQTT topic prefix |
| `MQTT_REFRESH` | `300` | Read interval (seconds) |
| `DB_USE_SQL` | `False` | Enable MySQL storage |
| `DB_SERVER` | - | MySQL hostname/IP |
| `DB_NAME` | - | MySQL database name |
| `DB_USERNAME` | - | MySQL username |
| `DB_PASSWORD` | - | MySQL password |
| `CAL_TEMPERATURE` | `0.0` | Temperature offset (°C) |
| `CAL_PRESSURE` | `0.0` | Pressure offset (hPa) |
| `CAL_HUMIDITY` | `0.0` | Humidity offset (%) |
| `CAL_LUX` | `0.0` | Light offset (lux) |

#### MQTT Broker Examples

**Single Broker:**
```bash
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]
```

**Multiple Brokers:**
```bash
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt1.local", "brokerport": 1883, "brokerusername": "user1", "brokerpassword": "pass1"}, {"py/object": "__main__.broker", "brokerfqdn": "mqtt2.local", "brokerport": 1883, "brokerusername": "user2", "brokerpassword": "pass2"}]
```

**With TLS (port 8883):**
```bash
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.example.com", "brokerport": 8883, "brokerusername": "user", "brokerpassword": "pass"}]
```

### Config File (Non-Docker)

When running without Docker, edit `readings.ini`:

```ini
[broker]
brokers = [{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]
topic = Weatherstation/
refresh = 300

[database]
use_sql = False
server = 
name = 
username = 
password = 

[calibration]
temperature = 0.0
pressure = 0.0
humidity = 0.0
lux = 0.0
```

## Hardware Requirements

- **Raspberry Pi** with I2C enabled (any model with GPIO)
- **I2C Sensors**: Compatible temperature, pressure, humidity, and light sensors
- **Network**: Connection to MQTT broker (and MySQL if database enabled)

### Enable I2C on Raspberry Pi

```bash
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable
sudo reboot
```

Verify I2C is working:
```bash
i2cdetect -y 1
```

## Database Setup (Optional)

To enable MySQL data logging:

1. Create database and table:

```sql
CREATE DATABASE weatherpi;
USE weatherpi;

CREATE TABLE Readings (
    ReadingID INT AUTO_INCREMENT PRIMARY KEY,
    ReadingTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Temperature FLOAT NOT NULL,
    Pressure FLOAT NOT NULL,
    Humidity FLOAT NOT NULL,
    Lux FLOAT,
    AmbientLux FLOAT
);

CREATE USER 'weatherpi_user'@'%' IDENTIFIED BY 'secure_password';
GRANT INSERT, SELECT ON weatherpi.Readings TO 'weatherpi_user'@'%';
FLUSH PRIVILEGES;
```

2. Configure database settings (environment variables or `readings.ini`)

3. Set `DB_USE_SQL=True` (or `use_sql = True` in config file)

## Sensor Calibration

Adjust sensor readings with calibration offsets. The offset value is **added** to the raw sensor reading.

**Examples:**
- If sensor reads 2°C too high: `CAL_TEMPERATURE=-2.0`
- If sensor reads 5 hPa too low: `CAL_PRESSURE=5.0`
- If humidity is 1% too high: `CAL_HUMIDITY=-1.0`

## Troubleshooting

### Container Fails with I2C Errors

**Problem:** Cannot access I2C devices  
**Solutions:**
- Verify `--privileged` flag is set
- Check `/dev/i2c-1` exists: `ls -la /dev/i2c-1`
- Enable I2C on Raspberry Pi: `raspi-config` → Interface Options → I2C
- Verify sensors are detected: `i2cdetect -y 1`

### MQTT Connection Fails

**Problem:** Cannot connect to MQTT broker  
**Solutions:**
- Verify broker hostname is correct and reachable
- Check network connectivity: `docker exec weatherpi ping mqtt.local`
- Verify broker credentials
- Check broker logs for authentication failures
- Try TLS port (8883) if broker requires encryption

### No Sensor Readings

**Problem:** Sensors not detected or returning errors  
**Solutions:**
- Verify sensors are properly connected to I2C bus
- Test with `i2cdetect -y 1` on the host
- Check container logs: `docker logs weatherpi`
- Ensure correct I2C address in code
- Check sensor power supply

### Database Connection Fails

**Problem:** Cannot connect to MySQL  
**Solutions:**
- Verify MySQL server is running and reachable
- Check database credentials
- Ensure database and table exist
- Verify user has proper permissions
- Check MySQL allows remote connections (if not localhost)

## Viewing Logs

**Docker:**
```bash
docker logs weatherpi
docker logs -f weatherpi          # Follow logs
docker logs --tail 50 weatherpi   # Last 50 lines
```

**Docker Compose:**
```bash
docker-compose logs weatherpi
docker-compose logs -f weatherpi
```

## Stopping the Service

The application handles shutdown signals gracefully, ensuring proper cleanup of MQTT connections and database resources.

**Docker Compose:**
```bash
docker-compose stop     # Graceful stop (30s timeout)
docker-compose down     # Stop and remove container
```

**Docker:**
```bash
docker stop weatherpi   # Graceful stop (30s timeout)
docker stop -t 30 weatherpi  # Explicit 30s timeout
```

During shutdown, the application:
- Completes the current sensor reading cycle
- Disconnects from all MQTT brokers cleanly
- Closes database connections properly
- Logs shutdown progress for monitoring

## Migration from Config File to Environment Variables

To migrate from `readings.ini` to environment variables:

1. Extract values from your existing `readings.ini`
2. Copy `.env.sample` to `.env`
3. Update `.env` with values from `readings.ini`
4. Use docker-compose to deploy

**Example conversion:**

`readings.ini`:
```ini
[broker]
brokers = [{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]
topic = Weatherstation/
refresh = 300
```

`.env`:
```bash
MQTT_BROKERS=[{"py/object": "__main__.broker", "brokerfqdn": "mqtt.local", "brokerport": 1883, "brokerusername": "user", "brokerpassword": "pass"}]
MQTT_TOPIC=Weatherstation/
MQTT_REFRESH=300
```

## Building for Different Architectures

```bash
# For Raspberry Pi (ARM v7)
docker buildx build --platform linux/arm/v7 -t weatherpi:latest .

# For ARM64 (Raspberry Pi 4/5)
docker buildx build --platform linux/arm64 -t weatherpi:latest .

# For x86_64 (Testing on desktop)
docker buildx build --platform linux/amd64 -t weatherpi:latest .
```

## Production Recommendations

1. **Use Docker Compose** for easier management and updates
2. **Secure credentials** with `.env` file (never commit to Git)
3. **Enable log rotation** to prevent disk space issues
4. **Use `restart: unless-stopped`** for automatic recovery after reboot
5. **Monitor container health** with built-in healthchecks
6. **Regular backups** of database and `.env` configuration
7. **Update regularly** to get latest security patches and features
8. **Use reverse proxy** for MQTT if exposing remotely
9. **Allow graceful shutdown** with `docker-compose stop` (not `docker-compose kill`) to ensure clean connection termination

## Project Structure

```
WeatherPi-V2/
├── CNSoft.WeatherPi.Readings.V2/
│   ├── readings.py              # Main application
│   ├── readings.ini.sample      # Sample config file
│   └── CNSoft.WeatherPi.Readings.pyproj
├── Dockerfile                   # Container build instructions
├── docker-compose.yml           # Container orchestration
├── requirements.txt             # Python dependencies
├── .env.sample                  # Environment variable template
├── DOCKER_CONVERSION.md         # Docker migration notes
├── DOCKER_SETUP.md              # Detailed Docker guide
├── ENV_VARS_REFERENCE.md        # Environment variable reference
└── README.md                    # This file
```

## Additional Documentation

- **[DOCKER_SETUP.md](DOCKER_SETUP.md)** - Complete Docker deployment guide
- **[ENV_VARS_REFERENCE.md](ENV_VARS_REFERENCE.md)** - Environment variables quick reference
- **[DOCKER_CONVERSION.md](DOCKER_CONVERSION.md)** - Migration and conversion notes

## License

See project repository for license information.

## Support

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/EnvillePlease/WeatherPi-V2).
