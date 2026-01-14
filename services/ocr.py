import cv2
import pytesseract
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed


class OCRService:
    """Service for extracting temperature readings from video frames using OCR."""

    def __init__(self, temp_min=5, temp_max=37):
        self.temp_min = temp_min
        self.temp_max = temp_max
        # Set tesseract path based on platform
        if platform.system() == 'Windows':
            pytesseract.pytesseract.tesseract_cmd = r'C:\Users\fma017\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
        # On Linux/Ubuntu, tesseract is typically in PATH at /usr/bin/tesseract

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
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_frame = clahe.apply(gray_frame)

        # Apply adaptive thresholding for better OCR across varying conditions
        thresh_frame = cv2.adaptiveThreshold(
            enhanced_frame, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=11,
            C=2
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
                    'temperature': temp_value,
                    'raw_text': raw_text,
                    'valid': True
                }
            else:
                return {
                    'sensor_id': roi['id'],
                    'temperature': temp_value,
                    'raw_text': raw_text,
                    'valid': False,
                    'reason': f'Out of range ({self.temp_min}-{self.temp_max})'
                }
        except ValueError:
            return {
                'sensor_id': roi['id'],
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
