"""Run with python -m database.check_connection; never print connection credentials."""
from pymongo.errors import PyMongoError

from database.connection import get_database


def main():
    try:
        get_database().command("ping")
    except PyMongoError:
        print("Connection failed. Check MONGO_URI and MongoDB availability locally.")
        raise SystemExit(1) from None
    print("Connection successful!")


if __name__ == "__main__":
    main()
