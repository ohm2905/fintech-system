from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime, date, timedelta
from transactions.models import Transaction, Category
from .models import Budget
from .serializers import BudgetSerializer

# Helper to parse YYYY-MM into a date object for the first day of that month
def parse_month_string(month_str):
    try:
        dt = datetime.strptime(month_str, "%Y-%m")
        return date(dt.year, dt.month, 1)
    except ValueError:
        return None

# ➕/✏️ Add or update a budget
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_modify_budget(request):
    data = request.data
    category_id = data.get('category')
    amount = data.get('amount')
    month_str = data.get('month')  # expects 'YYYY-MM' or 'YYYY-MM-DD'

    if not category_id or amount is None or not month_str:
        return Response({"error": "category, amount, and month are required fields."}, status=400)

    # Normalize month to first day of month date object
    if len(month_str) > 7:
        month_str = month_str[:7]  # Get YYYY-MM
    
    month_date = parse_month_string(month_str)
    if not month_date:
        return Response({"error": "Invalid month format. Use YYYY-MM."}, status=400)

    try:
        category = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return Response({"error": "Category not found."}, status=404)

    try:
        amount_val = float(amount)
        if amount_val <= 0:
            return Response({"error": "Amount must be greater than zero."}, status=400)
    except ValueError:
        return Response({"error": "Amount must be a number."}, status=400)

    # Check if budget already exists for this user, category, and month
    budget, created = Budget.objects.get_or_create(
        user=request.user,
        category=category,
        month=month_date,
        defaults={'amount': amount_val}
    )

    if not created:
        budget.amount = amount_val
        budget.save()

    serializer = BudgetSerializer(budget)
    return Response(serializer.data, status=201 if created else 200)


# 📄 List user's budgets
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_budgets(request):
    budgets = Budget.objects.filter(user=request.user).order_by('-month')
    serializer = BudgetSerializer(budgets, many=True)
    return Response(serializer.data)


# ❌ Delete a budget
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_budget(request, id):
    try:
        budget = Budget.objects.get(id=id, user=request.user)
        budget.delete()
        return Response({"message": "Budget deleted successfully."})
    except Budget.DoesNotExist:
        return Response({"error": "Budget not found."}, status=404)


# 📊 Budget status (Actual vs Limit)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def budget_status(request):
    month_str = request.GET.get('month')  # format: YYYY-MM
    if not month_str:
        # Default to current month
        month_date = date.today().replace(day=1)
        month_str = month_date.strftime("%Y-%m")
    else:
        month_date = parse_month_string(month_str)
        if not month_date:
            return Response({"error": "Invalid month format. Use YYYY-MM."}, status=400)

    import calendar
    today = date.today()
    total_days = calendar.monthrange(month_date.year, month_date.month)[1]
    
    # Calculate elapsed days in the target month
    if month_date.year < today.year or (month_date.year == today.year and month_date.month < today.month):
        # Past month: fully elapsed
        elapsed_days = total_days
    elif month_date.year == today.year and month_date.month == today.month:
        # Current month: elapsed days is today's day number
        elapsed_days = today.day
    else:
        # Future month: not started
        elapsed_days = 0

    # Get all budgets set for this month
    budgets = Budget.objects.filter(user=request.user, month=month_date)
    
    status_data = []
    for budget in budgets:
        # Calculate actual spending in this category for the month
        actual_spent = Transaction.objects.filter(
            user=request.user,
            category=budget.category,
            type='expense',
            date__year=month_date.year,
            date__month=month_date.month
        ).aggregate(total=Sum('amount'))['total'] or 0

        remaining = budget.amount - actual_spent
        percent_spent = (actual_spent / budget.amount) * 100 if budget.amount > 0 else 0

        # Calculate status flag
        if percent_spent > 100:
            status = 'exceeded'
        elif percent_spent >= 90:
            status = 'near_limit'
        else:
            status = 'under_budget'

        # Compute overspending projections
        actual_spent_val = float(actual_spent)
        budget_amount_val = float(budget.amount)
        
        if elapsed_days > 0:
            projected_spent = (actual_spent_val / elapsed_days) * total_days
        else:
            projected_spent = 0.0

        projected_overspend = max(0.0, projected_spent - budget_amount_val)
        is_projected_to_exceed = (projected_spent > budget_amount_val)

        status_data.append({
            "id": budget.id,
            "category_id": budget.category.id,
            "category_name": budget.category.name,
            "budget_amount": round(budget_amount_val, 2),
            "actual_spent": round(actual_spent_val, 2),
            "remaining": round(remaining, 2),
            "percent_spent": round(percent_spent, 1),
            "status": status,
            "projected_spent": round(projected_spent, 2),
            "projected_overspend": round(projected_overspend, 2),
            "is_projected_to_exceed": is_projected_to_exceed
        })

    return Response({
        "month": month_str,
        "budgets": status_data
    })


# 📊 Monthly Savings Rate over the last 6 months (up to target month)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def savings_rate(request):
    month_str = request.GET.get('month')
    if month_str:
        base_date = parse_month_string(month_str)
        if not base_date:
            return Response({"error": "Invalid month format. Use YYYY-MM."}, status=400)
    else:
        base_date = date.today().replace(day=1)

    result = []

    # Calculate for the last 6 months (including target month)
    for i in range(5, -1, -1):
        # Calculate year and month offset relative to base_date
        month_offset = base_date.month - i
        year_offset = base_date.year
        while month_offset <= 0:
            month_offset += 12
            year_offset -= 1
        
        target_month_date = date(year_offset, month_offset, 1)
        month_label = target_month_date.strftime("%Y-%m")

        # Sum Income
        income = Transaction.objects.filter(
            user=request.user,
            type='income',
            date__year=year_offset,
            date__month=month_offset
        ).aggregate(total=Sum('amount'))['total'] or 0

        # Sum Expenses
        expenses = Transaction.objects.filter(
            user=request.user,
            type='expense',
            date__year=year_offset,
            date__month=month_offset
        ).aggregate(total=Sum('amount'))['total'] or 0

        savings = income - expenses
        rate = (savings / income) * 100 if income > 0 else 0

        result.append({
            "month": month_label,
            "total_income": round(income, 2),
            "total_expense": round(expenses, 2),
            "net_savings": round(savings, 2),
            "savings_rate_percent": round(rate, 2)
        })

    return Response(result)


# 📈 Category Spending Trends over the last 6 months (up to target month)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def spending_trend(request):
    month_str = request.GET.get('month')
    if month_str:
        base_date = parse_month_string(month_str)
        if not base_date:
            return Response({"error": "Invalid month format. Use YYYY-MM."}, status=400)
    else:
        base_date = date.today().replace(day=1)

    result = []

    # Get all categories
    categories = Category.objects.filter(type='expense')
    
    # Calculate for the last 6 months
    for i in range(5, -1, -1):
        month_offset = base_date.month - i
        year_offset = base_date.year
        while month_offset <= 0:
            month_offset += 12
            year_offset -= 1
        
        target_month_date = date(year_offset, month_offset, 1)
        month_label = target_month_date.strftime("%Y-%m")

        # Get spending breakdown by category for this month
        breakdown = []
        monthly_total = 0
        
        for category in categories:
            total = Transaction.objects.filter(
                user=request.user,
                category=category,
                type='expense',
                date__year=year_offset,
                date__month=month_offset
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            if total > 0:
                monthly_total += total
                breakdown.append({
                    "category_id": category.id,
                    "category_name": category.name,
                    "amount": round(total, 2)
                })

        result.append({
            "month": month_label,
            "total_spent": round(monthly_total, 2),
            "breakdown": breakdown
        })

    return Response(result)
