#!/usr/bin/env python3
from smbus2 import SMBus
from bme280 import BME280
from bh1745 import BH1745
import mysql.connector
import time
import configparser
import argparse
import os
import sys
import paho.mqtt.client as mqtt_client
import random
import socket
import json
import jsonpickle
import ssl
import logging
import math
from typing import Optional, List, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

"""weatherpi readings publisher

This module reads sensors (BME280 for temperature/pressure/humidity
and BH1745 for colour/lux), optionally stores historic readings in a
MySQL database, and publishes the latest values to one or more MQTT
brokers as configured in `readings.ini` or Docker environment variables.

Configuration can be provided via:
- Config file: `readings.ini` (set with -c /path/to/readings.ini)
- Environment variables: MQTT_BROKERS, MQTT_TOPIC, MQTT_REFRESH, DB_*, CAL_* variables

Usage: `python readings.py [-c /path/to/readings.ini]`.
Environment variables take precedence over config file settings.
"""

# Custom object to hold broker details
class broker:
    """Simple container for MQTT broker connection details.

    Attributes:
        brokerfqdn (str): FQDN or IP of the broker.
        brokerport (int): TCP port of the broker (e.g. 1883 or 8883).
        brokerusername (str): Username for broker authentication.
        brokerpassword (str): Password for broker authentication.
    """
    brokerfqdn: str
    brokerport: int
    brokerusername: str
    brokerpassword: str

    def __init__(self, brokerfqdn: str, brokerport: int, brokerusername: str, brokerpassword: str) -> None:
        self.brokerfqdn = brokerfqdn
        self.brokerport = brokerport
        self.brokerusername = brokerusername
        self.brokerpassword = brokerpassword

# Initialise the BME280 (temperature, pressure, humidity)
bus = SMBus(1)
bme280 = BME280(i2c_dev=bus)

# Initialise the BH1745 (colour and lux sensor)
bh1745 = BH1745()
bh1745.setup()

# Parse command line for optional config file
parser = argparse.ArgumentParser(description='Publish sensor readings to MQTT/SQL')
parser.add_argument('-c', '--configfile', help='Path to configuration file', dest='configfile')
args = parser.parse_args()

# Determine default config path: readings.ini in the same directory as this script
script_dir = os.path.dirname(os.path.realpath(__file__))
default_config = os.path.join(script_dir, 'readings.ini')

config_path = args.configfile if args.configfile else default_config

# Function to load configuration from environment variables or config file
def load_config():
    """Load configuration from environment variables with fallback to config file.
    
    Environment variables override config file settings. This allows Docker containers
    to pass configuration via env vars without requiring a config file.
    """
    config = configparser.ConfigParser()
    config_file_exists = os.path.isfile(config_path)
    
    if config_file_exists:
        config.read(config_path)
        logging.info("Config file loaded: %s", config_path)
    else:
        logging.warning("Config file not found: %s. Using environment variables.", config_path)
    
    # Load MQTT broker configuration
    brokers_data = os.environ.get('MQTT_BROKERS')
    if brokers_data:
        try:
            brokers = jsonpickle.decode(brokers_data)
            logging.info("MQTT brokers loaded from env: MQTT_BROKERS")
        except Exception as e:
            logging.error("Failed to parse MQTT_BROKERS env var: %s", e)
            if config_file_exists:
                brokers = jsonpickle.decode(config.get('broker', 'brokers'))
            else:
                raise ValueError("MQTT_BROKERS env var is invalid and no config file found")
    elif config_file_exists:
        brokers = jsonpickle.decode(config.get('broker', 'brokers'))
    else:
        raise ValueError("MQTT_BROKERS env var not set and no config file found")
    
    # Load MQTT topic
    topic = os.environ.get('MQTT_TOPIC', config.get('broker', 'topic', fallback='Weatherstation/'))
    
    # Load refresh interval
    refresh_str = os.environ.get('MQTT_REFRESH', config.get('broker', 'refresh', fallback='300'))
    refresh_interval = int(refresh_str)
    
    # Load database configuration
    usesql = os.environ.get('DB_USE_SQL', config.get('db', 'usesql', fallback='False')).lower() in ('true', '1', 'yes')
    dbserver = os.environ.get('DB_SERVER', config.get('db', 'server', fallback=''))
    dbname = os.environ.get('DB_NAME', config.get('db', 'database', fallback=''))
    dbusername = os.environ.get('DB_USERNAME', config.get('db', 'username', fallback=''))
    dbpassword = os.environ.get('DB_PASSWORD', config.get('db', 'password', fallback=''))
    
    # Load calibration offsets
    cal_temp = float(os.environ.get('CAL_TEMPERATURE', config.get('calibration', 'temperature', fallback='0.0')))
    cal_pressure = float(os.environ.get('CAL_PRESSURE', config.get('calibration', 'pressure', fallback='0.0')))
    cal_humidity = float(os.environ.get('CAL_HUMIDITY', config.get('calibration', 'humidity', fallback='0.0')))
    cal_lux = float(os.environ.get('CAL_LUX', config.get('calibration', 'lux', fallback='0.0')))
    
    return brokers, topic, refresh_interval, usesql, dbserver, dbname, dbusername, dbpassword, cal_temp, cal_pressure, cal_humidity, cal_lux

# Load configuration
brokers, topic, refresh_interval, usesql, dbserver, dbname, dbusername, dbpassword, cal_temp, cal_pressure, cal_humidity, cal_lux = load_config()
clients: List[mqtt_client.Client] = []

# Generate a unique client ID
client_id: str = f'{socket.gethostname()}_s-{random.randint(0, 1000)}'
# The ID above combines the host name and a small random suffix to
# reduce the chance of client ID collisions when multiple instances run.

# Get the initial reading as it is always wrong.
# Perform an initial (warm-up) read from sensors. These initial values
# are known to be unreliable for these devices, so we discard them after
# a short delay. Keeping the call here ensures later readings are stable.
temperature: float = bme280.get_temperature()
pressure: float = bme280.get_pressure()
humidity: float = bme280.get_humidity()
r, g, b, c = bh1745.get_rgbc_raw()
time.sleep(1)

def connect_mqtt(brokerep: broker) -> mqtt_client.Client:
    """Create and connect an MQTT client for the given broker.

    brokerep should be an instance of `broker` containing connection
    details. Returns a started `paho.mqtt.client.Client` instance
    (network loop started) or a client with the loop started even if
    the initial connect failed.
    """
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logging.info("Connected to MQTT Broker %s", brokerep.brokerfqdn)
        else:
            logging.error("Failed to connect to MQTT Broker %s, return code %s", brokerep.brokerfqdn, rc)

    client_id_instance: str = client_id + brokerep.brokerfqdn
    
    # Prefer CallbackAPIVersion.VERSION1 if the installed paho-mqtt supports it
    # (preserves older callback API compatibility). Fall back to the modern
    # constructor if it's not available in this environment.
    cap = getattr(mqtt_client, 'CallbackAPIVersion', None)
    if cap is not None:
        try:
            client = mqtt_client.Client(cap.VERSION1, client_id_instance)
        except Exception:
            client = mqtt_client.Client(client_id=client_id_instance, protocol=mqtt_client.MQTTv311)
    else:
        client = mqtt_client.Client(client_id=client_id_instance, protocol=mqtt_client.MQTTv311)

    # Set up TLS if port 8883 is used
    if brokerep.brokerport == 8883:
        client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)
        client.tls_insecure_set(True)

    client.username_pw_set(brokerep.brokerusername, brokerep.brokerpassword)
    client.on_connect = on_connect
    try:
        client.connect(brokerep.brokerfqdn, brokerep.brokerport)
        # Start network loop in background so client maintains connection and can reconnect
        client.loop_start()
        time.sleep(1)
        logging.info("MQTT client loop started for %s", brokerep.brokerfqdn)
    except Exception as e:
        logging.error("Failed to connect/start MQTT client for %s: %s", brokerep.brokerfqdn, e)
        # Start loop anyway to allow client to attempt background reconnects if possible
        try:
            client.loop_start()
        except Exception:
            pass
    return client

def connect_db() -> Optional[Any]:
    """Connect to the MySQL database and return a connection object.

    Returns a `mysql.connector` connection on success or `None` on
    failure. Caller should check the result before using it.
    """
    try:
        conn = mysql.connector.connect(
            host=dbserver,
            database=dbname,
            user=dbusername,
            password=dbpassword,
            autocommit=False,
        )
        logging.info("Connected to DB %s", dbname)
        return conn
    except mysql.connector.Error as e:
        logging.error("Database connection failed: %s", e)
        return None

def publish_sensor(clients: List[mqtt_client.Client], conn: Optional[mysql.connector.connection.MySQLConnection]) -> None:
    """Main sensor read loop.

    This function runs an infinite loop that reads sensor values,
    applies calibration offsets from the config file, computes derived
    metrics (lux, dew point, corrected humidity), optionally inserts
    the readings into the configured SQL database, and publishes a
    JSON payload to the configured MQTT topic for each connected
    client.
    """
    cursor = None
    if usesql:
        if conn is not None:
            try:
                cursor = conn.cursor()
            except Exception as e:
                logging.error("Failed to create DB cursor at startup: %s", e)
                conn = None
        else:
            logging.warning("usesql=True but no DB connection provided at startup")

    while True:
        try:
            # Obtain readings from the sensors
            temperature = bme280.get_temperature()
            pressure = bme280.get_pressure()
            humidity = bme280.get_humidity()
            _, _, _, c = bh1745.get_rgbc_raw()

            # Apply per-sensor calibration offsets (configurable in readings.ini)
            try:
                temperature = temperature + cal_temp
            except Exception:
                logging.exception("Failed to apply temperature calibration")
            try:
                pressure = pressure + cal_pressure
            except Exception:
                logging.exception("Failed to apply pressure calibration")
            try:
                humidity = humidity + cal_humidity
            except Exception:
                logging.exception("Failed to apply humidity calibration")
            try:
                # Apply lux calibration to the raw c channel before conversion
                c = c + cal_lux
            except Exception:
                logging.exception("Failed to apply lux calibration")

            # Calculate lux from colour sensor data
            lx_tmp = c / 1.638375
            lx = min(max(round(lx_tmp, -2), 0), 40000)
            ambient_lux = min(lx, 10000)

            # Calculate dew point using the Magnus formula for better
            # accuracy across a wider temperature/humidity range.
            try:
                # Magnus constants for water vapor over liquid water
                a: float = 17.27
                b: float = 237.7
                # Protect against invalid humidity values (<=0)
                rh_fraction: float = max(min(humidity / 100.0, 1.0), 1e-6)
                gamma = (a * temperature) / (b + temperature) + math.log(rh_fraction)
                dewpoint = (b * gamma) / (a - gamma)
            except Exception:
                # Fallback to the original simple approximation if something goes wrong
                logging.exception("Magnus dew point calculation failed; using fallback")
                dewpoint = temperature - ((100 - humidity) / 5)

            corrected_humidity = 100 - (5 * (temperature - dewpoint))

            # Keep numeric values and round when publishing/storing
            temperature_r: float = round(temperature, 1)
            pressure_r: float = round(pressure, 1)
            humidity_r: float = round(humidity, 1)
            lx_r: float = round(lx, 1)
            ambient_lux_r: float = round(ambient_lux, 1)
            dewpoint_r: float = round(dewpoint, 1)
            corrected_humidity_r: float = round(corrected_humidity, 1)

            # Check for a bad reading from the sensors (sensor's known invalid startup values)
            if not (temperature_r == 22.0 and humidity_r == 82.3 and pressure_r == 684.3):
                # Insert the readings into the SQL database
                if usesql:
                    # Ensure DB connection is alive, try reconnect if not
                    if conn is None or not (getattr(conn, 'is_connected', lambda: True)() if conn is not None else False):
                        logging.warning("DB connection lost or not present; attempting reconnect")
                        conn = connect_db()
                        if conn is not None:
                            try:
                                cursor = conn.cursor()
                            except Exception as e:
                                logging.error("Failed to create DB cursor after reconnect: %s", e)
                                cursor = None

                    if conn is not None and cursor is not None:
                        try:
                            cursor.execute(
                                "INSERT INTO Readings (Humidity, Pressure, Temperature, Lux, AmbientLux) VALUES (%s, %s, %s, %s, %s)",
                                (humidity_r, pressure_r, temperature_r, lx_r, ambient_lux_r)
                            )
                            conn.commit()
                        except mysql.connector.Error as e:
                            logging.error("Database insert failed: %s", e)
                            try:
                                conn.close()
                            except Exception:
                                pass
                            conn = None
                            cursor = None

                # Prepare the MQTT payload
                mqtt_payload = json.dumps({
                    "temperature": temperature_r,
                    "pressure": pressure_r,
                    "humidity": humidity_r,
                    "dew_point": dewpoint_r,
                    "lx": lx_r,
                    "ambient_lux": ambient_lux_r
                })

                # Publish the readings to each MQTT server
                for client in clients:
                    try:
                        result = client.publish(topic + "WeatherData", mqtt_payload)
                        status = result[0]
                        if status == 0:
                            logging.debug("Published message to %s", topic)
                        else:
                            logging.warning("Client failed to send message to topic %s (status=%s)", topic, status)
                    except Exception as e:
                        logging.exception("Client failed to send message to topic %s: %s", topic, e)
                        # Attempt to reconnect this client
                        try:
                            client.reconnect()
                        except Exception:
                            pass
            else:
                logging.warning("Bad sensor reading detected: temp=%s hum=%s pres=%s", temperature_r, humidity_r, pressure_r)

        except Exception:
            logging.exception("Unexpected error in sensor loop; continuing")

        # Wait for the configured interval before repeating
        time.sleep(refresh_interval)

def run():
    """Application entry point.

    Sets up MQTT clients and DB connection (if enabled), starts the
    MQTT network loops, then enters the sensor publishing loop. Ensures
    graceful shutdown of clients and DB on exit.
    """
    for brokerep in brokers:
        client = connect_mqtt(brokerep)
        clients.append(client)

    conn = None
    if usesql:
        conn = connect_db()

    for client in clients:
        client.loop_start()

    try:
        publish_sensor(clients, conn)
    finally:
        # Graceful shutdown: stop MQTT loops and close DB connection
        for client in clients:
            try:
                client.loop_stop()
            except Exception:
                pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

if __name__ == '__main__':
    run()
