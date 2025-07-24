import os
from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

class MongoDBClient:
    def __init__(self):
        try:
            mongo_uri = os.getenv("MONGODB_URI")
            if not mongo_uri:
                raise ValueError("MONGODB_URI not found in environment variables")

            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command("ping")  # Check connection
            self.db = self.client["interview_db"]
        except Exception as e:
            raise RuntimeError(f"Failed to connect to MongoDB: {e}")

    def get_collection(self, name: str):
        return self.db[name]

    def get_user_session_collection(self):
        return self.db["user_sessions"]

    def get_user_session(self, user_id: str):
        return self.get_user_session_collection().find_one({"user_id": user_id})

    def update_user_session(self, user_id: str, data: dict):
        self.get_user_session_collection().update_one(
            {"user_id": user_id},
            {"$set": data},
            upsert=True
        )

# Singleton export
mongo_client = MongoDBClient()
get_collection = mongo_client.get_collection
get_user_session = mongo_client.get_user_session
update_user_session = mongo_client.update_user_session
