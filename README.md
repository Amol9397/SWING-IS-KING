# NSE Monthly Trend Line Break — FINAL

## Exact requested scanner
- NSE-listed EQ stocks only
- Monthly candles only for this tab
- Descending monthly trendline breakout
- Monthly EMA 144 filter
- Fibonacci from all-time high to all-time low
- Price above or around 0.50 Fib
- Two result states: CONFIRMED and CURRENT-MONTH IN PROGRESS
- High-contrast readable dashboard
- Full qualifying stock table + CSV

## Data architecture
The universe is loaded from NSE's official EQUITY_L.csv. Monthly OHLC data is requested at 1M frequency in batches. When NSE blocks cloud-server requests, the public monthly OHLC fallback is Yahoo Finance; the universe is still restricted to the NSE EQ master, and no non-NSE symbols are added by the application.

## Why current-month is included
The supplied TradingView screenshot shows a monthly candle breaking the descending trendline while the month is still open. Therefore the scanner separates:
- Confirmed: completed monthly candle broke the line and met filters.
- In progress: current monthly candle has broken the line and meets filters, but is not yet confirmed at month close.

## Deploy
Upload `app.py` and `requirements.txt` to GitHub and deploy on Streamlit Community Cloud.
