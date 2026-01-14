import time
from influxdb import InfluxDBClient


class InfluxService:
    """Service for writing temperature data to InfluxDB."""

    def __init__(self, host, port, database, username=None, password=None, measurement="anipills"):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.measurement = measurement
        self.client = None

    def connect(self):
        """Establish connection to InfluxDB."""
        self.client = InfluxDBClient(
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            database=self.database
        )

    def disconnect(self):
        """Close the InfluxDB connection."""
        if self.client:
            self.client.close()
            self.client = None

    def reconfigure(self, host=None, port=None, database=None, measurement=None, username=None, password=None):
        """Update configuration and reconnect."""
        if host is not None:
            self.host = host
        if port is not None:
            self.port = port
        if database is not None:
            self.database = database
        if measurement is not None:
            self.measurement = measurement
        if username is not None:
            self.username = username
        if password is not None:
            self.password = password
        self.disconnect()
        self.connect()

    def is_connected(self):
        """Check if connected to InfluxDB."""
        if self.client is None:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    def write_temperature(self, sensor_id, temperature, sensor_name=None):
        """Write a single temperature reading to InfluxDB."""
        if not self.client:
            self.connect()

        tags = {
            "sensor_id": f"sensor_{sensor_id}"
        }
        if sensor_name:
            tags["sensor_name"] = sensor_name

        point = {
            "measurement": self.measurement,
            "tags": tags,
            "fields": {
                "temperature": float(temperature)
            },
            "time": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }

        return self.client.write_points([point])

    def write_temperatures(self, readings):
        """Write multiple temperature readings to InfluxDB.

        Args:
            readings: List of dicts with 'sensor_id', 'temperature', and optional 'sensor_name' keys
        """
        if not readings:
            return False

        if not self.client:
            self.connect()

        timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        points = []
        for reading in readings:
            if reading.get('valid', True) and reading.get('temperature') is not None:
                tags = {
                    "sensor_id": f"sensor_{reading['sensor_id']}"
                }
                if reading.get('sensor_name'):
                    tags["sensor_name"] = reading['sensor_name']

                points.append({
                    "measurement": self.measurement,
                    "tags": tags,
                    "fields": {
                        "temperature": float(reading['temperature'])
                    },
                    "time": timestamp
                })

        if points:
            return self.client.write_points(points)
        return False

    def query_recent(self, limit=10):
        """Query recent temperature readings."""
        if not self.client:
            self.connect()

        query = f'SELECT * FROM "{self.measurement}" ORDER BY time DESC LIMIT {limit}'
        result = self.client.query(query)
        return list(result.get_points())
