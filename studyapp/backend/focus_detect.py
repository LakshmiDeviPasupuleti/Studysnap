import cv2
import numpy as np
import time
from datetime import datetime

class FocusDetector:
    def __init__(self):
        # Initialize face and eye detectors
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        
        # Focus tracking variables
        self.focus_start_time = None
        self.total_focus_time = 0
        self.current_session_score = 0
        self.focus_history = []

        # Live state for UI/APIs (additive only)
        self.latest_focus_score = 0.0
        self.current_status = "Session Ended"
        self.is_focused = False
        self.focus_threshold = 0.7
        self.alerts_log = []
        self._last_alert_ts = 0
        self._alert_cooldown_sec = 5

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
            eyes = self.eye_cascade.detectMultiScale(roi_gray)
            
            # Add score for eyes detected
            if len(eyes) >= 2:
                focus_score += 0.4
            elif len(eyes) == 1:
                focus_score += 0.2
        return min(focus_score, 1.0)

    def _maybe_alert_unfocused(self):
        now = time.time()
        if now - self._last_alert_ts >= self._alert_cooldown_sec:
            ts = datetime.now().strftime("%H:%M:%S")
            self.alerts_log.append(f"Not focused @ {ts}")
            self._last_alert_ts = now

    def get_state(self):
        """Snapshot for a web route if you want to expose it."""
        return {
            "focus_score": float(self.latest_focus_score),
            "status": self.current_status,
            "alerts": self.alerts_log[-20:],
            "total_focus_time": float(self.total_focus_time)
        }

    def run_focus_detection(self, session_duration_minutes=25):
        """Main function to run focus detection"""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open webcam")
            return
        
        session_end_time = time.time() + (session_duration_minutes * 60)
        frame_count = 0
        focus_scores = []
        
        print(f"Starting focus detection session for {session_duration_minutes} minutes")
        print("Press 'q' to quit early")
        
        try:
            while time.time() < session_end_time:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Convert to grayscale for detection
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Detect faces
                faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
                
                # Calculate focus score
                focus_score = self.calculate_focus_score(gray, faces)
                focus_scores.append(focus_score)

                # Maintain status/alerts (additive)
                self.latest_focus_score = float(focus_score)
                was_focused = self.is_focused
                self.is_focused = focus_score > self.focus_threshold
                self.current_status = "Focused" if self.is_focused else "Not Focused"
                if not self.is_focused:
                    self._maybe_alert_unfocused()

                # Original focus tracking
                if focus_score > 0.7:  # Threshold for being "focused"
                    if self.focus_start_time is None:
                        self.focus_start_time = time.time()
                else:
                    if self.focus_start_time is not None:
                        focus_duration = time.time() - self.focus_start_time
                        self.total_focus_time += focus_duration
                        self.focus_start_time = None
                
                # Display info on frame
                self._draw_info(frame, focus_score, faces)
                
                # Show frame
                cv2.imshow('Focus Detection', frame)
                
                # Break on 'q' key
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
                frame_count += 1
                time.sleep(0.1)  # Reduce CPU usage
                
        finally:
            # Cleanup
            cap.release()
            cv2.destroyAllWindows()
            
            # Calculate final metrics
            avg_focus = np.mean(focus_scores) if focus_scores else 0
            total_session_time = session_duration_minutes * 60
            
            print(f"\nSession Summary:")
            print(f"Total session time: {session_duration_minutes} minutes")
            print(f"Total focused time: {self.total_focus_time:.1f} seconds")
            print(f"Average focus score: {avg_focus:.2f}")
            print(f"Focus percentage: {(self.total_focus_time/total_session_time)*100:.1f}%")
            
            return {
                'total_focus_time': self.total_focus_time,
                'average_focus_score': avg_focus,
                'focus_percentage': (self.total_focus_time/total_session_time)*100,
                'session_duration': session_duration_minutes
            }

    def _draw_info(self, frame, focus_score, faces):
        """Draw detection information on the frame"""
        # Draw face rectangles
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
        
        # Display focus score
        cv2.putText(frame, f"Focus: {focus_score:.2f}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Display timer
        if self.focus_start_time:
            focus_duration = time.time() - self.focus_start_time
            cv2.putText(frame, f"Focused: {focus_duration:.1f}s", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

# Usage example
if __name__ == "__main__":
    detector = FocusDetector()
    session_results = detector.run_focus_detection(session_duration_minutes=25)
    # You can save these results to your database
    print("Session results:", session_results)
