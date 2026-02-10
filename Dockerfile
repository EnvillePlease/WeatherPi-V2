# Use Python 3.12 on Raspberry Pi OS or Debian 12 (Bookworm)
FROM python:3.12-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies for I2C access and sensors
RUN apt-get update && apt-get install -y \
    i2c-tools \
    libi2c-dev \
    gcc \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY CNSoft.WeatherPi.Readings.V2/ .

# Create a non-root user (optional, but recommended)
# Note: For I2C access, the user may need to be in the 'i2c' group
# For now, keeping as root for simplicity with I2C access
# RUN useradd -m -u 1000 weatherpi
# USER weatherpi

# Optional: Copy sample config for fallback (if env vars not set)
COPY CNSoft.WeatherPi.Readings.V2/readings.ini.sample /app/readings.ini.sample

# Labels for metadata
LABEL maintainer="WeatherPi V2" \
      description="WeatherPi Sensor Readings Publisher for MQTT and MySQL" \
      version="2.0"

# Health check (basic - checks if process is running)
# Note: This is a simple check; you may want to enhance it
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD ps aux | grep "[p]ython readings.py" || exit 1

# Run the application with unbuffered output for proper logging
CMD ["python", "-u", "readings.py"]
