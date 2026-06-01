from django.shortcuts import render

# Create your views here.

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

User = get_user_model()

@api_view(['POST'])
def signup(request):
    data = request.data
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return Response({"error": "Please provide username, email, and password."}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username is already taken."}, status=400)

    if User.objects.filter(email=email).exists():
        return Response({"error": "Email is already registered."}, status=400)

    try:
        user = User.objects.create(
            username=username,
            email=email,
            password=make_password(password)
        )
        return Response({"message": "User created successfully"}, status=201)
    except Exception as e:
        return Response({"error": f"Failed to create user: {str(e)}"}, status=400)

from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

@api_view(['POST'])
def login(request):
    data = request.data

    user = authenticate(username=data['username'], password=data['password'])

    if user is None:
        return Response({"error": "Invalid credentials"}, status=400)

    refresh = RefreshToken.for_user(user)

    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh)
    })