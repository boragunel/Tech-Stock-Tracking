import os
import json
import base64
import anthropic
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from fetch_stocks import fetch_stock_data

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.send"
]

DOC_ID_FILE = "doc_id.txt"


def authenticate():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds


def get_or_create_doc(docs, drive):
    if os.path.exists(DOC_ID_FILE):
        with open(DOC_ID_FILE) as f:
            doc_id = f.read().strip()
        try:
            doc = docs.documents().get(documentId=doc_id).execute()
            print(f"Updating existing document: {doc_id}")
            body = doc["body"]["content"]
            end_index = body[-1]["endIndex"] - 1
            if end_index > 1:
                docs.documents().batchUpdate(documentId=doc_id, body={"requests": [{
                    "deleteContentRange": {
                        "range": {"startIndex": 1, "endIndex": end_index}
                    }
                }]}).execute()
            return doc_id, False
        except Exception:
            print("Saved document not found — creating a new one.")
            os.remove(DOC_ID_FILE)

    title = "Tech Stock Report"
    doc = docs.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    # Move doc into 'stock tracking report' folder
    folder_results = drive.files().list(
        q="mimeType='application/vnd.google-apps.folder' and name='stock tracking report' and trashed=false",
        fields="files(id)"
    ).execute()
    folders = folder_results.get("files", [])
    if folders:
        folder_id = folders[0]["id"]
        drive.files().update(
            fileId=doc_id,
            addParents=folder_id,
            removeParents="root",
            fields="id, parents"
        ).execute()
        print(f"Moved document to 'stock tracking report' folder.")

    with open(DOC_ID_FILE, "w") as f:
        f.write(doc_id)
    print(f"Created new document: {doc_id}")
    return doc_id, True


def populate_doc(docs, doc_id, rows):
    date = rows[0]["date"] if rows else "N/A"
    headers = ["Ticker", "Company", "Date", "Open", "Close", "1D %", "1W %", "1M %", "3M %", "1Y %"]
    col_widths = [80, 180, 100, 80, 80, 70, 70, 70, 70, 70]
    num_cols = len(headers)
    num_rows = len(rows) + 1

    requests = []
    index = 1

    title = f"Tech Stock Report — {date}"
    requests.append({"insertText": {"location": {"index": index}, "text": title + "\n"}})
    requests.append({
        "updateParagraphStyle": {
            "range": {"startIndex": index, "endIndex": index + len(title)},
            "paragraphStyle": {"namedStyleType": "HEADING_1"},
            "fields": "namedStyleType"
        }
    })
    index += len(title) + 1

    subtitle = "Generated automatically from live market data\n"
    requests.append({"insertText": {"location": {"index": index}, "text": subtitle}})
    index += len(subtitle)

    requests.append({"insertTable": {"rows": num_rows, "columns": num_cols, "location": {"index": index}}})

    docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

    # Get table cell indexes
    doc = docs.documents().get(documentId=doc_id).execute()
    table = None
    table_start_index = None
    for elem in doc["body"]["content"]:
        if "table" in elem:
            table = elem["table"]
            table_start_index = elem["startIndex"]
            break

    if not table:
        print("Could not find table.")
        return

    all_rows = [headers] + [
        [
            r["ticker"], r["company_name"], r["date"],
            str(r["open_price"]), str(r["close_price"]),
            fmt_pct(r["change_1d_pct"]), fmt_pct(r["change_1w_pct"]),
            fmt_pct(r["change_1m_pct"]), fmt_pct(r["change_3m_pct"]),
            fmt_pct(r["change_1y_pct"]),
        ]
        for r in rows
    ]

    # Collect cells and insert in reverse order to avoid index shifting
    cells = []
    for row_i, row_data in enumerate(all_rows):
        for col_i, cell_text in enumerate(row_data):
            cell = table["tableRows"][row_i]["tableCells"][col_i]
            cell_index = cell["content"][0]["startIndex"]
            cells.append((cell_index, cell_text, row_i, col_i))

    cells.sort(key=lambda x: x[0], reverse=True)

    insert_requests = [
        {"insertText": {"location": {"index": ci}, "text": ct}}
        for ci, ct, _, _ in cells
    ]
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": insert_requests}).execute()

    # Re-fetch for styling
    doc = docs.documents().get(documentId=doc_id).execute()
    table = None
    table_start_index = None
    for elem in doc["body"]["content"]:
        if "table" in elem:
            table = elem["table"]
            table_start_index = elem["startIndex"]
            break

    style_requests = []
    for row_i, row_data in enumerate(all_rows):
        for col_i, cell_text in enumerate(row_data):
            cell = table["tableRows"][row_i]["tableCells"][col_i]
            cell_index = cell["content"][0]["startIndex"]

            if row_i == 0:
                style_requests.append({
                    "updateTextStyle": {
                        "range": {"startIndex": cell_index, "endIndex": cell_index + len(cell_text)},
                        "textStyle": {"bold": True},
                        "fields": "bold"
                    }
                })

            if row_i > 0 and col_i >= 5:
                try:
                    current_row = rows[row_i - 1]
                    key = ["change_1d_pct", "change_1w_pct", "change_1m_pct", "change_3m_pct", "change_1y_pct"][col_i - 5]
                    val = float(current_row[key])
                    color = {"red": 0.8, "green": 0.0, "blue": 0.0} if val < 0 else {"red": 0.0, "green": 0.6, "blue": 0.0}
                    style_requests.append({
                        "updateTextStyle": {
                            "range": {"startIndex": cell_index, "endIndex": cell_index + len(cell_text)},
                            "textStyle": {"foregroundColor": {"color": {"rgbColor": color}}},
                            "fields": "foregroundColor"
                        }
                    })
                except (TypeError, ValueError):
                    pass

    for col_i, width in enumerate(col_widths):
        style_requests.append({
            "updateTableColumnProperties": {
                "tableStartLocation": {"index": table_start_index},
                "columnIndices": [col_i],
                "tableColumnProperties": {
                    "widthType": "FIXED_WIDTH",
                    "width": {"magnitude": width, "unit": "PT"}
                },
                "fields": "widthType,width"
            }
        })

    docs.documents().batchUpdate(documentId=doc_id, body={"requests": style_requests}).execute()
    print(f"Done: https://docs.google.com/document/d/{doc_id}/edit")


def fmt_pct(val):
    if val is None:
        return "N/A"
    return f"{val:+.2f}%"


def generate_market_report(rows):
    summary_lines = []
    for r in rows:
        summary_lines.append(
            f"{r['company_name']} ({r['ticker']}): close={r['close_price']}, "
            f"1D={fmt_pct(r['change_1d_pct'])}, 1W={fmt_pct(r['change_1w_pct'])}, "
            f"1M={fmt_pct(r['change_1m_pct'])}, 3M={fmt_pct(r['change_3m_pct'])}, "
            f"1Y={fmt_pct(r['change_1y_pct'])}"
        )
    data_text = "\n".join(summary_lines)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        thinking={"type": "adaptive"},
        messages=[{
            "role": "user",
            "content": (
                f"Here is today's tech stock data:\n\n{data_text}\n\n"
                "Based on these numbers, write a concise ~200 word market analysis report. "
                "Identify key trends, notable performers (positive and negative), and where "
                "the market could be heading in the near term. Be direct and insightful."
            )
        }]
    )

    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def append_report_to_doc(docs, doc_id, report_text):
    doc = docs.documents().get(documentId=doc_id).execute()
    end_index = doc["body"]["content"][-1]["endIndex"] - 1

    heading = "AI Market Analysis\n"
    full_text = heading + report_text + "\n"

    insert_requests = [
        {"insertText": {"location": {"index": end_index}, "text": "\n" + full_text}}
    ]
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": insert_requests}).execute()

    # Re-fetch to style the heading
    doc = docs.documents().get(documentId=doc_id).execute()
    for elem in doc["body"]["content"]:
        if "paragraph" in elem:
            para = elem["paragraph"]
            text = "".join(r.get("textRun", {}).get("content", "") for r in para.get("elements", []))
            if "AI Market Analysis" in text:
                start = elem["startIndex"]
                end = elem["endIndex"] - 1
                docs.documents().batchUpdate(documentId=doc_id, body={"requests": [{
                    "updateParagraphStyle": {
                        "range": {"startIndex": start, "endIndex": end},
                        "paragraphStyle": {"namedStyleType": "HEADING_2"},
                        "fields": "namedStyleType"
                    }
                }]}).execute()
                break

    print("Market report appended.")


def send_email_report(creds, doc_id, date):
    if not os.path.exists("recipients.json"):
        print("No recipients.json found, skipping email.")
        return

    with open("recipients.json") as f:
        data = json.load(f)

    recipients = data.get("recipients", [])
    if not recipients:
        print("No recipients listed, skipping email.")
        return

    gmail = build("gmail", "v1", credentials=creds)
    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    for r in recipients:
        body = f"""Hi {r['name']},

Your daily Tech Stock Report for {date} is ready.

View it here: {doc_url}

This report includes live price data for 20 major tech stocks and an AI-generated market analysis.

Regards,
Stock Tracker Bot"""

        message = MIMEText(body)
        message["to"] = r["email"]
        message["subject"] = f"Tech Stock Report — {date}"
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        gmail.users().messages().send(userId="me", body={"raw": raw}).execute()
        print(f"Email sent to {r['email']}")


if __name__ == "__main__":
    print("Authenticating with Google...")
    creds = authenticate()
    docs = build("docs", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)

    print("Fetching stock data...")
    data = fetch_stock_data()
    if not data:
        print("No data fetched.")
        exit(1)

    date = data[0]["date"]
    doc_id, _ = get_or_create_doc(docs, drive)
    populate_doc(docs, doc_id, data)

    print("Generating AI market report...")
    report = generate_market_report(data)
    append_report_to_doc(docs, doc_id, report)

    print("Sending email report...")
    send_email_report(creds, doc_id, date)