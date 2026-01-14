// Anitab P51cam ROI Editor
// Uses Fabric.js for interactive ROI manipulation

class ROIEditor {
    constructor() {
        this.canvas = null;
        this.videoFeed = null;
        this.rois = [];
        this.editMode = true;
        this.roiIdCounter = 0;

        this.init();
    }

    init() {
        this.videoFeed = document.getElementById('video-feed');
        this.initCanvas();
        this.loadROIs();
        this.bindEvents();
        this.startStatusPolling();
        this.startVideoBackground();
    }

    initCanvas() {
        const container = document.querySelector('.video-container');
        const canvasEl = document.getElementById('roi-canvas');

        // Set canvas size to match video
        canvasEl.width = 640;
        canvasEl.height = 480;

        this.canvas = new fabric.Canvas('roi-canvas', {
            selection: true,
            preserveObjectStacking: true
        });

        this.canvas.setWidth(640);
        this.canvas.setHeight(480);
    }

    startVideoBackground() {
        // Update canvas background with video frames
        const updateBackground = () => {
            if (this.editMode) {
                // In edit mode, use static image as background
                fabric.Image.fromURL('/stream', (img) => {
                    if (img) {
                        img.scaleToWidth(this.canvas.width);
                        this.canvas.setBackgroundImage(img, this.canvas.renderAll.bind(this.canvas));
                    }
                }, { crossOrigin: 'anonymous' });
            }
        };

        // Update background periodically
        setInterval(updateBackground, 1000);
        updateBackground();
    }

    async loadROIs() {
        try {
            const response = await fetch('/api/rois');
            const rois = await response.json();
            this.rois = rois;
            this.roiIdCounter = Math.max(...rois.map(r => r.id), 0);
            this.renderROIs();
            this.updateROIList();
        } catch (error) {
            console.error('Failed to load ROIs:', error);
        }
    }

    renderROIs() {
        // Clear existing ROI objects
        const objects = this.canvas.getObjects().filter(obj => obj.isROI);
        objects.forEach(obj => this.canvas.remove(obj));

        // Add ROI rectangles
        this.rois.forEach(roi => {
            this.addROIToCanvas(roi);
        });

        this.canvas.renderAll();
    }

    addROIToCanvas(roi) {
        const rect = new fabric.Rect({
            left: roi.x,
            top: roi.y,
            width: roi.width,
            height: roi.height,
            fill: 'rgba(0, 255, 0, 0.2)',
            stroke: '#00ff00',
            strokeWidth: 2,
            cornerColor: '#00ff00',
            cornerSize: 8,
            transparentCorners: false,
            hasRotatingPoint: false,
            lockRotation: true
        });

        rect.isROI = true;
        rect.roiId = roi.id;

        // Add label
        const label = new fabric.Text(`S${roi.id}`, {
            left: roi.x,
            top: roi.y - 18,
            fontSize: 14,
            fill: '#00ff00',
            fontFamily: 'Arial',
            selectable: false,
            evented: false
        });
        label.isROI = true;
        label.isLabel = true;
        label.roiId = roi.id;

        // Group rect and label
        rect.label = label;

        this.canvas.add(rect);
        this.canvas.add(label);

        // Update label position when rect moves
        rect.on('moving', () => {
            label.set({
                left: rect.left,
                top: rect.top - 18
            });
        });

        rect.on('scaling', () => {
            label.set({
                left: rect.left * rect.scaleX,
                top: rect.top * rect.scaleY - 18
            });
        });
    }

    addNewROI() {
        this.roiIdCounter++;
        const newROI = {
            id: this.roiIdCounter,
            x: 100,
            y: 100,
            width: 95,
            height: 41
        };
        this.rois.push(newROI);
        this.addROIToCanvas(newROI);
        this.updateROIList();
        this.canvas.renderAll();
    }

    async saveROIs() {
        // Update ROI data from canvas
        const objects = this.canvas.getObjects().filter(obj => obj.isROI && !obj.isLabel);

        this.rois = objects.map(rect => ({
            id: rect.roiId,
            x: Math.round(rect.left),
            y: Math.round(rect.top),
            width: Math.round(rect.width * rect.scaleX),
            height: Math.round(rect.height * rect.scaleY)
        }));

        try {
            const response = await fetch('/api/rois', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.rois)
            });

            if (response.ok) {
                this.showMessage('ROIs saved successfully', 'success');
                this.updateROIList();
            } else {
                this.showMessage('Failed to save ROIs', 'error');
            }
        } catch (error) {
            console.error('Save error:', error);
            this.showMessage('Failed to save ROIs', 'error');
        }
    }

    resetROIs() {
        if (confirm('Reset all ROIs to saved configuration?')) {
            this.loadROIs();
        }
    }

    deleteSelectedROI() {
        const activeObject = this.canvas.getActiveObject();
        if (activeObject && activeObject.isROI) {
            // Remove label
            if (activeObject.label) {
                this.canvas.remove(activeObject.label);
            }
            // Remove rect
            this.canvas.remove(activeObject);
            // Remove from data
            this.rois = this.rois.filter(r => r.id !== activeObject.roiId);
            this.updateROIList();
            this.canvas.renderAll();
        }
    }

    updateROIList() {
        const container = document.getElementById('roi-list');
        if (this.rois.length === 0) {
            container.innerHTML = '<p class="no-data">No ROIs defined</p>';
            return;
        }

        container.innerHTML = this.rois.map(roi => `
            <div class="roi-item" data-id="${roi.id}">
                <span class="roi-label">Sensor ${roi.id}</span>
                <span class="roi-coords">(${roi.x}, ${roi.y}) ${roi.width}x${roi.height}</span>
            </div>
        `).join('');
    }

    setEditMode(enabled) {
        this.editMode = enabled;
        this.canvas.selection = enabled;

        const objects = this.canvas.getObjects();
        objects.forEach(obj => {
            obj.selectable = enabled;
            obj.evented = enabled && !obj.isLabel;
        });

        document.getElementById('btn-edit-mode').classList.toggle('active', enabled);
        document.getElementById('btn-view-mode').classList.toggle('active', !enabled);

        this.canvas.renderAll();
    }

    bindEvents() {
        // Mode toggle
        document.getElementById('btn-edit-mode').addEventListener('click', () => this.setEditMode(true));
        document.getElementById('btn-view-mode').addEventListener('click', () => this.setEditMode(false));

        // ROI controls
        document.getElementById('btn-add-roi').addEventListener('click', () => this.addNewROI());
        document.getElementById('btn-save-rois').addEventListener('click', () => this.saveROIs());
        document.getElementById('btn-reset-rois').addEventListener('click', () => this.resetROIs());

        // Delete on keyboard
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Delete' || e.key === 'Backspace') {
                this.deleteSelectedROI();
            }
        });

        // Processing controls
        document.getElementById('btn-start').addEventListener('click', () => this.startProcessing());
        document.getElementById('btn-stop').addEventListener('click', () => this.stopProcessing());
        document.getElementById('btn-capture').addEventListener('click', () => this.captureNow());

        // Settings
        document.getElementById('btn-save-interval').addEventListener('click', () => this.saveInterval());
    }

    async startProcessing() {
        try {
            const response = await fetch('/api/start', { method: 'POST' });
            const data = await response.json();
            if (response.ok) {
                this.showMessage('Processing started', 'success');
            } else {
                this.showMessage(data.error || 'Failed to start', 'error');
            }
        } catch (error) {
            this.showMessage('Failed to start processing', 'error');
        }
    }

    async stopProcessing() {
        try {
            const response = await fetch('/api/stop', { method: 'POST' });
            const data = await response.json();
            if (response.ok) {
                this.showMessage('Processing stopped', 'success');
            } else {
                this.showMessage(data.error || 'Failed to stop', 'error');
            }
        } catch (error) {
            this.showMessage('Failed to stop processing', 'error');
        }
    }

    async captureNow() {
        try {
            const response = await fetch('/api/capture', { method: 'POST' });
            const data = await response.json();
            if (response.ok) {
                this.updateReadings(data.readings, data.timestamp);
                this.showMessage('Capture complete', 'success');
            } else {
                this.showMessage(data.error || 'Capture failed', 'error');
            }
        } catch (error) {
            this.showMessage('Capture failed', 'error');
        }
    }

    async saveInterval() {
        const interval = document.getElementById('interval').value;
        try {
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ processing_interval_minutes: parseInt(interval) })
            });
            if (response.ok) {
                this.showMessage('Interval saved', 'success');
            }
        } catch (error) {
            this.showMessage('Failed to save interval', 'error');
        }
    }

    startStatusPolling() {
        const poll = async () => {
            try {
                const response = await fetch('/api/status');
                const status = await response.json();
                this.updateStatus(status);
            } catch (error) {
                console.error('Status poll failed:', error);
            }
        };

        poll();
        setInterval(poll, 5000);
    }

    updateStatus(status) {
        // Update status indicators
        const cameraEl = document.getElementById('camera-status');
        cameraEl.textContent = `Camera: ${status.camera_connected ? 'Connected' : 'Disconnected'}`;
        cameraEl.className = `status-indicator ${status.camera_connected ? 'connected' : 'disconnected'}`;

        const influxEl = document.getElementById('influx-status');
        influxEl.textContent = `InfluxDB: ${status.influx_connected ? 'Connected' : 'Disconnected'}`;
        influxEl.className = `status-indicator ${status.influx_connected ? 'connected' : 'disconnected'}`;

        const processingEl = document.getElementById('processing-status');
        processingEl.textContent = `Processing: ${status.processing_running ? 'Running' : 'Stopped'}`;
        processingEl.className = `status-indicator ${status.processing_running ? 'running' : 'stopped'}`;

        // Update interval field
        document.getElementById('interval').value = status.interval_minutes;

        // Update readings
        if (status.last_readings && status.last_readings.length > 0) {
            this.updateReadings(status.last_readings, status.last_reading_time);
        }
    }

    updateReadings(readings, timestamp) {
        const container = document.getElementById('readings-container');

        if (!readings || readings.length === 0) {
            container.innerHTML = '<p class="no-data">No readings yet</p>';
            return;
        }

        container.innerHTML = readings.map(r => {
            const statusClass = r.valid ? 'valid' : 'invalid';
            const temp = r.temperature !== null ? r.temperature.toFixed(2) : 'N/A';
            return `
                <div class="reading-item ${statusClass}">
                    <span class="sensor-id">Sensor ${r.sensor_id}</span>
                    <span class="temperature">${temp}°C</span>
                    ${!r.valid ? `<span class="reason">${r.reason || ''}</span>` : ''}
                </div>
            `;
        }).join('');

        document.getElementById('last-reading-time').textContent =
            timestamp ? `Last update: ${timestamp}` : '';
    }

    showMessage(text, type) {
        // Simple message display (could be enhanced with toast notifications)
        console.log(`[${type.toUpperCase()}] ${text}`);

        // You could add a toast notification here
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = text;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('show');
        }, 10);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.roiEditor = new ROIEditor();
});
