from django.shortcuts import render

def dashboard(request):
    return render(request, 'dashboard.html')

def login_page(request):
    return render(request, 'login.html')

def transactions_page(request):
    return render(request, 'transactions.html')

def signup_page(request):
    return render(request, 'signup.html')

def analytics_page(request):
    return render(request, 'analytics.html')

