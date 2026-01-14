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
    """Initialize all services with current config."""
    global camera_service, ocr_service, influx_service

    load_config()

    # Initialize camera service
    camera_service = CameraService(config['stream_url'])

    # Initialize OCR service
    temp_range = config.get('temperature_range', {'min': 5, 'max': 37})
    ocr_service = OCRService(temp_range['min'], temp_range['max'])

    # Initialize InfluxDB service
    influx_config = config['influxdb']
    influx_service = InfluxService(
        host=influx_config['host'],
        port=influx_config['port'],
        database=influx_config['database'],
        username=influx_config.get('username'),
        password=influx_config.get('password')
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
    return jsonify({
        'camera_connected': camera_service.is_connected() if camera_service else False,
        'influx_connected': influx_service.is_connected() if influx_service else False,
        'processing_running': processing_running,
        'last_readings': last_readings,
        'last_reading_time': last_reading_time,
        'interval_minutes': config.get('processing_interval_minutes', 15)
    })


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
