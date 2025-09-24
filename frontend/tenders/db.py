# tenders/db.py
from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "tenderinsights")

mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DB]
tenders_collection = mongo_db["tenders"]
