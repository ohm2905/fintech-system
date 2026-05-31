from django.urls import path
from .views import add_stock, delete_stock, portfolio_summary, get_stock_transactions, stock_forecast, search_stocks

urlpatterns = [
    path('add/', add_stock),
    path('transaction/add/', add_stock),
    path('summary/', portfolio_summary),
    path('delete/<int:id>/', delete_stock),
    path('transactions/', get_stock_transactions),
    path('forecast/', stock_forecast),
    path('search/', search_stocks),
]