from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()

class AccountsAPITests(APITestCase):
    def test_signup_successful(self):
        url = "/api/auth/signup/"
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "strongpassword123"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "User created successfully")
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_signup_missing_fields(self):
        url = "/api/auth/signup/"
        data = {
            "username": "newuser",
            "email": ""
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_signup_duplicate_username(self):
        User.objects.create_user(username="existinguser", email="existing@example.com", password="password123")
        url = "/api/auth/signup/"
        data = {
            "username": "existinguser",
            "email": "another@example.com",
            "password": "strongpassword123"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Username is already taken.")

