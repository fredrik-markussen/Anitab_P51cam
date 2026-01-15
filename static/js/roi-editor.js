// Anitab P51cam ROI Editor
// Uses Fabric.js for interactive ROI manipulation

class ROIEditor {
    constructor() {
        this.canvas = null;
        this.videoFeed = null;
        this.rois = [];
        this.editMode = true;
        this.roiIdCounter = 0;
        this.videoWidth = 640;
        this.videoHeight = 480;
        this.maxDisplayWidth = 960;

        this.init();
    }

    init() {
        this.videoFeed = document.getElementById('video-feed');
        this.initCanvas();
        this.loadROIs();
        this.loadInfluxConfig();
        this.loadOCRSettings();
        this.bindEvents();
        this.initCollapsibles();
        this.startStatusPolling();
        this.startVideoBackground();
    }

    initCanvas() {
        const canvasEl = document.getElementById('roi-canvas');
        canvasEl.width = this.videoWidth;
        canvasEl.height = this.videoHeight;

        this.canvas = new fabric.Canvas('roi-canvas', {
            selection: true,
            preserveObjectStacking: true
        });

        this.canvas.setWidth(this.videoWidth);
        this.canvas.setHeight(this.videoHeight);
    }

    updateCanvasSize(width, height) {
        if (width && height && (width !== this.videoWidth || height !== this.videoHeight)) {
            console.log(`Updating canvas to native resolution: ${width}x${height}`);
            this.videoWidth = width;
            this.videoHeight = height;

            // Set canvas to native resolution (internal coordinates)
            this.canvas.setWidth(width);
            this.canvas.setHeight(height);

            // Apply CSS scaling if too large for display
            const wrapper = document.querySelector('.canvas-container');
            if (width > this.maxDisplayWidth) {
                const scale = this.maxDisplayWidth / width;
                wrapper.style.transform = `scale(${scale})`;
                wrapper.style.transformOrigin = 'top left';
                wrapper.style.width = `${width}px`;
                wrapper.style.height = `${height}px`;
                // Adjust container size for scaled content
                const container = document.querySelector('.video-container');
                container.style.width = `${Math.round(width * scale)}px`;
                container.style.height = `${Math.round(height * scale)}px`;
                this.updateResolutionDisplay(width, height, Math.round(scale * 100));
            } else {
                wrapper.style.transform = '';
                wrapper.style.transformOrigin = '';
                wrapper.style.width = '';
                wrapper.style.height = '';
                const container = document.querySelector('.video-container');
                container.style.width = '';
                container.style.height = '';
                this.updateResolutionDisplay(width, height, 100);
            }

            this.renderROIs();
        }
    }

    updateResolutionDisplay(width, height, scalePercent) {
        let resDisplay = document.getElementById('resolution-display');
        if (!resDisplay) {
            resDisplay = document.createElement('span');
            resDisplay.id = 'resolution-display';
            resDisplay.className = 'resolution-display';
            document.querySelector('.refresh-control').prepend(resDisplay);
        }
        resDisplay.textContent = `${width}x${height}`;
        if (scalePercent < 100) {
            resDisplay.textContent += ` (${scalePercent}%)`;
        }
    }

    startVideoBackground() {
        // Update canvas background with video frames
        const updateBackground = () => {
            if (this.editMode) {
                // In edit mode, use static image as background
                fabric.Image.fromURL('/stream', (img) => {
                    if (img) {
                        // Scale image to fit canvas (native resolution)
                        img.scaleToWidth(this.videoWidth);
                        this.canvas.setBackgroundImage(img, this.canvas.renderAll.bind(this.canvas));
                    }
                }, { crossOrigin: 'anonymous' });
            }
        };

        // Update background periodically based on slider value
        let refreshInterval = setInterval(updateBackground, 1000);
        updateBackground();

        // Handle refresh rate slider changes
        const slider = document.getElementById('refresh-rate');
        const valueDisplay = document.getElementById('refresh-rate-value');

        slider.addEventListener('input', () => {
            const rate = parseInt(slider.value);
            valueDisplay.textContent = rate;

            // Clear old interval and set new one
            clearInterval(refreshInterval);
            refreshInterval = setInterval(updateBackground, rate);
        });
    }

    initCollapsibles() {
        document.querySelectorAll('.collapsible-header').forEach(header => {
            header.addEventListener('click', () => {
                const targetId = header.dataset.target;
                const content = document.getElementById(targetId);
                const icon = header.querySelector('.toggle-icon');

                content.classList.toggle('expanded');
                icon.textContent = content.classList.contains('expanded') ? '-' : '+';
            });
        });
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
        rect.roiName = roi.name || '';

        // Add label
        const displayLabel = roi.name || `S${roi.id}`;
        const label = new fabric.Text(displayLabel, {
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

        rect.label = label;

        this.canvas.add(rect);
        this.canvas.add(label);

        rect.on('moving', () => {
            label.set({ left: rect.left, top: rect.top - 18 });
        });

        rect.on('scaling', () => {
            label.set({ left: rect.left, top: rect.top - 18 });
        });
    }

    addNewROI() {
        this.roiIdCounter++;
        const newROI = {
            id: this.roiIdCounter,
            x: 100,
            y: 100,
            width: 150,
            height: 60
        };
        this.rois.push(newROI);
        this.addROIToCanvas(newROI);
        this.updateROIList();
        this.canvas.renderAll();
    }

    async saveROIs() {
        // Update ROI data from canvas
        const objects = this.canvas.getObjects().filter(obj => obj.isROI && !obj.isLabel);

        this.rois = objects.map(rect => {
            const roi = {
                id: rect.roiId,
                x: Math.round(rect.left),
                y: Math.round(rect.top),
                width: Math.round(rect.width * rect.scaleX),
                height: Math.round(rect.height * rect.scaleY)
            };
            if (rect.roiName) {
                roi.name = rect.roiName;
            }
            return roi;
        });

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

    deleteROIById(roiId) {
        const objects = this.canvas.getObjects();
        const rect = objects.find(obj => obj.isROI && !obj.isLabel && obj.roiId === roiId);
        if (rect) {
            if (rect.label) {
                this.canvas.remove(rect.label);
            }
            this.canvas.remove(rect);
            this.rois = this.rois.filter(r => r.id !== roiId);
            this.updateROIList();
            this.canvas.renderAll();
        }
    }

    updateROIName(roiId, name) {
        // Update in data
        const roi = this.rois.find(r => r.id === roiId);
        if (roi) {
            roi.name = name || undefined;
        }

        // Update canvas label
        const objects = this.canvas.getObjects();
        const rect = objects.find(obj => obj.isROI && !obj.isLabel && obj.roiId === roiId);
        if (rect) {
            rect.roiName = name;
            if (rect.label) {
                rect.label.set('text', name || `S${roiId}`);
                this.canvas.renderAll();
            }
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
                <div class="roi-info">
                    <input type="text" class="roi-name-input"
                           value="${roi.name || ''}"
                           placeholder="Sensor ${roi.id}"
                           data-roi-id="${roi.id}">
                    <span class="roi-coords">(${roi.x}, ${roi.y}) ${roi.width}x${roi.height}</span>
                </div>
                <button class="btn-delete-roi" data-roi-id="${roi.id}" title="Delete ROI">x</button>
            </div>
        `).join('');

        // Bind name input change handlers
        container.querySelectorAll('.roi-name-input').forEach(input => {
            input.addEventListener('change', (e) => this.updateROIName(
                parseInt(e.target.dataset.roiId),
                e.target.value
            ));
        });

        // Bind delete handlers
        container.querySelectorAll('.btn-delete-roi').forEach(btn => {
            btn.addEventListener('click', (e) => this.deleteROIById(
                parseInt(e.target.dataset.roiId)
            ));
        });
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
        document.getElementById('btn-reconnect-camera').addEventListener('click', () => this.reconnectCamera());

        // Delete on keyboard
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Delete' || e.key === 'Backspace') {
                if (document.activeElement.tagName !== 'INPUT') {
                    this.deleteSelectedROI();
                }
            }
        });

        // Processing controls
        document.getElementById('btn-start').addEventListener('click', () => this.startProcessing());
        document.getElementById('btn-stop').addEventListener('click', () => this.stopProcessing());
        document.getElementById('btn-capture').addEventListener('click', () => this.captureNow());
        document.getElementById('btn-capture-debug').addEventListener('click', () => this.captureDebug());

        // Settings
        document.getElementById('btn-save-interval').addEventListener('click', () => this.saveInterval());

        // InfluxDB settings
        document.getElementById('btn-test-influx').addEventListener('click', () => this.testInfluxConnection());
        document.getElementById('btn-save-influx').addEventListener('click', () => this.saveInfluxConfig());

        // OCR settings
        document.getElementById('btn-save-ocr').addEventListener('click', () => this.saveOCRSettings());
        document.getElementById('btn-reset-ocr').addEventListener('click', () => this.resetOCRDefaults());

        // Threshold mode toggle
        document.getElementById('threshold-mode').addEventListener('change', () => this.updateThresholdModeVisibility());
    }

    // InfluxDB Configuration Methods
    async loadInfluxConfig() {
        try {
            const response = await fetch('/api/influxdb');
            const config = await response.json();
            document.getElementById('influx-host').value = config.host || '';
            document.getElementById('influx-port').value = config.port || 8086;
            document.getElementById('influx-database').value = config.database || '';
            document.getElementById('influx-measurement').value = config.measurement || 'anipills';
            document.getElementById('influx-username').value = config.username || '';
        } catch (error) {
            console.error('Failed to load InfluxDB config:', error);
        }
    }

    async saveInfluxConfig() {
        const config = {
            host: document.getElementById('influx-host').value,
            port: parseInt(document.getElementById('influx-port').value),
            database: document.getElementById('influx-database').value,
            measurement: document.getElementById('influx-measurement').value,
            username: document.getElementById('influx-username').value
        };

        const password = document.getElementById('influx-password').value;
        if (password) {
            config.password = password;
        }

        try {
            const response = await fetch('/api/influxdb', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const data = await response.json();
            if (data.success) {
                this.showMessage(`InfluxDB settings saved. ${data.connected ? 'Connected!' : 'Not connected'}`,
                               data.connected ? 'success' : 'error');
            } else {
                this.showMessage('Failed to save InfluxDB settings', 'error');
            }
        } catch (error) {
            this.showMessage('Failed to save InfluxDB settings', 'error');
        }
    }

    async testInfluxConnection() {
        const config = {
            host: document.getElementById('influx-host').value,
            port: parseInt(document.getElementById('influx-port').value),
            database: document.getElementById('influx-database').value,
            measurement: document.getElementById('influx-measurement').value,
            username: document.getElementById('influx-username').value,
            password: document.getElementById('influx-password').value
        };

        try {
            const response = await fetch('/api/influxdb/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const data = await response.json();
            this.showMessage(data.message, data.success ? 'success' : 'error');
        } catch (error) {
            this.showMessage('Connection test failed', 'error');
        }
    }

    // OCR Settings Methods
    async loadOCRSettings() {
        try {
            const response = await fetch('/api/ocr-settings');
            const data = await response.json();

            // Temperature range
            document.getElementById('temp-min').value = data.temperature_range?.min ?? 5;
            document.getElementById('temp-max').value = data.temperature_range?.max ?? 37;

            // OCR settings
            const ocr = data.ocr_settings || {};

            // New threshold mode settings
            document.getElementById('threshold-mode').value = ocr.threshold_mode ?? 'simple';
            document.getElementById('threshold-value').value = ocr.threshold_value ?? 200;
            document.getElementById('use-clahe').checked = ocr.use_clahe ?? false;
            document.getElementById('psm-mode').value = ocr.psm_mode ?? 6;

            // Adaptive threshold settings (CLAHE)
            document.getElementById('clip-limit').value = ocr.clip_limit ?? 2.0;
            document.getElementById('tile-grid').value = ocr.tile_grid_size ?? 8;
            document.getElementById('block-size').value = ocr.block_size ?? 11;
            document.getElementById('c-constant').value = ocr.c_constant ?? 2;

            // Update visibility based on threshold mode
            this.updateThresholdModeVisibility();
        } catch (error) {
            console.error('Failed to load OCR settings:', error);
        }
    }

    updateThresholdModeVisibility() {
        const mode = document.getElementById('threshold-mode').value;
        const simpleSettings = document.getElementById('simple-threshold-settings');
        const adaptiveSettings = document.getElementById('adaptive-threshold-settings');

        if (simpleSettings) {
            simpleSettings.style.display = mode === 'simple' ? 'block' : 'none';
        }
        if (adaptiveSettings) {
            adaptiveSettings.style.display = mode === 'adaptive' ? 'block' : 'none';
        }
    }

    async saveOCRSettings() {
        const settings = {
            temperature_range: {
                min: parseFloat(document.getElementById('temp-min').value),
                max: parseFloat(document.getElementById('temp-max').value)
            },
            ocr_settings: {
                // Threshold mode settings
                threshold_mode: document.getElementById('threshold-mode').value,
                threshold_value: parseInt(document.getElementById('threshold-value').value),
                use_clahe: document.getElementById('use-clahe').checked,
                psm_mode: parseInt(document.getElementById('psm-mode').value),
                // CLAHE/Adaptive settings
                clip_limit: parseFloat(document.getElementById('clip-limit').value),
                tile_grid_size: parseInt(document.getElementById('tile-grid').value),
                block_size: parseInt(document.getElementById('block-size').value),
                c_constant: parseInt(document.getElementById('c-constant').value)
            }
        };

        console.log('Saving OCR settings:', settings);

        try {
            const response = await fetch('/api/ocr-settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });

            const data = await response.json();
            console.log('Server response:', data);

            if (response.ok && data.success) {
                this.showMessage(`OCR settings saved (threshold=${data.applied_settings?.threshold_value}, mode=${data.applied_settings?.threshold_mode})`, 'success');
            } else {
                this.showMessage('Failed to save OCR settings', 'error');
            }
        } catch (error) {
            console.error('Save error:', error);
            this.showMessage('Failed to save OCR settings', 'error');
        }
    }

    resetOCRDefaults() {
        // Legacy-style defaults (matching camera_check.py)
        document.getElementById('temp-min').value = 5;
        document.getElementById('temp-max').value = 37;
        document.getElementById('threshold-mode').value = 'simple';
        document.getElementById('threshold-value').value = 200;
        document.getElementById('use-clahe').checked = false;
        document.getElementById('psm-mode').value = 6;
        document.getElementById('clip-limit').value = 2.0;
        document.getElementById('tile-grid').value = 8;
        document.getElementById('block-size').value = 11;
        document.getElementById('c-constant').value = 2;
        this.updateThresholdModeVisibility();
    }

    // Camera Methods
    async reconnectCamera() {
        this.showMessage('Reconnecting camera...', 'success');
        try {
            const response = await fetch('/api/camera/reconnect', { method: 'POST' });
            const data = await response.json();
            if (response.ok && data.success) {
                const res = data.resolution;
                this.showMessage(`Camera reconnected (${res?.width}x${res?.height})`, 'success');
                if (res) {
                    this.updateCanvasSize(res.width, res.height);
                }
            } else {
                this.showMessage(data.error || 'Reconnect failed', 'error');
            }
        } catch (error) {
            this.showMessage('Reconnect failed', 'error');
        }
    }

    // Processing Methods
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

    async captureDebug() {
        try {
            const response = await fetch('/api/capture/debug', { method: 'POST' });
            const data = await response.json();
            if (response.ok) {
                this.updateReadings(data.readings, data.timestamp);
                this.updateDebugOutput(data.readings);
                this.showMessage('Debug capture complete', 'success');

                // Auto-expand debug section
                const debugSection = document.getElementById('debug-section');
                const debugHeader = document.querySelector('[data-target="debug-section"]');
                if (!debugSection.classList.contains('expanded')) {
                    debugSection.classList.add('expanded');
                    debugHeader.querySelector('.toggle-icon').textContent = '-';
                }
            } else {
                this.showMessage(data.error || 'Debug capture failed', 'error');
            }
        } catch (error) {
            this.showMessage('Debug capture failed', 'error');
        }
    }

    updateDebugOutput(readings) {
        const container = document.getElementById('debug-container');

        if (!readings || readings.length === 0) {
            container.innerHTML = '<p class="no-data">No debug data available</p>';
            return;
        }

        container.innerHTML = readings.map(r => {
            const statusClass = r.valid ? 'valid' : 'invalid';
            const temp = r.temperature !== null ? r.temperature.toFixed(2) + ' C' : 'N/A';
            const images = r.debug_images || {};
            const displayName = r.sensor_name || `Sensor ${r.sensor_id}`;

            return `
                <div class="debug-roi">
                    <div class="debug-roi-header">
                        <span class="debug-roi-name">${displayName}</span>
                        <span class="debug-roi-result ${statusClass}">${temp}</span>
                    </div>
                    <div class="debug-images">
                        ${images.original ? `
                            <div class="debug-image-item">
                                <img src="data:image/png;base64,${images.original}" alt="Original">
                                <div class="debug-image-label">Original</div>
                            </div>
                        ` : ''}
                        ${images.grayscale ? `
                            <div class="debug-image-item">
                                <img src="data:image/png;base64,${images.grayscale}" alt="Grayscale">
                                <div class="debug-image-label">Grayscale</div>
                            </div>
                        ` : ''}
                        ${images.enhanced ? `
                            <div class="debug-image-item">
                                <img src="data:image/png;base64,${images.enhanced}" alt="CLAHE">
                                <div class="debug-image-label">CLAHE</div>
                            </div>
                        ` : ''}
                        ${images.threshold ? `
                            <div class="debug-image-item">
                                <img src="data:image/png;base64,${images.threshold}" alt="Threshold">
                                <div class="debug-image-label">Threshold</div>
                            </div>
                        ` : ''}
                    </div>
                    <div class="debug-raw-text">
                        Raw OCR: "${r.raw_text || '(empty)'}"
                        ${!r.valid && r.reason ? ` - ${r.reason}` : ''}
                    </div>
                </div>
            `;
        }).join('');
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

        // Show/hide offline overlay
        const offlineOverlay = document.getElementById('offline-overlay');
        if (offlineOverlay) {
            offlineOverlay.style.display = status.camera_connected ? 'none' : 'flex';
        }

        // Update interval field
        document.getElementById('interval').value = status.interval_minutes;

        // Update canvas size if video resolution changed
        if (status.video_resolution) {
            this.updateCanvasSize(status.video_resolution.width, status.video_resolution.height);
        }

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
            const displayName = r.sensor_name || `Sensor ${r.sensor_id}`;
            return `
                <div class="reading-item ${statusClass}">
                    <span class="sensor-id">${displayName}</span>
                    <span class="temperature">${temp} C</span>
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
