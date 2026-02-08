from flask import Flask, request, jsonify
import pandas as pd
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from pymongo import MongoClient
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
import os

app = Flask(__name__)

# MongoDB setup
client = MongoClient('mongodb://localhost:27017')
db = client['Study-snap']
data_collection = db['data']

# Initialize model with better hyperparameters
reg_model = RandomForestRegressor(
    n_estimators=50,
    max_depth=3,
    min_samples_split=5,
    random_state=32,
    n_jobs=-1
)
def preprocess_user_data(user_data_list):
    """Process all documents for a user and flatten sessions"""
    sessions = []
    for user_data in user_data_list:
        parent_date = user_data.get('date')
        if not parent_date:
            continue

        for session in user_data.get('sessions', []):
            try:
                sessions.append({
                    'date': parent_date,
                    'session_number': int(session['session_number']),
                    'duration_completed': float(session['duration_completed']),
                    'weekday': datetime.strptime(parent_date, '%Y-%m-%d').weekday()
                    
                    
                })
            except (KeyError, ValueError, TypeError):
                continue
    
    return sessions


def create_features(df):
    """Generate predictive features from raw data"""
    df['date'] = pd.to_datetime(df['date'])
    df['day_of_month'] = df['date'].dt.day
    df['month'] = df['date'].dt.month
    
    return df


def train_and_predict(username, target_date):
    """Train on full user history and predict for a given date,
    then apply a strategic nudge towards the target duration."""
    try:
        # Fetch ALL data for user
        user_data_list = list(data_collection.find(
            {'username': username},
            {'sessions': 1, 'date': 1, 'username': 1}
        ))
        
        print(f"Fetched {len(user_data_list)} documents for {username}")
        if not user_data_list:
            print('No user data found, returning 25')
            return 25  # fallback if no data

        # Preprocess & clean
        sessions = preprocess_user_data(user_data_list)
        df = pd.DataFrame(sessions)
        
        if df.empty:
            print('Empty data frame, returning 25')
            return 25

        df = create_features(df)
        print(df)

        # Train model on all history
        features = ['session_number',
                    'day_of_month', 'month', 'weekday']
        X = df[features]
        y = df['duration_completed']
        
        reg_model.fit(X, y)
        
        # Calculate R² score (for your reference)
        default_score = reg_model.score(X, y)
        print(f"Model's R² Score: {default_score:.4f}")
        
        # Prepare prediction for the next session
        target_dt = datetime.strptime(target_date, '%Y-%m-%d')
        last_session = df.iloc[-1]
        
        predict_features = {
            'session_number': last_session['session_number'] + 1,
            'day_of_month': target_dt.day,
            'month': target_dt.month,
            'weekday': target_dt.weekday()
        }
        
        df_pred = pd.DataFrame([predict_features])
        raw_prediction = reg_model.predict(df_pred)[0]
        
        # --- NEW STRATEGIC LOGIC ---
        
        # Define your growth parameters
        target_duration = 30
        increment = 1 # The number of minutes to add
        
        # The recommended duration is the max of the raw prediction or
        # the last completed duration plus a small increment.
        # This nudges the user to improve from their last session.
        last_completed_duration = df['duration_completed'].iloc[-1]
        
        recommended_duration = max(raw_prediction, last_completed_duration + increment)
        
        # Ensure the final duration is between 15 and 30 minutes
        final_duration = max(15, min(recommended_duration, target_duration))
        
        print(f"Raw prediction: {raw_prediction:.2f}")
        print(f"Final recommended duration: {final_duration:.2f}")
        
        return final_duration
    
    except Exception as e:
        print(f"Prediction error for {username}: {str(e)}")
        return 25