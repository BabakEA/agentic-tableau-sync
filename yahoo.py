import yfinance as yf

def get_minute_data(ticker_symbol: str):
    print(f"⏱️ Fetching 1-minute interval data for {ticker_symbol.upper()} (Last 7 Days)...")
    
    ticker = yf.Ticker(ticker_symbol)
    
    try:
        # Fetching the maximum allowed chunk for 1m data (7 days)
        # Note: include_prepost=True will include pre-market and after-hours data if you want it
        history = ticker.history(period="7d", interval="1m", prepost=False)
        
        if history.empty:
            print("❌ No minute data returned. Double check the ticker symbol or if the market was closed.")
            return

        print(f"✅ Successfully retrieved {len(history)} data rows.")
        
        # Displaying the first few and last few records to see the timestamps
        print("\n=== FIRST 5 ROWS OF MINUTE DATA ===")
        print(history.head())
        
        print("\n=== LAST 5 ROWS OF MINUTE DATA ===")
        print(history.tail())
        
        # Optional: Save it out to a CSV in your workspace if you want to inspect the whole sheet
        csv_filename = f"{ticker_symbol.lower()}_1m_7d.csv"
        history.to_csv(csv_filename)
        print(f"\n💾 Saved full granular data to workspace as: {csv_filename}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    stock_code = input("Enter stock symbol (e.g., AAPL, NVDA, RY): ").strip()
    if stock_code:
        get_minute_data(stock_code)