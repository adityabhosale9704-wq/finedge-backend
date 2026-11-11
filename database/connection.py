"""One lazy MongoDB client shared by all backend features and setup commands."""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@lru_cache(maxsize=1)
def get_database():
    client = MongoClient(os.getenv("MONGO_URI"))
    return client[os.getenv("MONGO_DB_NAME", "finedge")]
