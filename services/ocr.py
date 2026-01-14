import cv2
import pytesseract
import platform
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed


class OCRService:
    """Service for extracting temperature readings from video frames using OCR."""

    DEFAULT_OCR_SETTINGS = {
        'clip_limit': 2.0,
        'tile_grid_size': 8,
        'block_size': 11,
        'c_constant': 2
    }

    def __init__(self, temp_min=5, temp_max=37, ocr_settings=None):
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.ocr_settings = {**self.DEFAULT_OCR_SETTINGS, **(ocr_settings or {})}
        # Set tesseract path based on platform
        if platform.system() == 'Windows':
            pytesseract.pytesseract.tesseract_cmd = r'C:\Users\fma017\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
        # On Linux/Ubuntu, tesseract is typically in PATH at /usr/bin/tesseract

    def update_settings(self, temp_min=None, temp_max=None, ocr_settings=None):
        """Update OCR settings dynamically."""
        if temp_min is not None:
            self.temp_min = temp_min
        if temp_max is not None:
            self.temp_max = temp_max
        if ocr_settings is not None:
            self.ocr_settings.update(ocr_settings)

    def format_temperature(self, raw_temp):
        """Convert raw OCR text to formatted temperature string."""
        temp_digits = ''.join(filter(str.isdigit, raw_temp))
        if len(temp_digits) >= 3:
            return f"{int(temp_digits[:-2]):02}.{int(temp_digits[-2:]):02}"
        return None

    def extract_from_roi(self, frame, roi):
        """Extract temperature text from a single ROI region."""
        x, y, w, h = roi['x'], roi['y'], roi['width'], roi['height']

        # Ensure ROI is within frame bounds
        if x < 0 or y < 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
            return None

        roi_frame = frame[y:y+h, x:x+w]

        # Convert to grayscale
        gray_frame = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)

        # Apply CLAHE for contrast enhancement (handles varying lighting)
        clip_limit = self.ocr_settings.get('clip_limit', 2.0)
        tile_size = self.ocr_settings.get('tile_grid_size', 8)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
        enhanced_frame = clahe.apply(gray_frame)

        # Apply adaptive thresholding for better OCR across varying conditions
        block_size = self.ocr_settings.get('block_size', 11)
        # Ensure block_size is odd
        if block_size % 2 == 0:
            block_size += 1
        c_constant = self.ocr_settings.get('c_constant', 2)

        thresh_frame = cv2.adaptiveThreshold(
            enhanced_frame, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=block_size,
            C=c_constant
        )

        # Extract text using pytesseract (psm 7 = single line of text)
        raw_text = pytesseract.image_to_string(
            thresh_frame,
            config='--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789.'
        ).strip()

        return raw_text

    def extract_temperature(self, frame, roi):
        """Extract and validate temperature from a single ROI."""
        raw_text = self.extract_from_roi(frame, roi)
        sensor_name = roi.get('name', f"Sensor {roi['id']}")

        if raw_text is None:
            return None

        formatted_temp = self.format_temperature(raw_text)
        if formatted_temp is None:
            return None

        try:
            temp_value = float(formatted_temp)
            if self.temp_min <= temp_value <= self.temp_max:
                return {
                    'sensor_id': roi['id'],
                    'sensor_name': sensor_name,
                    'temperature': temp_value,
                    'raw_text': raw_text,
                    'valid': True
                }
            else:
                return {
                    'sensor_id': roi['id'],
                    'sensor_name': sensor_name,
                    'temperature': temp_value,
                    'raw_text': raw_text,
                    'valid': False,
                    'reason': f'Out of range ({self.temp_min}-{self.temp_max})'
                }
        except ValueError:
            return {
                'sensor_id': roi['id'],
                'sensor_name': sensor_name,
                'temperature': None,
                'raw_text': raw_text,
                'valid': False,
                'reason': 'Invalid format'
            }

    def extract_all_temperatures(self, frame, rois, max_workers=4):
        """Extract temperatures from all ROIs in a frame using parallel processing.

        Args:
            frame: The video frame to process
            rois: List of ROI definitions
            max_workers: Maximum number of parallel OCR threads (default 4)
        """
        results = []

        # Use ThreadPoolExecutor for parallel OCR processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all ROI extraction tasks
            future_to_roi = {
                executor.submit(self.extract_temperature, frame, roi): roi
                for roi in rois
            }

            # Collect results as they complete
            for future in as_completed(future_to_roi):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    roi = future_to_roi[future]
                    results.append({
                        'sensor_id': roi['id'],
                        'sensor_name': roi.get('name', f"Sensor {roi['id']}"),
                        'temperature': None,
                        'raw_text': '',
                        'valid': False,
                        'reason': f'Processing error: {str(e)}'
                    })

        # Sort by sensor_id for consistent ordering
        results.sort(key=lambda r: r['sensor_id'])
        return results

    def get_valid_readings(self, frame, rois):
        """Get only valid temperature readings from all ROIs."""
        all_results = self.extract_all_temperatures(frame, rois)
        return [r for r in all_results if r.get('valid', False)]

    def _encode_image(self, img):
        """Encode an image to base64 PNG string."""
        _, buffer = cv2.imencode('.png', img)
        return base64.b64encode(buffer).decode('utf-8')

    def extract_temperature_debug(self, frame, roi):
        """Extract temperature with debug images for visualization.

        Returns dict with temperature data plus base64-encoded debug images.
        """
        x, y, w, h = roi['x'], roi['y'], roi['width'], roi['height']
        sensor_name = roi.get('name', f"Sensor {roi['id']}")

        if x < 0 or y < 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
            return {
                'sensor_id': roi['id'],
                'sensor_name': sensor_name,
                'valid': False,
                'reason': 'ROI out of bounds',
                'debug_images': {}
            }

        roi_frame = frame[y:y+h, x:x+w]

        # Get settings
        clip_limit = self.ocr_settings.get('clip_limit', 2.0)
        tile_size = self.ocr_settings.get('tile_grid_size', 8)
        block_size = self.ocr_settings.get('block_size', 11)
        if block_size % 2 == 0:
            block_size += 1
        c_constant = self.ocr_settings.get('c_constant', 2)

        # Convert to grayscale
        gray_frame = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)

        # Apply CLAHE
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
        enhanced_frame = clahe.apply(gray_frame)

        # Apply adaptive thresholding
        thresh_frame = cv2.adaptiveThreshold(
            enhanced_frame, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=block_size,
            C=c_constant
        )

        # Extract text
        raw_text = pytesseract.image_to_string(
            thresh_frame,
            config='--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789.'
        ).strip()

        # Encode debug images to base64
        debug_images = {
            'original': self._encode_image(roi_frame),
            'grayscale': self._encode_image(gray_frame),
            'enhanced': self._encode_image(enhanced_frame),
            'threshold': self._encode_image(thresh_frame)
        }

        # Format and validate temperature
        formatted_temp = self.format_temperature(raw_text)
        result = {
            'sensor_id': roi['id'],
            'sensor_name': sensor_name,
            'raw_text': raw_text,
            'debug_images': debug_images
        }

        if formatted_temp is None:
            result['temperature'] = None
            result['valid'] = False
            result['reason'] = 'Could not parse temperature'
        else:
            try:
                temp_value = float(formatted_temp)
                result['temperature'] = temp_value
                if self.temp_min <= temp_value <= self.temp_max:
                    result['valid'] = True
                else:
                    result['valid'] = False
                    result['reason'] = f'Out of range ({self.temp_min}-{self.temp_max})'
            except ValueError:
                result['temperature'] = None
                result['valid'] = False
                result['reason'] = 'Invalid format'

        return result

    def extract_all_temperatures_debug(self, frame, rois):
        """Extract temperatures from all ROIs with debug images."""
        results = []
        for roi in rois:
            result = self.extract_temperature_debug(frame, roi)
            results.append(result)
        results.sort(key=lambda r: r['sensor_id'])
        return results
