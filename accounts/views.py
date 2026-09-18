import datetime

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import JWTAuthentication
from accounts.mongo import get_users_collection


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"detail": "Email and password are required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = get_users_collection().find_one({"email": email})

        if not user or not check_password(password, user.get("password", "")):
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        payload = {
            "id": str(user["_id"]),
            "email": user["email"],
            "role": user.get("role"),
            "exp": datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=15),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        return Response({"token": token}, status=status.HTTP_200_OK)


class MeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "email": user.email,
                "name": user.name,
                "role": user.role,
            },
            status=status.HTTP_200_OK,
        )
