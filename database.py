import pymongo
from info import MONGO_URI

# মঙ্গো ক্লায়েন্ট সেটআপ
client = pymongo.MongoClient(MONGO_URI)
db = client["video_bot_db"]
users_collection = db["users_settings"]

# ইউজার ডেটাবেসে এড করা (স্ট্যাটাসের জন্য)
def add_user(user_id):
    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({"user_id": user_id})

# মোট ইউজার সংখ্যা
def count_users():
    return users_collection.count_documents({})

# ক্যাপশন সেভ ও আনা
def save_caption(user_id, caption):
    users_collection.update_one({"user_id": user_id}, {"$set": {"caption": caption}}, upsert=True)

def get_caption(user_id):
    data = users_collection.find_one({"user_id": user_id})
    return data.get("caption") if data else None

# থাম্বনেইল সেভ, আনা ও ডিলিট করা
def save_thumbnail(user_id, thumb_path):
    users_collection.update_one({"user_id": user_id}, {"$set": {"thumbnail": thumb_path}}, upsert=True)

def get_thumbnail(user_id):
    data = users_collection.find_one({"user_id": user_id})
    return data.get("thumbnail") if data else None

def delete_thumbnail(user_id):
    users_collection.update_one({"user_id": user_id}, {"$unset": {"thumbnail": ""}})
