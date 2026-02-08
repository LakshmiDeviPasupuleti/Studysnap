from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["Study-snap"]
users = db["users"]
def handle_login(username,password):
    existing_user=users.find_one({'username':username})
    print('almost there')
    if existing_user:
        if existing_user["password"] == password:
            return {"status": "success", "message": f"Welcome back, {username}!"}
        else:
            return {"status": "error", "message": "Incorrect password."}
    else:
        users.insert_one({"username": username, "password": password})
        return {"status": "success", "message": f"Account created for {username}!"}
