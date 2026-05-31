from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import date
from .models import Category, Transaction

User = get_user_model()

class TransactionAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="txuser", password="txpassword")
        self.client.force_authenticate(user=self.user)

        self.c_income = Category.objects.create(name="Salary", type="income")
        self.c_expense1 = Category.objects.create(name="Food", type="expense")
        self.c_expense2 = Category.objects.create(name="Bills", type="expense")

        # 1. Income transaction on 2026-05-01
        self.t1 = Transaction.objects.create(
            user=self.user,
            amount=50000.0,
            type="income",
            category=self.c_income,
            date=date(2026, 5, 1),
            description="Monthly salary"
        )
        # 2. Food expense transaction on 2026-05-05
        self.t2 = Transaction.objects.create(
            user=self.user,
            amount=150.0,
            type="expense",
            category=self.c_expense1,
            date=date(2026, 5, 5),
            description="Lunch at restaurant"
        )
        # 3. Bill expense transaction on 2026-05-10
        self.t3 = Transaction.objects.create(
            user=self.user,
            amount=1200.0,
            type="expense",
            category=self.c_expense2,
            date=date(2026, 5, 10),
            description="Electricity bill payment"
        )
        self.url = "/api/transactions/"

    def test_get_transactions_default_order(self):
        # Default order is date DESC
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 3)
        data = response.data["data"]
        # Order should be t3 (May 10), t2 (May 5), t1 (May 1)
        self.assertEqual(data[0]["id"], self.t3.id)
        self.assertEqual(data[1]["id"], self.t2.id)
        self.assertEqual(data[2]["id"], self.t1.id)

    def test_search_by_description(self):
        # Search "bill"
        response = self.client.get(self.url, {"search": "bill"})
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["data"][0]["description"], "Electricity bill payment")

    def test_search_by_category_name(self):
        # Search "Food"
        response = self.client.get(self.url, {"search": "Food"})
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["data"][0]["category_name"], "Food")

    def test_filter_by_type(self):
        response = self.client.get(self.url, {"type": "expense"})
        self.assertEqual(response.data["total"], 2)

    def test_filter_by_category(self):
        response = self.client.get(self.url, {"category": self.c_expense1.id})
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["data"][0]["id"], self.t2.id)

    def test_sorting_by_amount(self):
        # Sort by amount ASC
        response = self.client.get(self.url, {"sort_by": "amount", "order": "asc"})
        data = response.data["data"]
        # Order: 150 (Food), 1200 (Bills), 50000 (Salary)
        self.assertEqual(float(data[0]["amount"]), 150.0)
        self.assertEqual(float(data[1]["amount"]), 1200.0)
        self.assertEqual(float(data[2]["amount"]), 50000.0)

    def test_pagination(self):
        # Limit 2
        response = self.client.get(self.url, {"limit": 2, "page": 1})
        self.assertEqual(len(response.data["data"]), 2)
        self.assertEqual(response.data["total"], 3)
