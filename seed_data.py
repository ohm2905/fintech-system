import os
import django
import random
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
from transactions.models import Category, Transaction
from analytics.models import Budget

User = get_user_model()

def seed():
    print("Starting data seeding...")

    # 1. Create standard categories if they don't exist
    categories_data = [
        # Income
        ("Salary", "income"),
        ("Freelance", "income"),
        # Expense
        ("Food", "expense"),
        ("Rent", "expense"),
        ("Entertainment", "expense"),
        ("Utilities", "expense"),
        ("Travel", "expense"),
    ]

    categories = {}
    for name, cat_type in categories_data:
        cat, created = Category.objects.get_or_create(name=name, type=cat_type)
        categories[name] = cat
        if created:
            print(f"Created category: {name} ({cat_type})")

    users = User.objects.all()
    if not users:
        print("No users found. Please sign up first.")
        return

    today = date.today()

    # 2. Loop through all users and add transaction history + budgets
    for user in users:
        print(f"\nSeeding data for user: {user.username}")

        # Clear existing transactions and budgets to start fresh
        Transaction.objects.filter(user=user).delete()
        Budget.objects.filter(user=user).delete()

        # Seed transactions over the last 6 months
        for i in range(5, -1, -1):
            # Calculate year and month offset
            month_offset = today.month - i
            year_offset = today.year
            while month_offset <= 0:
                month_offset += 12
                year_offset -= 1
            
            # E.g. December 2025 to May 2026
            month_date = date(year_offset, month_offset, 1)
            print(f"  Adding transactions for {month_date.strftime('%Y-%m')}...")

            # --- INCOME TRANSACTIONS ---
            # Monthly Salary (fixed)
            Transaction.objects.create(
                user=user,
                category=categories["Salary"],
                amount=4500.0,
                type="income",
                date=date(year_offset, month_offset, 1),
                description="Monthly Salary"
            )

            # Freelance Income (random)
            if random.choice([True, False]):
                Transaction.objects.create(
                    user=user,
                    category=categories["Freelance"],
                    amount=round(random.uniform(300, 1200), 2),
                    type="income",
                    date=date(year_offset, month_offset, 15),
                    description="Freelance project payout"
                )

            # --- EXPENSE TRANSACTIONS ---
            # Monthly Rent (fixed)
            Transaction.objects.create(
                user=user,
                category=categories["Rent"],
                amount=1200.0,
                type="expense",
                date=date(year_offset, month_offset, 2),
                description="Rent payment"
            )

            # Utilities (mostly fixed)
            Transaction.objects.create(
                user=user,
                category=categories["Utilities"],
                amount=round(random.uniform(120, 180), 2),
                type="expense",
                date=date(year_offset, month_offset, 5),
                description="Water & electricity bill"
            )

            # Food (multiple transactions per month)
            for d in [5, 12, 19, 26]:
                Transaction.objects.create(
                    user=user,
                    category=categories["Food"],
                    amount=round(random.uniform(80, 150), 2),
                    type="expense",
                    date=date(year_offset, month_offset, d),
                    description="Grocery shopping"
                )

            # Entertainment
            Transaction.objects.create(
                user=user,
                category=categories["Entertainment"],
                amount=round(random.uniform(50, 250), 2),
                type="expense",
                date=date(year_offset, month_offset, 18),
                description="Movies and dining out"
            )

            # Travel
            if random.choice([True, False]):
                Transaction.objects.create(
                    user=user,
                    category=categories["Travel"],
                    amount=round(random.uniform(80, 300), 2),
                    type="expense",
                    date=date(year_offset, month_offset, 22),
                    description="Weekend trip / Uber rides"
                )

        # 3. Add Budgets for the CURRENT Month (May 2026)
        current_month_date = date(today.year, today.month, 1)
        print(f"  Setting budgets for {current_month_date.strftime('%Y-%m')}...")

        # Food Budget: $450 (Actual spending will be around $400-$600, causing a nice mix of status states)
        Budget.objects.create(
            user=user,
            category=categories["Food"],
            amount=450.0,
            month=current_month_date
        )

        # Rent Budget: $1200 (Matches actual, showing 100% "near limit" or exactly at budget limit)
        Budget.objects.create(
            user=user,
            category=categories["Rent"],
            amount=1200.0,
            month=current_month_date
        )

        # Entertainment Budget: $200
        Budget.objects.create(
            user=user,
            category=categories["Entertainment"],
            amount=200.0,
            month=current_month_date
        )

        # Utilities Budget: $150
        Budget.objects.create(
            user=user,
            category=categories["Utilities"],
            amount=150.0,
            month=current_month_date
        )

    print("\nSeeding completed successfully!")

if __name__ == "__main__":
    seed()
