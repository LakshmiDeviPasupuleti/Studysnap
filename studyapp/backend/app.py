from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os

# Camera/focus routes you already have (provides /video_feed, /get_focus_score, /start_session, /stop_session)
from focus_detection import init_focus_routes

app = Flask(__name__)
CORS(app)

# --- Point Flask to your dashboard folder ---
FRONT_DIR = r"C:\Users\vasud\OneDrive\Desktop\assignment studyapp\studyapp"   # <-- serving updated dashboard
print("Serving frontend from:", FRONT_DIR)

# Register focus/camera endpoints
init_focus_routes(app)

# ---------- PAGES ----------
# Open the dashboard by default at /
@app.get("/")
def serve_dashboard_root():
    return send_from_directory(FRONT_DIR, "dashboard.html")

@app.get("/dashboard")
def serve_dashboard():
    return send_from_directory(FRONT_DIR, "dashboard.html")

# (optional) if you also want to see index.html from the same folder
@app.get("/index")
def serve_index():
    return send_from_directory(FRONT_DIR, "index.html")

# Serve static assets next to dashboard.html (script.js, css, images/*, etc.)
@app.get("/<path:asset_path>")
def serve_assets(asset_path: str):
    file_path = os.path.join(FRONT_DIR, asset_path)
    if os.path.isfile(file_path):
        return send_from_directory(FRONT_DIR, asset_path)
    return jsonify({"error": "Not found"}), 404

if __name__ == "__main__":
    # no reloader to avoid Windows socket errors
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
