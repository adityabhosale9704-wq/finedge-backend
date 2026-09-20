import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "finedge")

_client = MongoClient(MONGO_URI)
_db = _client[MONGO_DB_NAME]


def get_salary_structure_collection():
    return _db["salary_structure"]


def get_salary_revisions_collection():
    return _db["salary_revisions"]
