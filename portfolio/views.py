from django.shortcuts import render
from .utils import get_stock_price
from datetime import date, datetime

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Portfolio, StockTransaction
from .serializers import PortfolioSerializer, StockTransactionSerializer


def recalculate_holdings(user, stock_name):
    # Fetch all transactions chronologically
    txs = StockTransaction.objects.filter(user=user, stock_name=stock_name).order_by('date', 'id')
    
    running_quantity = 0
    running_buy_price = 0.0

    for tx in txs:
        if tx.transaction_type == 'BUY':
            new_qty = running_quantity + tx.quantity
            new_cost = (running_quantity * running_buy_price) + (tx.quantity * tx.price)
            running_buy_price = new_cost / new_qty if new_qty > 0 else 0.0
            running_quantity = new_qty
        elif tx.transaction_type == 'SELL':
            running_quantity = running_quantity - tx.quantity
            # Average buy price does not change when selling
            if running_quantity < 0:
                running_quantity = 0  # Safeguard

    # Update or Delete the summary table Portfolio
    portfolio_record = Portfolio.objects.filter(user=user, stock_name=stock_name).first()

    if running_quantity > 0:
        if portfolio_record:
            portfolio_record.quantity = running_quantity
            portfolio_record.buy_price = running_buy_price
            portfolio_record.save()
        else:
            Portfolio.objects.create(
                user=user,
                stock_name=stock_name,
                quantity=running_quantity,
                buy_price=running_buy_price
            )
    else:
        if portfolio_record:
            portfolio_record.delete()


# ➕ Add Stock Transaction (BUY/SELL)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_stock(request):
    data = request.data.copy()
    stock_name = data.get('stock_name', '').upper()
    transaction_type = data.get('transaction_type', 'BUY').upper()
    
    try:
        quantity = int(data.get('quantity', 0))
        # Accept 'buy_price' or 'price' for backward compatibility
        price = float(data.get('buy_price') or data.get('price') or 0.0)
    except (ValueError, TypeError):
        return Response({"error": "Quantity and Price must be valid numbers."}, status=400)

    date_str = data.get('date')
    if not date_str:
        tx_date = date.today()
    else:
        try:
            tx_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

    if not stock_name:
        return Response({"error": "Stock name is required."}, status=400)
    if quantity <= 0:
        return Response({"error": "Quantity must be greater than zero."}, status=400)
    if price <= 0:
        return Response({"error": "Price must be greater than zero."}, status=400)
    if transaction_type not in ['BUY', 'SELL']:
        return Response({"error": "Transaction type must be BUY or SELL."}, status=400)

    # Validation: Insufficient shares check for SELL transactions
    if transaction_type == 'SELL':
        holding = Portfolio.objects.filter(user=request.user, stock_name=stock_name).first()
        current_qty = holding.quantity if holding else 0
        if current_qty < quantity:
            return Response({
                "error": f"Insufficient holdings. You only own {current_qty} shares of {stock_name} but tried to sell {quantity} shares."
            }, status=400)

    # Save transaction
    tx = StockTransaction.objects.create(
        user=request.user,
        stock_name=stock_name,
        transaction_type=transaction_type,
        quantity=quantity,
        price=price,
        date=tx_date
    )

    # Recalculate portfolio holdings
    recalculate_holdings(request.user, stock_name)

    return Response({
        "message": f"Successfully registered {transaction_type} of {quantity} shares of {stock_name}.",
        "transaction_id": tx.id
    }, status=201)


# 📊 Portfolio Summary
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def portfolio_summary(request):
    stocks = Portfolio.objects.filter(user=request.user)

    result = []
    total_investment = 0
    total_current_value = 0

    profits = []

    for stock in stocks:
        current_price = get_stock_price(stock.stock_name)

        investment = stock.quantity * stock.buy_price
        current_value = stock.quantity * current_price
        profit_loss = current_value - investment

        total_investment += investment
        total_current_value += current_value

        profits.append({
            "stock": stock.stock_name,
            "profit": profit_loss
        })

        roi_percent = round((profit_loss / investment) * 100, 2) if investment > 0 else 0.0

        result.append({
            "id": stock.id,
            "stock": stock.stock_name,
            "quantity": stock.quantity,
            "buy_price": round(stock.buy_price, 2),
            "current_price": round(current_price, 2),
            "investment": round(investment, 2),
            "current_value": round(current_value, 2),
            "profit_loss": round(profit_loss, 2),
            "roi_percent": roi_percent
        })

    # 🔥 Top gainer / loser
    top_gainer = None
    top_loser = None

    if len(profits) >= 2:
        profits_sorted = sorted(profits, key=lambda x: x["profit"])
        top_loser = profits_sorted[0]["stock"]
        top_gainer = profits_sorted[-1]["stock"]

    elif len(profits) == 1:
        top_gainer = profits[0]["stock"]
        top_loser = None

    # 🔥 Overall calculation
    overall_profit = total_current_value - total_investment

    growth_percent = (
        (overall_profit / total_investment) * 100
        if total_investment > 0 else 0
    )

    # 🔹 Search by Stock Name
    search_query = request.GET.get('search')
    filtered_result = result
    if search_query:
        search_query = search_query.upper()
        filtered_result = [s for s in result if search_query in s["stock"]]

    # 🔹 Sorting
    sort_by = request.GET.get('sort_by', 'stock')  # default = stock
    order = request.GET.get('order', 'asc')        # default = asc

    if sort_by not in ['stock', 'quantity', 'buy_price', 'current_price', 'investment', 'current_value', 'profit_loss']:
        sort_by = 'stock'

    reverse_order = (order == 'desc')

    if sort_by == 'stock':
        filtered_result = sorted(filtered_result, key=lambda x: x['stock'].lower(), reverse=reverse_order)
    else:
        filtered_result = sorted(filtered_result, key=lambda x: x[sort_by], reverse=reverse_order)

    # 🔹 Pagination
    try:
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 5))
    except ValueError:
        return Response({"error": "page and limit must be integers"}, status=400)

    if page < 1 or limit < 1:
        return Response({"error": "page and limit must be > 0"}, status=400)

    start = (page - 1) * limit
    end = start + limit

    total_filtered = len(filtered_result)
    paged_result = filtered_result[start:end]

    return Response({
        "total_investment": round(total_investment, 2),
        "total_current_value": round(total_current_value, 2),
        "overall_profit_loss": round(overall_profit, 2),
        "growth_percent": round(growth_percent, 2),
        "top_gainer": top_gainer,
        "top_loser": top_loser,
        "total": total_filtered,
        "page": page,
        "limit": limit,
        "stocks": paged_result,
        "all_stocks": result
    })


# ❌ Delete Stock (Removes stock summary and all related transactions)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_stock(request, id):
    try:
        stock = Portfolio.objects.get(id=id, user=request.user)
        # Delete all transactions for this stock
        StockTransaction.objects.filter(user=request.user, stock_name=stock.stock_name).delete()
        stock.delete()
        return Response({"message": "Stock and all its transactions deleted successfully"})
    except Portfolio.DoesNotExist:
        return Response({"error": "Stock not found"}, status=404)


# 📄 Get Stock Transactions history (with search, date filters, sorting, and pagination)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stock_transactions(request):
    txs = StockTransaction.objects.filter(user=request.user)

    # 🔹 Search by Stock Name
    search_query = request.GET.get('search')
    if search_query:
        txs = txs.filter(stock_name__icontains=search_query.upper())

    # 🔹 Filter by Date Range
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        txs = txs.filter(date__gte=start_date)
    if end_date:
        txs = txs.filter(date__lte=end_date)

    # 🔹 Sorting
    sort_by = request.GET.get('sort_by', 'date')  # default = date
    order = request.GET.get('order', 'desc')      # default = desc

    if sort_by not in ['date', 'stock_name']:
        sort_by = 'date'

    if order == 'desc':
        sort_by_field = f'-{sort_by}'
    else:
        sort_by_field = sort_by

    txs = txs.order_by(sort_by_field, '-id' if order == 'desc' else 'id')

    # 🔹 Pagination
    try:
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 5))
    except ValueError:
        return Response({"error": "page and limit must be integers"}, status=400)

    if page < 1 or limit < 1:
        return Response({"error": "page and limit must be > 0"}, status=400)

    start = (page - 1) * limit
    end = start + limit

    total = txs.count()
    txs_paged = txs[start:end]

    serializer = StockTransactionSerializer(txs_paged, many=True)

    return Response({
        "total": total,
        "page": page,
        "limit": limit,
        "data": serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_forecast(request):
    import numpy as np
    import yfinance as yf
    import datetime

    stock_name = request.GET.get('stock')
    if not stock_name:
        return Response({"error": "Stock name is required."}, status=400)

    stock_name = stock_name.upper()

    try:
        # Fetch 60 days of historical data (using the NSE ticker suffix)
        ticker = yf.Ticker(stock_name + ".NS")
        history = ticker.history(period="60d")

        if history.empty:
            # Fallback in case NSE lookup fails, try standard US ticker just in case
            ticker = yf.Ticker(stock_name)
            history = ticker.history(period="60d")

        # Drop any NaN values in Close to avoid math errors (e.g. current day data might be NaN)
        history = history.dropna(subset=['Close'])

        if history.empty or len(history) < 5:
            return Response({"error": f"Insufficient historical price data found for ticker '{stock_name}'."}, status=400)

        # Retrieve Close prices
        prices = history['Close'].values
        n = len(prices)

        # Fit OLS linear trend
        x = np.arange(n)
        slope, intercept = np.polyfit(x, prices, 1)

        # Forecast next 7 days (day index n to n+6)
        future_x = np.arange(n, n + 7)
        forecast_prices = slope * future_x + intercept

        # Calculate standard deviation of historical residuals to establish standard error
        residuals = prices - (slope * x + intercept)
        std_error = np.std(residuals)
        if std_error <= 0:
            std_error = prices[-1] * 0.02  # fallback if standard deviation is zero (flat line)

        # Uncertainty expands with sqrt(days_ahead)
        future_days = np.arange(1, 8)
        uncertainty = std_error * 1.96 * np.sqrt(future_days)

        lower_bound = forecast_prices - uncertainty
        upper_bound = forecast_prices + uncertainty

        # Get last close date
        last_date = history.index[-1].to_pydatetime().date()
        
        # Generate forecast dates
        forecast_dates = []
        for i in range(1, 8):
            f_date = last_date + datetime.timedelta(days=i)
            forecast_dates.append(f_date.strftime("%Y-%m-%d"))

        # Limit historical response to last 30 days for cleaner charting
        history_dates = [d.to_pydatetime().date().strftime("%Y-%m-%d") for d in history.index[-30:]]
        history_prices = [round(float(p), 2) for p in history['Close'].values[-30:]]

        return Response({
            "stock": stock_name,
            "current_price": round(float(prices[-1]), 2),
            "history_dates": history_dates,
            "history_prices": history_prices,
            "forecast_dates": forecast_dates,
            "forecast_prices": [round(float(p), 2) for p in forecast_prices],
            "lower_bound": [round(float(p), 2) for p in lower_bound],
            "upper_bound": [round(float(p), 2) for p in upper_bound]
        }, status=200)

    except Exception as e:
        return Response({"error": f"An error occurred while generating the stock forecast: {str(e)}"}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_stocks(request):
    import requests
    query = request.GET.get('q', '').strip()
    if not query:
        return Response([])
    
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={query}&newsCount=0"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            quotes = data.get('quotes', [])
            
            results = []
            seen = set()
            for quote in quotes:
                symbol = quote.get('symbol', '')
                if quote.get('quoteType') == 'EQUITY' and (symbol.endswith('.NS') or symbol.endswith('.BO')):
                    base_symbol = symbol.split('.')[0].upper()
                    if base_symbol not in seen:
                        seen.add(base_symbol)
                        results.append({
                            'symbol': base_symbol,
                            'name': quote.get('longname') or quote.get('shortname') or base_symbol,
                            'exchange': 'NSE' if symbol.endswith('.NS') else 'BSE'
                        })
            return Response(results)
    except Exception as e:
        print("Error searching stocks:", e)
        
    return Response([])