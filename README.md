# Tech Stock Tracking

An automated system that fetches live data for the top 20 global tech stocks, generates a formatted report in Google Docs, and delivers an AI-powered market analysis to your inbox — every day, fully hands-free.

---

## What It Does

- Fetches live stock data for 20 major tech companies via Yahoo Finance
- Tracks open/close prices and % changes over 1D, 1W, 1M, 3M, and 1Y periods
- Creates and updates a formatted Google Doc with a colour-coded data table
- Uses **Claude Opus 4.7** to generate a ~200 word AI market analysis report
- Automatically emails the report link to a configurable list of recipients
- Runs every day at **9:00 AM UTC** via GitHub Actions — no local machine required

---

## Stocks Tracked

| Ticker | Company |
|--------|---------|
| NVDA | NVIDIA |
| GOOG | Alphabet (Google) |
| AAPL | Apple |
| MSFT | Microsoft |
| AMZN | Amazon |
| TSM | TSMC |
| AVGO | Broadcom |
| META | Meta Platforms |
| TSLA | Tesla |
| 005930.KS | Samsung Electronics |
| TCEHY | Tencent |
| ASML | ASML Holding |
| 000660.KS | SK Hynix |
| MU | Micron Technology |
| ORCL | Oracle |
| AMD | Advanced Micro Devices |
| NFLX | Netflix |
| PLTR | Palantir |
| INTC | Intel |
| BABA | Alibaba |

---

## Project Structure

```
├── fetch_stocks.py          # Fetches live stock data via yfinance
├── create_google_doc.py     # Creates/updates Google Doc and sends emails
├── recipients.json          # List of email recipients
├── Database.sql             # Latest stock data in SQL format
├── .github/workflows/
│   └── stock_report.yml     # GitHub Actions automation (daily schedule)
```

---

## How to Add Email Recipients

Edit `recipients.json`:

```json
{
    "recipients": [
        {"name": "Your Name", "email": "your@email.com"},
        {"name": "Another Person", "email": "another@email.com"}
    ]
}
```

---

## Tech Stack

- **Python 3.11**
- **yfinance** — live stock data
- **Google Docs API / Drive API / Gmail API** — document creation and email delivery
- **Anthropic Claude Opus 4.7** — AI market analysis
- **GitHub Actions** — cloud automation (no local machine needed)

---

## Setup (for developers)

1. Clone the repository
2. Install dependencies: `pip install yfinance pandas google-api-python-client google-auth-oauthlib google-auth-httplib2 anthropic`
3. Set up a Google Cloud project with Docs, Drive, and Gmail APIs enabled
4. Download `credentials.json` from Google Cloud Console (OAuth Desktop app)
5. Run `python create_google_doc.py` once to authenticate and generate `token.json`
6. Add the following GitHub Secrets to your repository:
   - `GOOGLE_CREDENTIALS` — contents of `credentials.json`
   - `GOOGLE_TOKEN` — contents of `token.json`
   - `GOOGLE_DOC_ID` — your Google Doc ID
   - `ANTHROPIC_API_KEY` — your Anthropic API key

---

## Automated Schedule

The workflow runs daily at **9:00 AM UTC** (12:00 PM Turkey time). It can also be triggered manually from the GitHub Actions tab.