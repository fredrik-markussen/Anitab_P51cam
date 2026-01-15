# Anitab P51cam - Functional Specification Document

**Version:** 1.0
**Date:** 2026-01-15
**Author:** Anitab Research Team
**Status:** Draft

---

## Table of Contents

1. [Overview](#1-overview)
2. [User Profile](#2-user-profile)
3. [System Architecture](#3-system-architecture)
4. [User Interface Specifications](#4-user-interface-specifications)
5. [Functional Requirements](#5-functional-requirements)
6. [System Behaviors](#6-system-behaviors)
7. [Data Management](#7-data-management)
8. [Multi-Camera Expansion](#8-multi-camera-expansion)
9. [Configuration Parameters](#9-configuration-parameters)
10. [Error Handling](#10-error-handling)
11. [Future Considerations](#11-future-considerations)

---

## 1. Overview

### 1.1 Purpose

The Anitab P51cam is an automated temperature monitoring system designed to extract and log animal body temperature readings from Anipill sensor displays using optical character recognition (OCR). The system captures video from camera feeds, processes regions of interest (ROIs) to extract temperature values, and logs validated data to InfluxDB for analysis via Grafana.

### 1.2 Scope

This document specifies the functional parameters, user interface design, and system behaviors for the Anitab P51cam application. It serves as the authoritative reference for development decisions.

### 1.3 Use Case

**Primary Use Case:** A biology PhD researcher monitors animal body temperatures during experiments. The system runs continuously, capturing temperature readings from Anipill device displays at configurable intervals. Invalid readings are discarded to maintain data integrity. Historical analysis is performed externally using Grafana dashboards connected to InfluxDB.

### 1.4 Key Objectives

- Accurate OCR extraction of temperature readings from camera feeds
- Reliable data logging to InfluxDB for time-series analysis
- Active monitoring interface for real-time observation
- Easy ROI configuration for different experimental setups
- Future expansion to multi-camera monitoring

---

## 2. User Profile

### 2.1 Primary User

| Attribute | Description |
|-----------|-------------|
| Role | PhD Researcher in Biology |
| Technical Level | Non-developer with good understanding of project requirements |
| Use Pattern | Active monitoring during experiments |
| Environment | Laboratory setting with animal experiments |

### 2.2 User Needs

- Simple, intuitive interface for monitoring current readings
- Visual feedback on system status and sensor health
- Easy configuration of ROI regions without coding
- Reliable unattended operation when not actively monitoring
- Clear indication when readings fail or are out of range

---

## 3. System Architecture

### 3.1 Deployment Environment

```
┌─────────────────────────────────────────────────────────────┐
│                    Laboratory Setup                          │
│                                                              │
│  ┌──────────────┐    MJPEG     ┌──────────────────────────┐ │
│  │  Raspberry   │─────────────▶│     Anipill Devices      │ │
│  │  Pi Camera   │   Stream     │  (Temperature Displays)  │ │
│  └──────────────┘              └──────────────────────────┘ │
│         │                                                    │
│         │ HTTP                                               │
│         ▼                                                    │
│  ┌──────────────┐              ┌──────────────────────────┐ │
│  │   P51cam     │───────────▶  │       InfluxDB           │ │
│  │   Server     │   Write      │   (Time-Series DB)       │ │
│  └──────────────┘              └──────────────────────────┘ │
│         │                                │                   │
│         │ Web UI                         │ Query             │
│         ▼                                ▼                   │
│  ┌──────────────┐              ┌──────────────────────────┐ │
│  │   Browser    │              │        Grafana           │ │
│  │  (User)      │              │   (Historical Charts)    │ │
│  └──────────────┘              └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.8+, Flask |
| OCR Engine | Tesseract via Pytesseract |
| Image Processing | OpenCV |
| Database | InfluxDB 1.8 |
| Frontend | HTML5, CSS3, JavaScript, Fabric.js |
| Visualization | Grafana (external) |

---

## 4. User Interface Specifications

### 4.1 Design Principles

- **Dark Theme:** Professional dark interface to reduce eye strain during extended monitoring sessions
- **Information Density:** Show all critical information without scrolling
- **Clear Status Indicators:** Immediate visual feedback on system state
- **Minimal Clicks:** Common actions accessible with single clicks

### 4.2 Main Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  ANITAB P51CAM                              [Status: ● Running]     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────┐  ┌───────────────────────────┐│
│  │                                 │  │   CURRENT READINGS        ││
│  │                                 │  │                           ││
│  │      LIVE VIDEO FEED            │  │   Sensor 1:  36.5°C  ●    ││
│  │      (with ROI overlay)         │  │   Sensor 2:  36.8°C  ●    ││
│  │                                 │  │   Sensor 3:  37.1°C  ●    ││
│  │                                 │  │   Sensor 4:  36.4°C  ●    ││
│  │   [ROI boxes drawn on feed]     │  │   Sensor 5:  36.9°C  ●    ││
│  │                                 │  │   Sensor 6:  ---.--  ○    ││
│  │                                 │  │   Sensor 7:  36.7°C  ●    ││
│  │                                 │  │   Sensor 8:  36.2°C  ●    ││
│  │                                 │  │                           ││
│  └─────────────────────────────────┘  │   Last Update: 14:32:15   ││
│                                       │   Next Capture: 2m 34s    ││
│                                       └───────────────────────────┘│
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  [▶ Start]  [⏹ Stop]  [📷 Capture Now]  [⚙ Settings]  [ROI Edit]││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 4.3 UI Components

#### 4.3.1 Video Feed Panel

| Element | Specification |
|---------|---------------|
| Size | 640x480 minimum, responsive |
| Feed Type | MJPEG stream with ROI overlay |
| ROI Display | Colored rectangles with sensor names |
| Update Rate | Real-time streaming |

#### 4.3.2 Current Readings Panel

| Element | Specification |
|---------|---------------|
| Display | List of all configured sensors |
| Format | `[Name]: [Value]°C [Status Indicator]` |
| Status Indicators | ● Green = Valid, ○ Gray = No reading, ● Red = Out of range |
| Timestamp | Last successful capture time |
| Countdown | Time until next scheduled capture |

#### 4.3.3 Control Buttons

| Button | Action | Keyboard Shortcut |
|--------|--------|-------------------|
| Start | Begin automatic capture cycle | `S` |
| Stop | Halt automatic captures | `X` |
| Capture Now | Trigger immediate OCR capture | `C` |
| Settings | Open settings panel | `Ctrl+,` |
| ROI Edit | Enter ROI editing mode | `E` |

### 4.4 ROI Editor Interface

```
┌─────────────────────────────────────────────────────────────────────┐
│  ROI EDITOR                                        [Save] [Cancel]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                                                                 ││
│  │                    INTERACTIVE CANVAS                           ││
│  │                                                                 ││
│  │    ┌──────────┐                        Click and drag to       ││
│  │    │ Sensor 1 │ ← Draggable            create new ROI          ││
│  │    └──────────┘   Resizable                                    ││
│  │                      ┌──────────┐                              ││
│  │                      │ Sensor 2 │                              ││
│  │                      └──────────┘                              ││
│  │                                                                 ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ROI List:                                                          │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │ □ Sensor 1  │ x: 100  y: 50   │ 120 x 40  │ [Rename] [Delete] │││
│  │ □ Sensor 2  │ x: 300  y: 150  │ 120 x 40  │ [Rename] [Delete] │││
│  │ [+ Add New ROI]                                                │││
│  └────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

#### 4.4.1 ROI Editor Behaviors

| Action | Behavior |
|--------|----------|
| Click ROI | Select for editing, show resize handles |
| Drag ROI | Reposition on canvas |
| Drag handles | Resize ROI dimensions |
| Double-click | Edit ROI name inline |
| Right-click | Context menu (Delete, Duplicate, Rename) |
| Click canvas | Deselect all ROIs |
| Drag on empty area | Create new ROI |

### 4.5 Settings Panel

```
┌─────────────────────────────────────────────────────────────────────┐
│  SETTINGS                                                    [×]    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─ Capture Settings ─────────────────────────────────────────────┐│
│  │  Capture Interval:  [    15    ] minutes                       ││
│  │  Temperature Range: [   5   ] °C  to  [  37  ] °C              ││
│  └────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ┌─ Camera Settings ──────────────────────────────────────────────┐│
│  │  Stream URL: [ http://192.168.1.100:8080/video           ]     ││
│  │              [Test Connection]  [Reconnect]                    ││
│  └────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ┌─ InfluxDB Settings ────────────────────────────────────────────┐│
│  │  Host:     [ localhost        ]  Port: [ 8086 ]                ││
│  │  Database: [ anipill_temps    ]                                ││
│  │  Username: [ **************** ]  [Test Connection]             ││
│  └────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ┌─ OCR Settings (Advanced) ──────────────────────────────────────┐│
│  │  Threshold Mode:    [Adaptive ▼]                               ││
│  │  CLAHE Enhancement: [✓] Enabled                                ││
│  │  Tesseract PSM:     [7 - Single line ▼]                        ││
│  └────────────────────────────────────────────────────────────────┘│
│                                                                     │
│                                          [Apply]  [Reset Defaults] │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.6 Color Scheme

| Element | Color (Hex) | Usage |
|---------|-------------|-------|
| Background | `#1a1a2e` | Main background |
| Panel Background | `#16213e` | Card/panel backgrounds |
| Primary Accent | `#0f3460` | Headers, borders |
| Text Primary | `#e8e8e8` | Main text |
| Text Secondary | `#a0a0a0` | Labels, hints |
| Success | `#4ecca3` | Valid readings, connected status |
| Warning | `#ffc107` | Warnings, near-limit readings |
| Error | `#ff6b6b` | Errors, invalid readings |
| Inactive | `#6c757d` | Disabled elements |

---

## 5. Functional Requirements

### 5.1 Core Functions

#### FR-001: Video Stream Display

| Attribute | Specification |
|-----------|---------------|
| Description | Display live MJPEG video feed from camera |
| Input | Camera stream URL |
| Output | Real-time video in web interface |
| Behavior | Continuous streaming with automatic reconnection on failure |

#### FR-002: ROI Configuration

| Attribute | Specification |
|-----------|---------------|
| Description | Define rectangular regions for OCR extraction |
| Capacity | 5-8 ROIs per camera (expandable) |
| Properties | x, y, width, height, name |
| Persistence | Save to `config/rois.json` |

#### FR-003: Temperature Extraction

| Attribute | Specification |
|-----------|---------------|
| Description | Extract temperature values from ROI regions using OCR |
| Process | Capture frame → Extract ROI → Preprocess → OCR → Parse value |
| Output Format | Decimal number with one decimal place (e.g., `36.5`) |
| Parallel Processing | Process multiple ROIs concurrently |

#### FR-004: Data Validation

| Attribute | Specification |
|-----------|---------------|
| Description | Validate extracted temperature readings |
| Valid Range | Configurable (default: 5°C to 37°C) |
| Invalid Handling | **Discard** - do not log invalid readings |
| Display | Show `---.--` for failed/invalid readings |

#### FR-005: Data Logging

| Attribute | Specification |
|-----------|---------------|
| Description | Write valid readings to InfluxDB |
| Database | InfluxDB 1.8 |
| Measurement | Configurable (default: `temperature`) |
| Tags | sensor_id, sensor_name, camera_id |
| Fields | value (float) |

#### FR-006: Scheduled Capture

| Attribute | Specification |
|-----------|---------------|
| Description | Automatic periodic temperature capture |
| Interval | Configurable (1-60 minutes) |
| Default | 15 minutes |
| Control | Start/Stop via UI buttons |

#### FR-007: Manual Capture

| Attribute | Specification |
|-----------|---------------|
| Description | On-demand immediate temperature capture |
| Trigger | "Capture Now" button |
| Behavior | Bypass scheduled interval, capture immediately |

### 5.2 User Interface Functions

#### FR-101: Status Display

| Attribute | Specification |
|-----------|---------------|
| Description | Show current system status |
| Elements | Running/Stopped indicator, last capture time, next capture countdown |
| Update Rate | Every 5 seconds |

#### FR-102: Reading Display

| Attribute | Specification |
|-----------|---------------|
| Description | Show current temperature readings |
| Format | Sensor name, value, status indicator |
| Status Colors | Green (valid), Gray (no reading), Red (out of range) |

#### FR-103: ROI Overlay

| Attribute | Specification |
|-----------|---------------|
| Description | Draw ROI rectangles on video feed |
| Style | Colored rectangles with sensor name labels |
| Toggle | Option to show/hide overlay |

---

## 6. System Behaviors

### 6.1 Startup Sequence

```
1. Load configuration from config/rois.json
2. Initialize camera service
   - Connect to MJPEG stream
   - Verify connection successful
   - Begin frame capture thread
3. Initialize OCR service
   - Load Tesseract engine
   - Apply configured settings
4. Initialize InfluxDB service
   - Connect to database
   - Verify write permissions
5. Start Flask web server
6. Display status: Ready (not capturing)
```

### 6.2 Capture Cycle

```
┌─────────────────┐
│  Trigger Event  │ (Scheduled or Manual)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Capture Frame  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  For Each ROI:  │
│  ┌─────────────┐│
│  │Extract Region│
│  └──────┬──────┘│
│         ▼       │
│  ┌─────────────┐│
│  │ Preprocess  ││  (Grayscale, CLAHE, Threshold)
│  └──────┬──────┘│
│         ▼       │
│  ┌─────────────┐│
│  │  Run OCR    ││
│  └──────┬──────┘│
│         ▼       │
│  ┌─────────────┐│
│  │Parse Number ││
│  └──────┬──────┘│
│         ▼       │
│  ┌─────────────┐│
│  │  Validate   ││
│  └──────┬──────┘│
│         │       │
│    Valid?       │
│    ├─Yes────────┼──▶ Log to InfluxDB
│    └─No─────────┼──▶ Discard (display ---.--)
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ Update UI with  │
│ current readings│
└─────────────────┘
```

### 6.3 Error Recovery

| Error Type | Detection | Recovery Action |
|------------|-----------|-----------------|
| Camera disconnect | Frame capture timeout | Attempt reconnection every 30 seconds |
| OCR failure | No parseable number | Display `---.--`, continue with other ROIs |
| InfluxDB disconnect | Write failure | Queue data locally, retry connection |
| Out-of-range reading | Value outside configured range | Discard reading, log to debug output |

### 6.4 State Management

| State | Description | Allowed Transitions |
|-------|-------------|---------------------|
| Idle | System ready, not capturing | → Running |
| Running | Scheduled captures active | → Idle, → Capturing |
| Capturing | Currently processing OCR | → Running |
| Error | System error occurred | → Idle (after resolution) |

---

## 7. Data Management

### 7.1 InfluxDB Schema

```
Measurement: temperature (configurable)

Tags:
  - sensor_id:   string  (e.g., "sensor_1")
  - sensor_name: string  (e.g., "Mouse_A")
  - camera_id:   string  (e.g., "cam_1")

Fields:
  - value: float (temperature in °C)

Timestamp: capture time (UTC)
```

### 7.2 Data Flow

```
Camera → P51cam → InfluxDB → Grafana
         │
         └─ Web UI (current readings only)
```

### 7.3 Data Retention

| Aspect | Specification |
|--------|---------------|
| Current Readings | Displayed in UI, not persisted locally |
| Historical Data | Stored in InfluxDB, retention managed externally |
| Configuration | Persisted in `config/rois.json` |

---

## 8. Multi-Camera Expansion

### 8.1 Future Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MULTI-CAMERA DASHBOARD                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─ Camera Tabs ──────────────────────────────────────────────────┐│
│  │ [Cam 1 ●] [Cam 2 ●] [Cam 3 ○] [+ Add Camera]                   ││
│  └────────────────────────────────────────────────────────────────┘│
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │   Camera 1       │  │   Camera 2       │  │   Camera 3       │ │
│  │   ┌──────────┐   │  │   ┌──────────┐   │  │   ┌──────────┐   │ │
│  │   │  Video   │   │  │   │  Video   │   │  │   │  Video   │   │ │
│  │   │  Feed    │   │  │   │  Feed    │   │  │   │  Feed    │   │ │
│  │   └──────────┘   │  │   └──────────┘   │  │   └──────────┘   │ │
│  │   Sensors: 8     │  │   Sensors: 6     │  │   Disconnected   │ │
│  │   Status: ●      │  │   Status: ●      │  │   Status: ○      │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                     │
│  ┌─ All Readings Summary ─────────────────────────────────────────┐│
│  │ Total Sensors: 14  │  Valid: 12  │  Failed: 2  │  [Export CSV] ││
│  └────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Multi-Camera Requirements

| Requirement | Specification |
|-------------|---------------|
| Display | Single dashboard with all cameras visible |
| Layout | Grid or tab-based camera switching |
| Configuration | Independent ROI configuration per camera |
| Data Logging | Unified InfluxDB with camera_id tag |
| Status | Per-camera connection status indicators |
| Scalability | Support 2-8 cameras initially |

### 8.3 Configuration Structure (Future)

```json
{
  "cameras": [
    {
      "id": "cam_1",
      "name": "Lab A - Cage 1",
      "stream_url": "http://192.168.1.100:8080/video",
      "enabled": true,
      "rois": [
        {"id": "sensor_1", "name": "Mouse_A", "x": 100, "y": 50, "width": 120, "height": 40}
      ]
    },
    {
      "id": "cam_2",
      "name": "Lab A - Cage 2",
      "stream_url": "http://192.168.1.101:8080/video",
      "enabled": true,
      "rois": []
    }
  ],
  "global_settings": {
    "processing_interval_minutes": 15,
    "temperature_range": {"min": 5, "max": 37},
    "influxdb": {}
  }
}
```

---

## 9. Configuration Parameters

### 9.1 Capture Settings

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `processing_interval_minutes` | integer | 15 | 1-60 | Minutes between automatic captures |
| `temperature_range.min` | float | 5.0 | -10 to 50 | Minimum valid temperature |
| `temperature_range.max` | float | 37.0 | -10 to 50 | Maximum valid temperature |

### 9.2 Camera Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stream_url` | string | - | MJPEG stream URL |
| `reconnect_interval_seconds` | integer | 30 | Seconds between reconnection attempts |

### 9.3 OCR Settings

| Parameter | Type | Default | Options | Description |
|-----------|------|---------|---------|-------------|
| `threshold_mode` | string | "adaptive" | adaptive, binary | Image thresholding method |
| `clahe_enabled` | boolean | true | - | Enable contrast enhancement |
| `tesseract_psm` | integer | 7 | 0-13 | Tesseract page segmentation mode |
| `block_size` | integer | 11 | odd numbers | Adaptive threshold block size |

### 9.4 InfluxDB Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | string | "localhost" | InfluxDB server address |
| `port` | integer | 8086 | InfluxDB port |
| `database` | string | "anipill" | Database name |
| `measurement` | string | "temperature" | Measurement name |
| `username` | string | - | Authentication username |
| `password` | string | - | Authentication password |

---

## 10. Error Handling

### 10.1 Error Categories

| Category | Examples | User Notification |
|----------|----------|-------------------|
| Camera | Stream unavailable, timeout | Status indicator red, toast message |
| OCR | No text detected, parse failure | Reading shows `---.--` |
| Database | Connection failed, write error | Status banner, retry indicator |
| Configuration | Invalid JSON, missing fields | Error modal on load |

### 10.2 Error Messages

| Code | Message | User Action |
|------|---------|-------------|
| E001 | "Camera connection failed" | Check camera URL and network |
| E002 | "OCR extraction failed for [sensor]" | Adjust ROI position or OCR settings |
| E003 | "InfluxDB connection refused" | Verify database settings |
| E004 | "Temperature out of valid range" | Reading discarded (automatic) |
| E005 | "Configuration file corrupted" | Reset to defaults or restore backup |

---

## 11. Future Considerations

### 11.1 Planned Enhancements

| Feature | Priority | Description |
|---------|----------|-------------|
| Multi-camera support | High | Single dashboard for multiple cameras |
| Camera health monitoring | Medium | Detect camera drift or focus issues |
| Batch export | Low | Export readings to CSV from UI |
| Mobile-responsive UI | Low | Support tablet/phone viewing |

### 11.2 Not In Scope

The following features are explicitly **not** included in this specification:

- User authentication/login system
- Email/SMS alerting
- Historical data charts (use Grafana)
- Audit trail/compliance logging
- Cloud deployment

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| Anipill | Implantable temperature sensor device for research animals |
| ROI | Region of Interest - rectangular area on video frame for OCR |
| OCR | Optical Character Recognition - extracting text from images |
| MJPEG | Motion JPEG - video streaming format |
| CLAHE | Contrast Limited Adaptive Histogram Equalization |
| PSM | Page Segmentation Mode (Tesseract setting) |

---

## Appendix B: File Structure

```
Anitab_P51cam/
├── app.py                    # Main Flask application
├── requirements.txt          # Python dependencies
├── Anitab_P51cam-FSD.md     # This document
├── config/
│   └── rois.json            # Configuration file
├── services/
│   ├── camera.py            # Video capture service
│   ├── ocr.py               # OCR processing service
│   └── influx.py            # Database service
├── templates/
│   └── index.html           # Web UI template
└── static/
    ├── css/style.css        # Stylesheet
    └── js/roi-editor.js     # ROI editor JavaScript
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-15 | Anitab Research Team | Initial specification |

---

*This document should be referenced during all development activities. Any deviations from these specifications require documented approval.*
