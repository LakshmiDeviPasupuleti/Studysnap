from pymongo import MongoClient
from datetime import datetime, timedelta
import statistics
from model import train_and_predict  # Import ML function

client = MongoClient('mongodb://localhost:27017')
db = client['Study-snap']
users = db['users']
data_collection = db['data']


def save(data):
    print('Saving session started')
    username = data['username']
    today = data['date']
    duration = data['duration_completed']

    # Check user exists
    if not users.find_one({'username': username}):
        return {"status": "error", "message": "User not found"}

    # Fetch existing sessions for TODAY (before adding new one)
    today_doc = data_collection.find_one({"username": username, "date": today})
    existing_sessions = today_doc.get("sessions", []) if today_doc else []
    
    # Check daily session limit
    if len(existing_sessions) >= 2:
        return {"status": "error", "message": "Daily session limit (2) reached"}

    # Session number
    session_number = len(existing_sessions) + 1

    # Calculate features using ONLY COMPLETED DAYS (before today)
    today_date = datetime.strptime(today, "%Y-%m-%d")
    
     # Final session of prev day

    # 2. Average last 4 COMPLETED days (2025-08-16 to 2025-08-19)
    last4_days_durations = []
    for i in range(1, 5):  # Days N-1, N-2, N-3, N-4
        target_date = (today_date - timedelta(days=i)).strftime("%Y-%m-%d")
        doc = data_collection.find_one({"username": username, "date": target_date})
        
        if doc:
            target_sessions = doc.get("sessions", [])
            if target_sessions:
                # Use final session duration for that COMPLETED day
                last4_days_durations.append(target_sessions[-1]["duration_completed"])
    
    # Calculate average (use only available history)
    if last4_days_durations:
        avg_last4 = round(statistics.mean(last4_days_durations), 2)
    else:
        avg_last4 = 0

    # Create new session with PROPERLY calculated features
    new_session = {
        "session_number": session_number,
        "duration_completed": duration,
   
        "avg_fourdays": avg_last4
    }

    # Update sessions array and save to DB
    updated_sessions = existing_sessions + [new_session]
    data_collection.update_one(
        {"username": username, "date": today},
        {"$set": {"sessions": updated_sessions}},
        upsert=True
    )

    # Train model on updated data
    print("Training model with updated data...")
    train_and_predict(username, today)

    return {"status": "success", "session": new_session}