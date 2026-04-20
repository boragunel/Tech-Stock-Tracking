# Project Summary — Tech Stock Tracking System

## What Was Built

A fully automated stock tracking and reporting system that requires zero daily input from the user. Every morning it fetches live market data, updates a Google Doc, generates an AI market analysis, and emails the report to a configurable list of recipients.

---

## How It Was Built — Step by Step

### 1. Stock Data Fetching (`fetch_stocks.py`)
- Already existed at project start
- Uses the `yfinance` library to pull live price data for 20 major tech stocks
- Calculates % price changes over 1D, 1W, 1M, 3M, and 1Y periods
- Also generates `Database.sql` with the latest data in SQL format

### 2. Google Cloud Setup
- Created a Google Cloud project (`Tech-Stock-Tracking`)
- Enabled **Google Docs API**, **Google Drive API**, and **Gmail API**
- Created an OAuth 2.0 Desktop App credential
- Downloaded `credentials.json` for local authentication
- Added `borra.gunel@gmail.com` as a test user on the OAuth consent screen

### 3. Google Doc Automation (`create_google_doc.py`)
- Authenticates with Google using OAuth 2.0 (saves token to `token.json`)
- Creates a Google Doc titled **"Tech Stock Report"** inside the `stock tracking report` folder in Google Drive
- On subsequent runs, clears and rewrites the existing document
- If the document is deleted, automatically recreates it in the same folder
- Builds a formatted table with colour-coded % change columns (green = positive, red = negative)
- Inserts a **Heading 1** title with the current date

### 4. AI Market Analysis (Claude Opus 4.7)
- Integrated the **Anthropic API** using the `anthropic` Python SDK
- Passes all 20 stock data points to **Claude Opus 4.7** with adaptive thinking enabled
- Claude generates a ~200 word market analysis report identifying trends and outlook
- The report is appended to the Google Doc under a **"AI Market Analysis"** heading

### 5. Automated Email Delivery
- Added Gmail API integration to send emails after each report update
- Recipients are configured in `recipients.json` — add or remove people at any time
- Each email contains the report date and a direct link to the Google Doc
- Sent automatically from the authenticated Google account

### 6. GitHub Actions Automation (`.github/workflows/stock_report.yml`)
- The entire pipeline runs on **GitHub's servers** — no local machine required
- Scheduled via cron: **every day at 9:00 AM UTC** (12:00 PM Turkey time)
- Can also be triggered manually from the GitHub Actions tab
- Credentials are stored securely as **GitHub Secrets** (never in the code)

---

## GitHub Secrets Used

| Secret | Purpose |
|--------|---------|
| `GOOGLE_CREDENTIALS` | OAuth client credentials from Google Cloud |
| `GOOGLE_TOKEN` | OAuth access/refresh token for Google APIs |
| `GOOGLE_DOC_ID` | ID of the existing Google Doc to update |
| `ANTHROPIC_API_KEY` | API key for Claude Opus 4.7 |

---

## Files in the Repository

| File | Purpose |
|------|---------|
| `fetch_stocks.py` | Fetches live stock data and generates SQL |
| `create_google_doc.py` | Main script — doc update, AI report, email |
| `recipients.json` | Email recipient list |
| `Database.sql` | Latest stock data snapshot |
| `.github/workflows/stock_report.yml` | GitHub Actions automation |
| `.gitignore` | Keeps credentials off GitHub |

---

## Daily Flow (Automated)

```
9:00 AM UTC
    ↓
GitHub Actions triggers
    ↓
Fetch live stock data (yfinance)
    ↓
Update Google Doc with formatted table
    ↓
Claude Opus 4.7 generates market report
    ↓
Report appended to Google Doc
    ↓
Email sent to all recipients in recipients.json
```