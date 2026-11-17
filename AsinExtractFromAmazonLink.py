import gspread
import re
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets setup
SERVICE_ACCOUNT_FILE = 'credentials1.json'
SPREADSHEET_ID = 'YOUR_SOURCING_SHEET_ID'

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
client = gspread.authorize(creds)

# Open the spreadsheet and sheet
sheet = client.open_by_key(SPREADSHEET_ID).worksheet("sheet1")

# Get all links in col A starting from row 2
links = sheet.col_values(1)[1:]  # skip header

# Regex to extract ASIN from link
asin_pattern = re.compile(r"/dp/([A-Z0-9]{10})")

# Prepare update list
updates = []
for i, link in enumerate(links, start=2):
    match = asin_pattern.search(link)
    if match:
        asin = match.group(1)
        updates.append({'range': f"B{i}", 'values': [[asin]]})
    else:
        updates.append({'range': f"B{i}", 'values': [[""]]})


# Batch update
sheet.batch_update([{
    'range': u['range'],
    'values': u['values']
} for u in updates])

print("ASINs extracted and written to column B.")
