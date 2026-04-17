import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

TICKERS = [
    "NVDA", "GOOG", "AAPL", "MSFT", "AMZN", "TSM", "AVGO", "META", "TSLA",
    "005930.KS", "TCEHY", "ASML", "000660.KS", "MU", "ORCL", "AMD", "NFLX",
    "PLTR", "INTC", "BABA"
]

COMPANY_NAMES = {
    "NVDA": "NVIDIA", "GOOG": "Alphabet (Google)", "AAPL": "Apple",
    "MSFT": "Microsoft", "AMZN": "Amazon", "TSM": "TSMC",
    "AVGO": "Broadcom", "META": "Meta Platforms", "TSLA": "Tesla",
    "005930.KS": "Samsung Electronics", "TCEHY": "Tencent",
    "ASML": "ASML Holding", "000660.KS": "SK Hynix",
    "MU": "Micron Technology", "ORCL": "Oracle",
    "AMD": "Advanced Micro Devices", "NFLX": "Netflix",
    "PLTR": "Palantir", "INTC": "Intel", "BABA": "Alibaba"
}

def pct_change(current, past):
    if past is None or past == 0:
        return None
    return round(((current - past) / past) * 100, 4)

def get_price_at(hist, days_ago):
    target = datetime.today().date() - timedelta(days=days_ago)
    # Walk back up to 7 extra days to find a trading day
    for offset in range(8):
        d = target - timedelta(days=offset)
        matches = hist[hist.index.date == d]
        if not matches.empty:
            return matches["Close"].iloc[-1]
    return None

def fetch_stock_data():
    today = datetime.today().date()
    start = today - timedelta(days=400)  # enough history for 1-year change

    rows = []
    for ticker in TICKERS:
        print(f"Fetching {ticker}...")
        try:
            t = yf.Ticker(ticker)
            hist = t.history(start=start.isoformat(), end=(today + timedelta(days=1)).isoformat())

            if hist.empty:
                print(f"  No data for {ticker}, skipping.")
                continue

            # Strip timezone without converting so local dates are preserved
            if hist.index.tzinfo is not None:
                hist.index = hist.index.map(lambda x: x.replace(tzinfo=None))

            # Drop rows where Close is NaN (e.g. market not closed yet today)
            hist = hist.dropna(subset=["Close"])

            if hist.empty:
                print(f"  No valid close data for {ticker}, skipping.")
                continue

            latest = hist.iloc[-1]
            open_price  = round(float(latest["Open"]),  4) if not pd.isna(latest["Open"]) else round(float(latest["Close"]), 4)
            close_price = round(float(latest["Close"]), 4)

            p1d  = get_price_at(hist, 1)
            p1w  = get_price_at(hist, 7)
            p1m  = get_price_at(hist, 30)
            p3m  = get_price_at(hist, 90)
            p1y  = get_price_at(hist, 365)

            rows.append({
                "ticker":       ticker,
                "company_name": COMPANY_NAMES.get(ticker, ticker),
                "date":         str(today),
                "open_price":   open_price,
                "close_price":  close_price,
                "change_1d_pct": pct_change(close_price, p1d),
                "change_1w_pct": pct_change(close_price, p1w),
                "change_1m_pct": pct_change(close_price, p1m),
                "change_3m_pct": pct_change(close_price, p3m),
                "change_1y_pct": pct_change(close_price, p1y),
            })
        except Exception as e:
            print(f"  Error fetching {ticker}: {e}")

    return rows

def to_sql_val(v):
    if v is None:
        return "NULL"
    if isinstance(v, str):
        return f"'{v.replace(chr(39), chr(39)+chr(39))}'"
    return str(v)

def generate_sql(rows, output_file="Database.sql"):
    lines = []

    lines.append("-- ============================================================")
    lines.append("--  Stock Market Data")
    lines.append(f"--  Generated: {datetime.today().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("-- ============================================================\n")

    lines.append("DROP TABLE IF EXISTS stock_data;")
    lines.append("")
    lines.append("CREATE TABLE stock_data (")
    lines.append("    id            INT AUTO_INCREMENT PRIMARY KEY,")
    lines.append("    ticker        VARCHAR(20)    NOT NULL,")
    lines.append("    company_name  VARCHAR(100),")
    lines.append("    date          DATE           NOT NULL,")
    lines.append("    open_price    DECIMAL(15,4),")
    lines.append("    close_price   DECIMAL(15,4),")
    lines.append("    change_1d_pct DECIMAL(10,4),   -- % change vs 1 day ago")
    lines.append("    change_1w_pct DECIMAL(10,4),   -- % change vs 1 week ago")
    lines.append("    change_1m_pct DECIMAL(10,4),   -- % change vs 1 month ago")
    lines.append("    change_3m_pct DECIMAL(10,4),   -- % change vs 3 months ago")
    lines.append("    change_1y_pct DECIMAL(10,4),   -- % change vs 1 year ago")
    lines.append("    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    lines.append(");")
    lines.append("")

    lines.append("INSERT INTO stock_data")
    lines.append("    (ticker, company_name, date, open_price, close_price,")
    lines.append("     change_1d_pct, change_1w_pct, change_1m_pct, change_3m_pct, change_1y_pct)")
    lines.append("VALUES")

    value_lines = []
    for r in rows:
        vals = ", ".join([
            to_sql_val(r["ticker"]),
            to_sql_val(r["company_name"]),
            to_sql_val(r["date"]),
            to_sql_val(r["open_price"]),
            to_sql_val(r["close_price"]),
            to_sql_val(r["change_1d_pct"]),
            to_sql_val(r["change_1w_pct"]),
            to_sql_val(r["change_1m_pct"]),
            to_sql_val(r["change_3m_pct"]),
            to_sql_val(r["change_1y_pct"]),
        ])
        value_lines.append(f"    ({vals})")

    lines.append(",\n".join(value_lines) + ";")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nSQL written to {output_file}  ({len(rows)} rows)")

if __name__ == "__main__":
    data = fetch_stock_data()
    if data:
        generate_sql(data)
    else:
        print("No data fetched — check your internet connection or ticker symbols.")