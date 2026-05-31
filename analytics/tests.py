from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from unittest.mock import patch, MagicMock, ANY
from rest_framework.test import APIClient

User = get_user_model()

class AIChatAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpassword123"
        )
        self.chat_url = "/api/analytics/chat/"

    def test_unauthenticated_request_returns_401(self):
        """
        Unauthenticated requests must be blocked.
        """
        response = self.client.post(self.chat_url, {"message": "hello"})
        self.assertEqual(response.status_code, 401)

    @override_settings(GEMINI_API_KEY="")
    def test_missing_gemini_api_key_returns_500(self):
        """
        Missing GEMINI_API_KEY setting should trigger a 500 error.
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.chat_url, {"message": "hello"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.data)
        self.assertIn("Gemini API Key is not configured", response.data["error"])

    @override_settings(GEMINI_API_KEY="fake-key-123")
    def test_missing_message_returns_400(self):
        """
        Requests without a message parameter must return 400.
        """
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.chat_url, {})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

    @override_settings(GEMINI_API_KEY="fake-key-123")
    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_successful_gemini_chat_returns_200(self, mock_model_class, mock_configure):
        """
        Authenticated valid requests must invoke the Gemini SDK and return the AI text.
        """
        self.client.force_authenticate(user=self.user)

        # Mock Model Instance and response
        mock_model_instance = MagicMock()
        mock_chat_session = MagicMock()
        mock_response = MagicMock()
        
        mock_response.text = "Mocked financial guidance from Gemini assistant."
        mock_chat_session.send_message.return_value = mock_response
        mock_model_instance.start_chat.return_value = mock_chat_session
        mock_model_class.return_value = mock_model_instance

        payload = {
            "message": "Give me a summary of my budget",
            "history": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "how can I help?"}
            ]
        }

        response = self.client.post(self.chat_url, payload, format="json")
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("response", response.data)
        self.assertEqual(response.data["response"], "Mocked financial guidance from Gemini assistant.")
        
        # Verify calls were made correctly
        mock_configure.assert_called_once_with(api_key="fake-key-123")
        mock_model_class.assert_called_once_with(
            model_name="gemini-2.5-flash",
            system_instruction=ANY
        )
        mock_model_instance.start_chat.assert_called_once_with(history=[
            {"role": "user", "parts": ["hello"]},
            {"role": "model", "parts": ["how can I help?"]}
        ])
        mock_chat_session.send_message.assert_called_once()


class BudgetProjectionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser_budget",
            email="testuser_budget@example.com",
            password="testpassword123"
        )
        self.client.force_authenticate(user=self.user)
        
        from transactions.models import Category
        self.category = Category.objects.create(
            name="Dining",
            type="expense"
        )

    def test_budget_projections_current_month(self):
        """
        Verify projection calculations for the current month.
        """
        from datetime import date
        import calendar
        from analytics.models import Budget
        from transactions.models import Transaction

        today = date.today()
        current_month_str = today.strftime("%Y-%m")
        month_date = today.replace(day=1)

        # Create a budget of 3000
        budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            month=month_date,
            amount=3000.00
        )

        # Create an expense of 1000 today
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            type="expense",
            amount=1000.00,
            date=today,
            description="Dinner out"
        )

        response = self.client.get(f"/api/analytics/budget-status/?month={current_month_str}")
        self.assertEqual(response.status_code, 200)
        
        budgets_data = response.data.get("budgets", [])
        self.assertEqual(len(budgets_data), 1)
        
        b_data = budgets_data[0]
        self.assertEqual(b_data["actual_spent"], 1000.00)
        self.assertEqual(b_data["budget_amount"], 3000.00)
        
        # Calculate expected projected values dynamically
        total_days = calendar.monthrange(today.year, today.month)[1]
        elapsed_days = today.day
        expected_projected = round((1000.00 / elapsed_days) * total_days, 2)
        
        self.assertEqual(b_data["projected_spent"], expected_projected)
        self.assertEqual(b_data["is_projected_to_exceed"], expected_projected > 3000.00)

    def test_budget_projections_past_month(self):
        """
        Verify that past months are treated as fully completed, so projection matches actual.
        """
        from datetime import date, timedelta
        import calendar
        from analytics.models import Budget
        from transactions.models import Transaction

        # Last month date logic
        today = date.today()
        first_of_this_month = today.replace(day=1)
        last_month_any_day = first_of_this_month - timedelta(days=15)
        last_month_start = last_month_any_day.replace(day=1)
        last_month_str = last_month_start.strftime("%Y-%m")

        # Create a budget for last month
        Budget.objects.create(
            user=self.user,
            category=self.category,
            month=last_month_start,
            amount=2000.00
        )

        # Create an expense in last month
        Transaction.objects.create(
            user=self.user,
            category=self.category,
            type="expense",
            amount=500.00,
            date=last_month_start,
            description="Last month expense"
        )

        response = self.client.get(f"/api/analytics/budget-status/?month={last_month_str}")
        self.assertEqual(response.status_code, 200)
        
        budgets_data = response.data.get("budgets", [])
        self.assertEqual(len(budgets_data), 1)
        
        b_data = budgets_data[0]
        self.assertEqual(b_data["actual_spent"], 500.00)
        self.assertEqual(b_data["projected_spent"], 500.00)
        self.assertEqual(b_data["projected_overspend"], 0.00)
        self.assertEqual(b_data["is_projected_to_exceed"], False)
