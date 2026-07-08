import yfinance as yf

def get_stock_data(ticker_symbol: str):
    print(f"🍏 Fetching data for ticker: {ticker_symbol.upper()}...")
    
    # Initialize the ticker object
    ticker = yf.Ticker(ticker_symbol)
    
    try:
        # 1. Fetch current price and structural overview info
        info = ticker.info
        
        # Check if we got a valid response back
        if not info or 'regularMarketPrice' not in info and 'currentPrice' not in info:
            print(f"❌ Could not find valid data for ticker '{ticker_symbol}'. Is it typed correctly?")
            return

        company_name = info.get('longName', 'Unknown Company')
        current_price = info.get('currentPrice' or 'regularMarketPrice')
        currency = info.get('currency', 'USD')
        market_cap = info.get('marketCap', 0)
        trailing_pe = info.get('trailingPE', 'N/A')

        print("\n=== COMPANY OVERVIEW ===")
        print(f"Name:          {company_name}")
        print(f"Current Price: {current_price} {currency}")
        print(f"Market Cap:    ${market_cap:,}")
        print(f"Trailing P/E:  {trailing_pe}")

        # 2. Fetch recent daily historical data (e.g., last 5 days)
        print("\n=== RECENT TRADING HISTORY (Last 5 Days) ===")
        history = ticker.history(period="5d")
        print(history[['Open', 'High', 'Low', 'Close', 'Volume']])
        
    except Exception as e:
        print(f"An error occurred while calling Yahoo Finance: {e}")

if __name__ == "__main__":
    # You can change this to any code (e.g., "SHOP", "RY", "AAPL", "MSFT")
    stock_code = input("Enter a stock symbol (e.g., AAPL): ").strip()
    if stock_code:
        get_stock_data(stock_code)
    else:
        print("Please enter a valid ticker string.")

