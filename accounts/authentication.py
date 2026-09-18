import jwt
from bson import ObjectId
from bson.errors import InvalidId
from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

from accounts.mongo import get_users_collection


class MongoUser:
    def __init__(self, user_doc):
        self.id = str(user_doc["_id"])
        self.email = user_doc.get("email")
        self.name = user_doc.get("name")
        self.role = user_doc.get("role")
        self.is_authenticated = True


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ", 1)[1].strip()

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token has expired.")
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed("Invalid token.")

        user_id = payload.get("id")
        if not user_id:
            raise exceptions.AuthenticationFailed("Invalid token payload.")

        try:
            user_doc = get_users_collection().find_one({"_id": ObjectId(user_id)})
        except InvalidId:
            raise exceptions.AuthenticationFailed("Invalid token payload.")

        if not user_doc:
            raise exceptions.AuthenticationFailed("User not found.")

        return (MongoUser(user_doc), token)

    def authenticate_header(self, request):
        return "Bearer"
