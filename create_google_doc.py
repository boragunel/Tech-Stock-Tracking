import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from fetch_stocks import fetch_stock_data

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive"
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


def get_or_create_doc(docs):
    if os.path.exists(DOC_ID_FILE):
        with open(DOC_ID_FILE) as f:
            doc_id = f.read().strip()
        print(f"Updating existing document: {doc_id}")
        # Clear all content
        doc = docs.documents().get(documentId=doc_id).execute()
        body = doc["body"]["content"]
        end_index = body[-1]["endIndex"] - 1
        if end_index > 1:
            docs.documents().batchUpdate(documentId=doc_id, body={"requests": [{
                "deleteContentRange": {
                    "range": {"startIndex": 1, "endIndex": end_index}
                }
            }]}).execute()
        return doc_id, False
    else:
        title = f"Tech Stock Report"
        doc = docs.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]
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


if __name__ == "__main__":
    print("Authenticating with Google...")
    creds = authenticate()
    docs = build("docs", "v1", credentials=creds)

    print("Fetching stock data...")
    data = fetch_stock_data()
    if not data:
        print("No data fetched.")
        exit(1)

    date = data[0]["date"]
    doc_id, _ = get_or_create_doc(docs)
    populate_doc(docs, doc_id, data)