import cv2
import threading
import time


class CameraService:
    """Service for capturing video frames from MJPEG stream."""

    def __init__(self, stream_url):
        self.stream_url = stream_url
        self.cap = None
        self.frame = None
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

    def start(self):
        """Start the video capture thread."""
        if self.running:
            return

        self.cap = cv2.VideoCapture(self.stream_url)
        if not self.cap.isOpened():
            raise ConnectionError(f"Cannot connect to stream: {self.stream_url}")

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the video capture thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.cap:
            self.cap.release()
            self.cap = None

    def _capture_loop(self):
        """Continuously capture frames in background thread."""
        while self.running:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.frame = frame
                else:
                    # Try to reconnect
                    self.cap.release()
                    time.sleep(1)
                    self.cap = cv2.VideoCapture(self.stream_url)
            else:
                time.sleep(0.1)

    def get_frame(self):
        """Get the latest captured frame."""
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
            return None

    def get_jpeg(self):
        """Get the latest frame as JPEG bytes."""
        frame = self.get_frame()
        if frame is not None:
            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                return jpeg.tobytes()
        return None

    def is_connected(self):
        """Check if camera is connected and capturing."""
        return self.running and self.cap is not None and self.cap.isOpened()

    def draw_rois(self, frame, rois):
        """Draw ROI rectangles on a frame."""
        if frame is None:
            return None

        frame_with_rois = frame.copy()
        for roi in rois:
            x, y, w, h = roi['x'], roi['y'], roi['width'], roi['height']
            cv2.rectangle(frame_with_rois, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Use custom name if available, otherwise default to S{id}
            label = roi.get('name', f"S{roi['id']}")
            # Truncate long names for display
            if len(label) > 12:
                label = label[:9] + "..."
            cv2.putText(frame_with_rois, label, (x, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        return frame_with_rois

    def get_jpeg_with_rois(self, rois):
        """Get the latest frame with ROI overlays as JPEG bytes."""
        frame = self.get_frame()
        if frame is not None:
            frame_with_rois = self.draw_rois(frame, rois)
            ret, jpeg = cv2.imencode('.jpg', frame_with_rois)
            if ret:
                return jpeg.tobytes()
        return None
