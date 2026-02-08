import cv2
import numpy as np
import time
import threading
from datetime import datetime
from flask import Response, jsonify

class FocusDetector:
    def __init__(self):
        # Initialize face and eye detectors
        try:
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        except Exception as e:
            print(f"Error loading Haar cascades: {e}")
            # Try alternative paths
            self.face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
            self.eye_cascade = cv2.CascadeClassifier('haascade_eye.xml')
        
        # Focus tracking variables
        self.focus_start_time = None
        self.total_focus_time = 0
        self.low_focus_start_time = None
        self.focus_log = []        # per-second session log
        self.last_log_time = None  # for 1-sec logging
        self.current_focus_score = 0
        self.session_start_time = None
        self.is_running = False
        self.session_results = {}
        self.cap = None
        
        # Variables for warning count and display
        self.warning_count = 0
        self.last_warning_time = 0

    def calculate_focus_score(self, frame, faces):
        """Calculate focus score based on face and eye detection"""
        if len(faces) == 0:
            return 0.0  # No face detected
        
        focus_score = 0.0
        for (x, y, w, h) in faces:
            # Base score for face detection
            focus_score += 0.3
            
            # ROI for eyes
            roi_gray = frame[y:y+h, x:x+w]
            eyes = self.eye_cascade.detectMultiScale(roi_gray, 1.1, 4)
            
            # Add score for eyes detected
            if len(eyes) >= 2:
                focus_score += 0.4
            elif len(eyes) == 1:
                focus_score += 0.2
            
        return min(focus_score, 1.0)  # Cap at 1.0

    def generate_frames(self):
        """Generate frames with focus detection for video streaming"""
        print("Starting frame generation. Attempting to open webcam (camera 0)...")
        self.cap = cv2.VideoCapture(0)
        
        # Try alternative camera index if 0 fails
        if not self.cap.isOpened():
            print("Camera 0 failed. Trying camera 1...")
            self.cap = cv2.VideoCapture(1)
        
        if not self.cap.isOpened():
            print("Error: Could not open webcam on indices 0 or 1. Camera may be disconnected or in use.")
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + 
                   self._generate_error_frame("Camera not available. Check if camera is connected.") + 
                   b'\r\n')
            return
        
        self.is_running = True
        self.session_start_time = time.time()
        session_start_time = self.session_start_time
        focus_scores = []
        
        try:
            while self.is_running:
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                # Convert to grayscale for detection
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Detect faces
                faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
                
                # Calculate focus score
                self.current_focus_score = self.calculate_focus_score(gray, faces)
                focus_scores.append(self.current_focus_score)
                
                # Update focus tracking
                if self.current_focus_score > 0.7:  # Threshold for being "focused"
                    if self.focus_start_time is None:
                        self.focus_start_time = time.time()
                    # Reset low focus timer and warning on recovery
                    self.low_focus_start_time = None
                else:
                    if self.focus_start_time is not None:
                        focus_duration = time.time() - self.focus_start_time
                        self.total_focus_time += focus_duration
                        self.focus_start_time = None
                
                # Check for continuous low focus to issue a warning
                if self.current_focus_score < 0.3:
                    if self.low_focus_start_time is None:
                        self.low_focus_start_time = time.time()
                    elif time.time() - self.low_focus_start_time >= 5:
                        self.warning_count += 1
                        
                        self.low_focus_start_time = None
                        self.last_warning_time = time.time()
                else:
                    # Reset the low focus timer if focus recovers
                    self.low_focus_start_time = None
                    
                # Draw info on frame
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                
                cv2.putText(frame, f"Focus: {self.current_focus_score:.2f}", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                if self.focus_start_time:
                    focus_duration = time.time() - self.focus_start_time
                    cv2.putText(frame, f"Focused: {focus_duration:.1f}s", (10, 60), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                
                # Display warning message for a limited time
                if time.time() - self.last_warning_time < 3: # Display for 3 seconds
                    cv2.putText(frame, "Warning: Low Focus", (10, 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                cv2.putText(frame, f"Warnings: {self.warning_count}", (10, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                # Stop the session if warnings exceed 1 (i.e., after the 2nd warning)
                if self.warning_count >=2 :
                    self.is_running = False
                    break
                    
                # Encode frame for streaming
                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
                time.sleep(0.03)  # Faster frame rate for smoother video
                
        except Exception as e:
            print(f"Error in generate_frames: {e}")
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + 
                   self._generate_error_frame("Camera error") + 
                   b'\r\n')
        finally:
            # Cleanup
            self._cleanup()
            
            # Calculate final metrics
            session_duration = time.time() - session_start_time
            avg_focus = np.mean(focus_scores) if focus_scores else 0
            
            self.session_results = {
                'total_focus_time': self.total_focus_time,
                'average_focus_score': avg_focus,
                'focus_percentage': (self.total_focus_time/session_duration)*100 if session_duration > 0 else 0,
                'session_duration': session_duration
            }
        
            print(f"\nSession Summary:")
            print(f"Total session time: {session_duration:.1f} seconds")
            print(f"Total focused time: {self.total_focus_time:.1f} seconds")
            print(f"Average focus score: {avg_focus:.2f}")
            print(f"Focus percentage: {(self.total_focus_time/session_duration)*100:.1f}%")
        
        black_frame = np.zeros((480, 640, 3), dtype=np.uint8)  # 480x640 black
        ret, buffer = cv2.imencode('.jpg', black_frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    def _generate_error_frame(self, message):
        """Generate an error frame with message"""
        frame = np.zeros((300, 500, 3), dtype=np.uint8)
        cv2.putText(frame, message, (50, 150), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        ret, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes()

    def _cleanup(self):
        """Clean up resources"""
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

# Create a global detector instance
detector = FocusDetector()

# Flask routes for focus detection
def init_focus_routes(app):
    """Initialize focus detection routes with the Flask app"""
    
    @app.route('/get_focus_score')
    def get_focus_score():
        return jsonify({'focus_score': detector.current_focus_score})
    
    @app.route('/video_feed')
    def video_feed():
        return Response(detector.generate_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    
    @app.route('/start_session')
    def start_session():
        # Reset detector for new session
        detector.__init__()
        detector.is_running = True
        return jsonify({'status': 'session started'})
    @app.route('/warning_status')
    def warning_status():
        return jsonify({'warnings':detector.warning_count})
    @app.route('/stop_session')
    def stop_session():
        detector.is_running = False
        # Wait briefly for the generator to finish and populate session_results.
        # If it doesn't appear within a timeout, compute a sensible fallback.
        timeout = 5.0
        waited = 0.0
        interval = 0.2
        while not detector.session_results and waited < timeout:
            time.sleep(interval)
            waited += interval

        # If still empty, compute fallback results from current detector state
        if not detector.session_results:
            now = time.time()
            session_duration = 0
            if getattr(detector, 'session_start_time', None):
                session_duration = now - detector.session_start_time

            avg_focus = detector.current_focus_score or 0
            total_focus = detector.total_focus_time or 0
            focus_pct = (total_focus / session_duration) * 100 if session_duration > 0 else 0

            detector.session_results = {
                'total_focus_time': total_focus,
                'average_focus_score': avg_focus,
                'focus_percentage': focus_pct,
                'session_duration': session_duration
            }

        return jsonify(detector.session_results)
    
    @app.route('/focus_status')
    def focus_status():
        status = "not focused"
        if detector.current_focus_score > 0.7:
            status = "focused"
        elif detector.current_focus_score > 0.3:
            status = "partially focused"
            
        return jsonify({
            'is_running': detector.is_running,
            'focus_score': round(detector.current_focus_score,2),
            'status': status,
            'focus_duration': detector.total_focus_time,
            'warnings': detector.warning_count,
        })
