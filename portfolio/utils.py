from django.core.cache import cache
import yfinance as yf

def get_stock_price(stock_name):
    cache_key = f"stock_price_{stock_name.upper()}"
    cached_price = cache.get(cache_key)
    
    if cached_price is not None:
        return cached_price

    try:
        stock = yf.Ticker(stock_name + ".NS")  # NSE stocks
        data = stock.history(period="1d")

        if not data.empty:
            price = float(data['Close'].iloc[-1])
            # Cache for 15 minutes (900 seconds)
            cache.set(cache_key, price, 900)
            return price

    except Exception as e:
        print("Error fetching price:", e)

    return 0