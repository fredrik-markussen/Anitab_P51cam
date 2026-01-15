import json
import os
import threading
import time
from flask import Flask, Response, render_template, jsonify, request

from services.camera import CameraService
from services.ocr import OCRService
from services.influx import InfluxService

app = Flask(__name__)

# Configuration file path
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config', 'rois.json')

# Global state
config = {}
camera_service = None
ocr_service = None
influx_service = None
processing_thread = None
processing_running = False
last_readings = []
last_reading_time = None


def load_config():
    """Load configuration from JSON file."""
    global config
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    return config


def save_config():
    """Save configuration to JSON file."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def init_services():
    """Initialize all services with current config.

    Per FSD 6.1 Startup Sequence:
    1. Load configuration
    2. Initialize camera service
    3. Initialize OCR service
    4. Initialize InfluxDB service
    """
    global camera_service, ocr_service, influx_service

    load_config()

    # Initialize camera service (per FSD 9.2: reconnect_interval_seconds)
    reconnect_interval = config.get('reconnect_interval_seconds', 30)
    camera_service = CameraService(config['stream_url'], reconnect_interval_seconds=reconnect_interval)

    # Initialize OCR service with settings
    temp_range = config.get('temperature_range', {'min': 5, 'max': 37})
    ocr_settings = config.get('ocr_settings', {})
    ocr_service = OCRService(
        temp_min=temp_range['min'],
        temp_max=temp_range['max'],
        ocr_settings=ocr_settings
    )

    # Initialize InfluxDB service (per FSD 7.1: camera_id tag)
    influx_config = config['influxdb']
    camera_id = config.get('camera_id', 'cam_1')
    influx_service = InfluxService(
        host=influx_config['host'],
        port=influx_config['port'],
        database=influx_config['database'],
        username=influx_config.get('username'),
        password=influx_config.get('password'),
        measurement=influx_config.get('measurement', 'temperature'),
        camera_id=camera_id
    )


def processing_loop():
    """Background loop for OCR processing and data logging."""
    global processing_running, last_readings, last_reading_time

    while processing_running:
        try:
            # Get current frame
            frame = camera_service.get_frame()
            if frame is not None:
                # Extract temperatures
                readings = ocr_service.extract_all_temperatures(frame, config['rois'])
                last_readings = readings
                last_reading_time = time.strftime('%Y-%m-%d %H:%M:%S')

                # Write valid readings to InfluxDB
                valid_readings = [r for r in readings if r.get('valid', False)]
                if valid_readings:
                    try:
                        influx_service.write_temperatures(valid_readings)
                        print(f"Wrote {len(valid_readings)} readings to InfluxDB")
                    except Exception as e:
                        print(f"InfluxDB write error: {e}")

                # Log to console
                for r in readings:
                    status = "OK" if r.get('valid') else f"SKIP ({r.get('reason', 'unknown')})"
                    print(f"Sensor {r['sensor_id']}: {r.get('temperature', 'N/A')} - {status}")

        except Exception as e:
            print(f"Processing error: {e}")

        # Sleep for configured interval
        interval_seconds = config.get('processing_interval_minutes', 15) * 60
        # Check every second if we should stop
        for _ in range(interval_seconds):
            if not processing_running:
                break
            time.sleep(1)


# Routes
@app.route('/')
def index():
    """Main web UI page."""
    return render_template('index.html')


@app.route('/stream')
def stream():
    """Video stream endpoint."""
    def generate():
        while True:
            jpeg = camera_service.get_jpeg()
            if jpeg:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
            time.sleep(0.033)  # ~30 fps

    return Response(generate(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/stream/overlay')
def stream_overlay():
    """Video stream with ROI overlay."""
    def generate():
        while True:
            jpeg = camera_service.get_jpeg_with_rois(config['rois'])
            if jpeg:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
            time.sleep(0.033)  # ~30 fps

    return Response(generate(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/rois', methods=['GET'])
def get_rois():
    """Get current ROI configuration."""
    return jsonify(config.get('rois', []))


@app.route('/api/rois', methods=['POST'])
def update_rois():
    """Update ROI configuration."""
    global config
    new_rois = request.json
    if not isinstance(new_rois, list):
        return jsonify({'error': 'Invalid ROI data'}), 400

    config['rois'] = new_rois
    save_config()
    return jsonify({'success': True, 'rois': config['rois']})


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get full configuration (excluding sensitive data)."""
    safe_config = {
        'stream_url': config.get('stream_url'),
        'processing_interval_minutes': config.get('processing_interval_minutes', 15),
        'temperature_range': config.get('temperature_range', {'min': 5, 'max': 37}),
        'rois': config.get('rois', [])
    }
    return jsonify(safe_config)


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration settings."""
    global config
    updates = request.json

    # Update allowed fields
    if 'processing_interval_minutes' in updates:
        config['processing_interval_minutes'] = int(updates['processing_interval_minutes'])
    if 'temperature_range' in updates:
        config['temperature_range'] = updates['temperature_range']
    if 'stream_url' in updates:
        config['stream_url'] = updates['stream_url']
        # Restart camera with new URL
        camera_service.stop()
        camera_service.stream_url = config['stream_url']
        camera_service.start()

    save_config()
    return jsonify({'success': True})


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current system status and readings."""
    resolution = camera_service.get_resolution() if camera_service else None
    return jsonify({
        'camera_connected': camera_service.is_connected() if camera_service else False,
        'influx_connected': influx_service.is_connected() if influx_service else False,
        'processing_running': processing_running,
        'last_readings': last_readings,
        'last_reading_time': last_reading_time,
        'interval_minutes': config.get('processing_interval_minutes', 15),
        'video_resolution': resolution
    })


@app.route('/api/camera/reconnect', methods=['POST'])
def reconnect_camera():
    """Force reconnect to camera stream to pick up new settings."""
    global camera_service

    print("[Camera] Reconnecting to stream...")
    try:
        camera_service.stop()
        time.sleep(0.5)  # Brief pause before reconnecting
        camera_service.start()

        # Wait a moment for first frame
        time.sleep(1)
        resolution = camera_service.get_resolution()

        print(f"[Camera] Reconnected. Resolution: {resolution}")
        return jsonify({
            'success': True,
            'message': 'Camera reconnected',
            'resolution': resolution
        })
    except Exception as e:
        print(f"[Camera] Reconnect failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/start', methods=['POST'])
def start_processing():
    """Start the background processing loop."""
    global processing_thread, processing_running

    if processing_running:
        return jsonify({'error': 'Already running'}), 400

    processing_running = True
    processing_thread = threading.Thread(target=processing_loop, daemon=True)
    processing_thread.start()

    return jsonify({'success': True, 'message': 'Processing started'})


@app.route('/api/stop', methods=['POST'])
def stop_processing():
    """Stop the background processing loop."""
    global processing_running

    if not processing_running:
        return jsonify({'error': 'Not running'}), 400

    processing_running = False
    return jsonify({'success': True, 'message': 'Processing stopped'})


@app.route('/api/capture', methods=['POST'])
def capture_now():
    """Perform immediate OCR capture (for testing)."""
    global last_readings, last_reading_time

    frame = camera_service.get_frame()
    if frame is None:
        return jsonify({'error': 'No frame available'}), 500

    readings = ocr_service.extract_all_temperatures(frame, config['rois'])
    last_readings = readings
    last_reading_time = time.strftime('%Y-%m-%d %H:%M:%S')

    return jsonify({
        'success': True,
        'readings': readings,
        'timestamp': last_reading_time
    })


@app.route('/api/capture/debug', methods=['POST'])
def capture_debug():
    """Perform OCR capture with debug output including processed images."""
    global last_readings, last_reading_time

    frame = camera_service.get_frame()
    if frame is None:
        return jsonify({'error': 'No frame available'}), 500

    print(f"[Capture Debug] Using OCR settings: {ocr_service.ocr_settings}")

    readings = ocr_service.extract_all_temperatures_debug(frame, config['rois'])

    # Update last readings (without debug images for status polling)
    last_readings = [{k: v for k, v in r.items() if k != 'debug_images'} for r in readings]
    last_reading_time = time.strftime('%Y-%m-%d %H:%M:%S')

    return jsonify({
        'success': True,
        'readings': readings,
        'timestamp': last_reading_time
    })


# InfluxDB Configuration API
@app.route('/api/influxdb', methods=['GET'])
def get_influxdb_config():
    """Get InfluxDB configuration (excluding password)."""
    influx_config = config.get('influxdb', {})
    return jsonify({
        'host': influx_config.get('host', ''),
        'port': influx_config.get('port', 8086),
        'database': influx_config.get('database', ''),
        'measurement': influx_config.get('measurement', 'anipills'),
        'username': influx_config.get('username', '')
    })


@app.route('/api/influxdb', methods=['POST'])
def update_influxdb_config():
    """Update InfluxDB configuration."""
    global config, influx_service
    updates = request.json

    if 'influxdb' not in config:
        config['influxdb'] = {}

    # Update allowed fields
    for field in ['host', 'port', 'database', 'measurement', 'username']:
        if field in updates:
            config['influxdb'][field] = updates[field]

    # Only update password if explicitly provided (not empty)
    if updates.get('password'):
        config['influxdb']['password'] = updates['password']

    save_config()

    # Reconfigure service
    influx_service.reconfigure(
        host=config['influxdb'].get('host'),
        port=config['influxdb'].get('port'),
        database=config['influxdb'].get('database'),
        measurement=config['influxdb'].get('measurement', 'anipills'),
        username=config['influxdb'].get('username'),
        password=config['influxdb'].get('password')
    )

    return jsonify({'success': True, 'connected': influx_service.is_connected()})


@app.route('/api/influxdb/test', methods=['POST'])
def test_influxdb_connection():
    """Test InfluxDB connection with provided settings."""
    test_config = request.json or config.get('influxdb', {})

    test_service = InfluxService(
        host=test_config.get('host'),
        port=test_config.get('port', 8086),
        database=test_config.get('database'),
        measurement=test_config.get('measurement', 'anipills'),
        username=test_config.get('username'),
        password=test_config.get('password')
    )

    try:
        test_service.connect()
        connected = test_service.is_connected()
        test_service.disconnect()
        return jsonify({
            'success': connected,
            'message': 'Connection successful' if connected else 'Connection failed'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# OCR Settings API
@app.route('/api/ocr-settings', methods=['GET'])
def get_ocr_settings():
    """Get current OCR settings."""
    return jsonify({
        'temperature_range': config.get('temperature_range', {'min': 5, 'max': 37}),
        'ocr_settings': config.get('ocr_settings', {
            'clip_limit': 2.0,
            'tile_grid_size': 8,
            'block_size': 11,
            'c_constant': 2,
            'threshold_mode': 'simple',
            'threshold_value': 200,
            'use_clahe': False,
            'psm_mode': 6
        })
    })


@app.route('/api/ocr-settings', methods=['POST'])
def update_ocr_settings():
    """Update OCR settings."""
    global config, ocr_service
    updates = request.json

    print(f"[OCR Settings] Received update: {updates}")

    if 'temperature_range' in updates:
        config['temperature_range'] = updates['temperature_range']

    if 'ocr_settings' in updates:
        if 'ocr_settings' not in config:
            config['ocr_settings'] = {}
        config['ocr_settings'].update(updates['ocr_settings'])

        # Validate block_size is odd
        if config['ocr_settings'].get('block_size', 11) % 2 == 0:
            config['ocr_settings']['block_size'] += 1

    save_config()

    # Update OCR service
    ocr_service.update_settings(
        temp_min=config.get('temperature_range', {}).get('min'),
        temp_max=config.get('temperature_range', {}).get('max'),
        ocr_settings=config.get('ocr_settings')
    )

    print(f"[OCR Settings] Applied to service: {ocr_service.ocr_settings}")

    return jsonify({'success': True, 'applied_settings': ocr_service.ocr_settings})


def main():
    """Main entry point."""
    print("Initializing services...")
    init_services()

    print(f"Starting camera service: {config['stream_url']}")
    try:
        camera_service.start()
        print("Camera connected successfully")
    except ConnectionError as e:
        print(f"Warning: Camera connection failed: {e}")
        print("Camera will retry in background...")

    print("Connecting to InfluxDB...")
    try:
        influx_service.connect()
        print("InfluxDB connected successfully")
    except Exception as e:
        print(f"Warning: InfluxDB connection failed: {e}")

    print("Starting Flask server on port 8080...")
    app.run(host='0.0.0.0', port=8080, threaded=True)


if __name__ == '__main__':
    main()
