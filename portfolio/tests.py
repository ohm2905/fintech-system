from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import date
from .models import StockTransaction

User = get_user_model()

class StockTransactionAPITests(APITestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(username="testuser", password="testpassword")
        self.client.force_authenticate(user=self.user)
        
        # Create test transactions
        # 1. TCS BUY on 2026-05-10
        self.t1 = StockTransaction.objects.create(
            user=self.user,
            stock_name="TCS",
            transaction_type="BUY",
            quantity=10,
            price=3000.0,
            date=date(2026, 5, 10)
        )
        # 2. INFY BUY on 2026-05-15
        self.t2 = StockTransaction.objects.create(
            user=self.user,
            stock_name="INFY",
            transaction_type="BUY",
            quantity=5,
            price=1500.0,
            date=date(2026, 5, 15)
        )
        # 3. TCS SELL on 2026-05-20
        self.t3 = StockTransaction.objects.create(
            user=self.user,
            stock_name="TCS",
            transaction_type="SELL",
            quantity=2,
            price=3100.0,
            date=date(2026, 5, 20)
        )
        self.url = "/api/portfolio/transactions/"

    def test_get_transactions_default_order(self):
        # Default order should be date DESC, then id DESC
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Total count is 3
        self.assertEqual(response.data["total"], 3)
        transactions = response.data["data"]
        self.assertEqual(transactions[0]["id"], self.t3.id)
        self.assertEqual(transactions[1]["id"], self.t2.id)
        self.assertEqual(transactions[2]["id"], self.t1.id)

    def test_search_by_stock_name(self):
        # Search TCS
        response = self.client.get(self.url, {"search": "TCS"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 2)
        transactions = response.data["data"]
        self.assertEqual(transactions[0]["stock_name"], "TCS")
        self.assertEqual(transactions[1]["stock_name"], "TCS")

    def test_filter_by_date_range(self):
        # Start date filter (>= May 15)
        response = self.client.get(self.url, {"start_date": "2026-05-15"})
        self.assertEqual(response.data["total"], 2)
        
        # End date filter (<= May 15)
        response = self.client.get(self.url, {"end_date": "2026-05-15"})
        self.assertEqual(response.data["total"], 2)

        # Both
        response = self.client.get(self.url, {"start_date": "2026-05-11", "end_date": "2026-05-19"})
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["data"][0]["stock_name"], "INFY")

    def test_sorting_by_name(self):
        # Sort by stock_name ASC
        response = self.client.get(self.url, {"sort_by": "stock_name", "order": "asc"})
        transactions = response.data["data"]
        # INFY comes first, then TCS
        self.assertEqual(transactions[0]["stock_name"], "INFY")
        self.assertEqual(transactions[1]["stock_name"], "TCS")

    def test_pagination(self):
        # Limit to 2 rows per page, page 1
        response = self.client.get(self.url, {"limit": 2, "page": 1})
        self.assertEqual(len(response.data["data"]), 2)
        self.assertEqual(response.data["total"], 3)
        self.assertEqual(response.data["page"], 1)

        # Page 2
        response = self.client.get(self.url, {"limit": 2, "page": 2})
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["page"], 2)


class PortfolioSummaryAPITests(APITestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(username="testuser_p", password="testpassword")
        self.client.force_authenticate(user=self.user)
        
        # Create Portfolio summary records (holdings)
        from .models import Portfolio
        # 1. TCS
        Portfolio.objects.create(
            user=self.user,
            stock_name="TCS",
            quantity=10,
            buy_price=3000.0
        )
        # 2. INFY
        Portfolio.objects.create(
            user=self.user,
            stock_name="INFY",
            quantity=5,
            buy_price=1500.0
        )
        # 3. RELIANCE
        Portfolio.objects.create(
            user=self.user,
            stock_name="RELIANCE",
            quantity=8,
            buy_price=2400.0
        )
        self.url = "/api/portfolio/summary/"

    def test_summary_all_and_overall(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # All stocks returned (full unpaginated) in all_stocks
        self.assertEqual(len(response.data["all_stocks"]), 3)
        # Paged output default limit is 5, page is 1
        self.assertEqual(response.data["total"], 3)
        self.assertEqual(len(response.data["stocks"]), 3)

    def test_summary_search(self):
        # Search INFY
        response = self.client.get(self.url, {"search": "INFY"})
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["stocks"][0]["stock"], "INFY")

    def test_summary_sort(self):
        # Sort by buy_price ASC
        response = self.client.get(self.url, {"sort_by": "buy_price", "order": "asc"})
        stocks = response.data["stocks"]
        self.assertEqual(stocks[0]["stock"], "INFY")  # 1500
        self.assertEqual(stocks[1]["stock"], "RELIANCE")  # 2400
        self.assertEqual(stocks[2]["stock"], "TCS")  # 3000

        # Sort by quantity DESC
        response = self.client.get(self.url, {"sort_by": "quantity", "order": "desc"})
        stocks = response.data["stocks"]
        self.assertEqual(stocks[0]["stock"], "TCS")  # 10
        self.assertEqual(stocks[1]["stock"], "RELIANCE")  # 8
        self.assertEqual(stocks[2]["stock"], "INFY")  # 5

    def test_summary_pagination(self):
        # Limit 2
        response = self.client.get(self.url, {"limit": 2, "page": 1})
        self.assertEqual(response.data["total"], 3)
        self.assertEqual(len(response.data["stocks"]), 2)
        self.assertEqual(len(response.data["all_stocks"]), 3) # should still contain all stocks for chart


from unittest.mock import patch, MagicMock
import pandas as pd

class StockForecastAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser_f", password="testpassword")
        self.client.force_authenticate(user=self.user)
        self.url = "/api/portfolio/forecast/"

    def test_forecast_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(self.url, {"stock": "TCS"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_forecast_missing_param_returns_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('yfinance.Ticker')
    def test_forecast_success_returns_200(self, mock_ticker):
        mock_instance = MagicMock()
        
        # Generate 60 days of mock prices (dates index ending at 2026-05-30)
        dates = pd.date_range(end='2026-05-30', periods=60)
        mock_prices = [float(100 + i) for i in range(60)]
        mock_df = pd.DataFrame({'Close': mock_prices}, index=dates)
        
        mock_instance.history.return_value = mock_df
        mock_ticker.return_value = mock_instance

        response = self.client.get(self.url, {"stock": "TCS"})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["stock"], "TCS")
        self.assertEqual(response.data["current_price"], 159.0)  # last item is 100+59 = 159.0
        self.assertEqual(len(response.data["history_dates"]), 30)
        self.assertEqual(len(response.data["forecast_dates"]), 7)
        self.assertEqual(len(response.data["forecast_prices"]), 7)
        self.assertEqual(len(response.data["lower_bound"]), 7)
        self.assertEqual(len(response.data["upper_bound"]), 7)
        
        # OLS slope is 1.0, next day value should project to 160.0
        self.assertEqual(response.data["forecast_prices"][0], 160.0)


class StockSearchAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser_s", password="testpassword")
        self.client.force_authenticate(user=self.user)
        self.url = "/api/portfolio/search/"

    def test_search_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(self.url, {"q": "jio"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_search_empty_query_returns_empty_list(self):
        response = self.client.get(self.url, {"q": ""})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    @patch('requests.get')
    def test_search_success_filters_indian_equities(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "quotes": [
                {
                    "symbol": "JIOFIN.NS",
                    "shortname": "JIO FIN SERVICES LTD",
                    "quoteType": "EQUITY",
                    "longname": "Jio Financial Services Limited",
                    "exchDisp": "NSE"
                },
                {
                    "symbol": "000600.SZ",
                    "shortname": "HEBEI JIONTO ENERGY",
                    "quoteType": "EQUITY",
                    "exchDisp": "Shenzhen"
                },
                {
                    "symbol": "JIOFIN.BO",
                    "shortname": "Jio Financial Services Limited",
                    "quoteType": "EQUITY",
                    "exchDisp": "Bombay"
                }
            ]
        }
        mock_get.return_value = mock_response

        response = self.client.get(self.url, {"q": "jio"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should filter and return JIOFIN without duplicates
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["symbol"], "JIOFIN")
        self.assertEqual(response.data[0]["name"], "Jio Financial Services Limited")


