import cv2
import requests
from requests.exceptions import RequestException
import numpy as np
import pytesseract
import time
from influxdb import InfluxDBClient

# Configuration for pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Users\fma017\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

# Initialize InfluxDB client
client = InfluxDBClient(host='10.239.99.73', port=8086, username='admin', password='hamsterpi', database='Anipill_data')

def format_temperature(raw_temp):
    temp_digits = ''.join(filter(str.isdigit, raw_temp))
    return f"{int(temp_digits[:-2]):02}.{int(temp_digits[-2:]):02}" if len(temp_digits) >= 3 else "00.00"

def extract_text_from_roi(frame, roi):
    x, y, w, h = roi
    roi_frame = frame[y:y+h, x:x+w]
    gray_frame = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
    _, thresh_frame = cv2.threshold(gray_frame, 200, 255, cv2.THRESH_BINARY_INV)
    cv2.imshow('Thresholded ROI', thresh_frame)
    
    cv2.waitKey(50) # Wait for 1 ms before moving on, so the window displays very briefly
    return pytesseract.image_to_string(thresh_frame, config='--psm 6').strip()

def draw_rois_and_extract_text(frame, sensor_rois):
    points = []
    for index, roi in enumerate(sensor_rois):
        sensor_text = extract_text_from_roi(frame, roi)
        formatted_temp = format_temperature(sensor_text)
        print(f"Sensor {index + 1}: {formatted_temp} (raw: {sensor_text})")
        cv2.rectangle(frame, (roi[0], roi[1]), (roi[0]+roi[2], roi[1]+roi[3]), (0, 255, 0), 2)
       
        if 5 <= float(formatted_temp) <= 37:
            point = {
                "measurement": "anipills",
                "tags": {
                    "sensor_id": f"sensor_{index + 1}"
                },
                "fields": {
                    "temperature": float(formatted_temp)
                },
                "time": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            points.append(point)
        else:
            print(f"Filtered out: Sensor {index + 1} temperature {formatted_temp} out of range.")

    # Write points to InfluxDB
    if points:  # Check if there are any points to write
        client.write_points(points)
    
    
def camera_feed_process(video_feed_url, username, password):
    processing_time = 10
    start_time = time.time()
    end_time = start_time + processing_time
    session = requests.Session()
    session.auth = (username, password)

    try:
        while time.time() < end_time:
            try:
                response = session.get(video_feed_url, stream = True, timeout=5)
                if response.status_code == 200:
                    buffer = b''
                    for chunk in response.iter_content(chunk_size=1024):
                        buffer += chunk
                        a = buffer.find(b'\xff\xd8')
                        b = buffer.find(b'\xff\xd9')
                        if a != -1 and b != -1:
                            jpg = buffer[a:b+2]
                            buffer = buffer[b+2:]
                            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                            if frame is not None:
                                process_frame(frame)  # Assume process_frame includes ROI drawing and text extraction
                            cv2.imshow('Frame with ROIs', frame)
                            if cv2.waitKey(1) & 0xFF == ord('q'):
                                break
            except RequestException as e:
                print(f"Network request failed: {e}")
                break  # Exiting the loop on network failure
    except Exception as e:
        print(f"An error occurred: {e}")

        
        
        
def process_frame(frame):
   # Manually define the ROIs with space between them
   x1, y1 = 140, 29 # Starting position for the first ROI
   width, height = 95, 41  # The size of each ROI
   space_x, space_y = 110, 23  # The space between ROIs horizontally and vertically
   sensor_rois = [
   # Column 1
   # ROI 1 (top-left corner)
   (x1, y1, width, height),
   # ROI 2 (below ROI 1)
   (x1, y1 + height + space_y, width, height),
   # ROI 3 (below ROI 2)
   (x1, y1 + 2*(height + space_y), width -2, height),
   # ROI 4 (below ROI 3)
   (x1, y1+2  + 3*(height + space_y), width-3, height),

      # Column 2
      # ROI 5 (to the right of ROI 1)
      (x1 + width + space_x, y1, width, height),
      # ROI 6 (below ROI 5)
      (x1 + width + space_x, y1 + height + space_y, width, height),
      # ROI 7 (below ROI 6)
      (x1 + width + space_x, y1  + 2*(height + space_y), width, height),
      # ROI 8 (below ROI 7)
      (x1 + width + space_x, y1  + 3*(height + space_y), width, height),
      ]

   # Draw ROIs and extract text
   draw_rois_and_extract_text(frame, sensor_rois)

    

runtime = 60 * 60 *24 # run for 24 hours
 
start_time = time.time()


if __name__ == "__main__":
    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            if elapsed >= runtime:
                print(f"Exiting: Runtime limit reached at {elapsed} seconds.")
                break

            print(f"Elapsed Time: {elapsed} seconds - Starting camera feed check...")
            camera_feed_process("http://10.239.99.103/cam_pic.php", "admin", "hamsterpi")
            print("Finished camera feed check, pausing for 15 minutes...")
            # If there's time left, sleep, otherwise exit
            if time.time() - start_time + 10 < runtime:
                time.sleep(60*15)  # Sleep for the pause
                
                print("Resuming...")
            else:
                print("Exiting: Insufficient time for another process cycle.")
                break
    except KeyboardInterrupt:
        print("Program stopped by user.")
    #finally:
        #cv2.destroyAllWindows()
       