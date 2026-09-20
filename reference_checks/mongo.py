import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "finedge")

_client = MongoClient(MONGO_URI)
_db = _client[MONGO_DB_NAME]


def get_reference_checks_collection():
    return _db["reference_checks"]
