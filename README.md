# Anitab P51cam - Temperature Monitor

Automated temperature monitoring system for Anipill devices. Captures video from a camera monitoring temperature sensor displays, extracts readings via OCR, and logs validated data to InfluxDB.

## Features

- Real-time MJPEG video streaming with ROI overlay
- OCR-based temperature extraction from 8 sensor regions
- Interactive ROI editor (drag, resize, add/delete regions)
- Temperature validation (configurable range, default 5-37°C)
- InfluxDB 1.8 time-series data logging
- Web-based monitoring UI

## Requirements

- Python 3.8+
- Tesseract OCR
- InfluxDB 1.8

## Installation

```bash
# Install Tesseract OCR
sudo apt install tesseract-ocr

# Install venv package
sudo apt install python3.12-venv

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Navigate to project directory and install dependencies
cd /path/to/Anitab_P51cam
pip install -r requirements.txt
```

## Configuration

Edit `config/rois.json`:

```json
{
  "stream_url": "http://10.239.99.61:5000/stream",
  "processing_interval_minutes": 15,
  "temperature_range": {"min": 5, "max": 37},
  "rois": [...],
  "influxdb": {
    "host": "10.239.99.73",
    "port": 8086,
    "database": "Anipill_data"
  }
}
```

## Usage

```bash
python app.py
```

Access the web UI at `http://localhost:8080`

### Web UI Controls

- **Edit ROIs** - Click and drag to position sensor regions
- **Start/Stop Processing** - Enable/disable automatic data collection
- **Capture Now** - Perform immediate OCR reading (for testing)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stream` | GET | Raw MJPEG video stream |
| `/stream/overlay` | GET | Video stream with ROI boxes |
| `/api/rois` | GET/POST | Get or update ROI configuration |
| `/api/config` | GET/POST | Get or update settings |
| `/api/status` | GET | Current system status and readings |
| `/api/start` | POST | Start background processing |
| `/api/stop` | POST | Stop background processing |
| `/api/capture` | POST | Trigger immediate capture |

## Project Structure

```
├── app.py                 # Flask web application
├── config/
│   └── rois.json          # Configuration file
├── services/
│   ├── camera.py          # Video capture service
│   ├── ocr.py             # OCR extraction service
│   └── influx.py          # InfluxDB service
├── templates/
│   └── index.html         # Web UI template
└── static/
    ├── css/style.css
    └── js/roi-editor.js
```
