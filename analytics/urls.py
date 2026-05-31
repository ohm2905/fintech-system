from django.urls import path
from .views import add_modify_budget, get_budgets, delete_budget, budget_status, savings_rate, spending_trend
from .ai_assistant import chat_with_gemini

urlpatterns = [
    path('budget/', get_budgets),
    path('budget/add/', add_modify_budget),
    path('budget/delete/<int:id>/', delete_budget),
    path('budget-status/', budget_status),
    path('savings-rate/', savings_rate),
    path('spending-trend/', spending_trend),
    path('chat/', chat_with_gemini),
]
