import time
from influxdb import InfluxDBClient


class InfluxService:
    """Service for writing temperature data to InfluxDB."""

    def __init__(self, host, port, database, username=None, password=None):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
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

    def is_connected(self):
        """Check if connected to InfluxDB."""
        if self.client is None:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    def write_temperature(self, sensor_id, temperature):
        """Write a single temperature reading to InfluxDB."""
        if not self.client:
            self.connect()

        point = {
            "measurement": "anipills",
            "tags": {
                "sensor_id": f"sensor_{sensor_id}"
            },
            "fields": {
                "temperature": float(temperature)
            },
            "time": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }

        return self.client.write_points([point])

    def write_temperatures(self, readings):
        """Write multiple temperature readings to InfluxDB.

        Args:
            readings: List of dicts with 'sensor_id' and 'temperature' keys
        """
        if not readings:
            return False

        if not self.client:
            self.connect()

        timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

        points = []
        for reading in readings:
            if reading.get('valid', True) and reading.get('temperature') is not None:
                points.append({
                    "measurement": "anipills",
                    "tags": {
                        "sensor_id": f"sensor_{reading['sensor_id']}"
                    },
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

        query = f'SELECT * FROM anipills ORDER BY time DESC LIMIT {limit}'
        result = self.client.query(query)
        return list(result.get_points())
