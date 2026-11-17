import gspread
from google.oauth2.service_account import Credentials
import time
import re
from datetime import datetime

# ---------- Configuration ----------
SOURCE_SHEET_ID = "YOUR_ORDERS_SHEET_ID"
SOURCE_TAB_NAME = "TOSHIP"

DEST_SHEET_ID = "YOUR_LABELS_SHEET_ID"
DEST_TAB_NAME = "Sheet1"

CREDENTIAL_PREFIX = "credentials"
MAX_CREDENTIALS = 23

# ---------- Fixed Sender Info ----------
sender_info = [
    "YOUR NAME",          # FromName
    "",                   # PhoneFrom
    "YOUR STREET ADDRESS",# Street1From
    "",                   # CompanyFrom
    "",                   # Street2From
    "YOUR CITY",          # CityFrom
    "YOUR STATE",         # StateFrom
    "YOUR ZIP"            # PostalCodeFrom
]


def get_client_with_rotating_credentials():
    for i in range(1, MAX_CREDENTIALS + 1):
        try:
            creds_file = f"{CREDENTIAL_PREFIX}{i}.json"
            creds = Credentials.from_service_account_file(
                creds_file, scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            client = gspread.authorize(creds)
            print(f"✅ Using {creds_file}")
            return client
        except Exception as e:
            print(f"❌ Skipping {creds_file} — {e}")

    raise Exception("🚫 All credential files failed!")


# ---------- Load Sheets ----------
gc = get_client_with_rotating_credentials()
src_sheet = gc.open_by_key(SOURCE_SHEET_ID).worksheet(SOURCE_TAB_NAME)
src_data = src_sheet.get_all_values()

raw_header = src_data[0]
header_map = {h.strip().lower(): idx for idx, h in enumerate(raw_header)}

# ---------- Required columns ----------
required_cols = [
    "labels",
    "to name",
    "customer contact",
    "to street",
    "to street 2",
    "to city",
    "to state",
    "to postal",
    "productname",
    "pack of",
    "orderid",
    "length",
    "width",
    "height",
    "weight",
    "quantity",
    "amazon link",
    "buyer name",
    "deliver by",
]

missing = [col for col in required_cols if col not in header_map]
if missing:
    raise Exception(f"❌ Missing columns in TOSHIP: {missing}")

# ---------- Filter Rows Where "Labels" == "yes" ----------
rows_to_transfer = [
    row
    for row in src_data[1:]
    if len(row) > header_map["labels"]
    and row[header_map["labels"]].strip().lower() == "yes"
]


# ---------- Helper Functions ----------
def get(col, row):
    return row[header_map[col]].strip() if header_map[col] < len(row) else ""


def shorten_product_name(name):
    words = name.split()
    return " ".join(words[:12])


def extract_short_date(date_str):
    try:
        last_part = date_str.strip().split("to")[-1].strip()
        cleaned = re.sub(r"\s+\b[A-Z]{2,4}\b$", "", last_part)
        dt = datetime.strptime(cleaned, "%a, %b %d, %Y")
        return dt.strftime("%d %b")
    except Exception as e:
        print(f"⚠️ Failed to parse delivery date: '{date_str}' — {e}")
        return ""


# ---------- Transform Rows ----------
batch_data = []
sequence_no = 1

for row in rows_to_transfer:
    try:
        quantity = int(float(get("quantity", row))) if get("quantity", row) else 1
    except ValueError:
        print(f"⚠️ Skipping row with invalid quantity: {get('quantity', row)}")
        continue

    try:
        pack_of = int(float(get("pack of", row))) if get("pack of", row) else 1
    except ValueError:
        pack_of = 1

    try:
        weight = float(get("weight", row)) if get("weight", row) else 0.0
        length = float(get("length", row)) if get("length", row) else 0.0
        width = float(get("width", row)) if get("width", row) else 0.0
        height = float(get("height", row)) if get("height", row) else 0.0
    except ValueError:
        print("⚠️ Skipping row with invalid dimensions.")
        continue

    product_name = shorten_product_name(get("productname", row))
    delivery_date = extract_short_date(get("deliver by", row))

    # ==========================================================
    # OLD WEIGHT / QUANTITY SPLITTING LOGIC DISABLED
    # This old logic was creating multiple label rows based on
    # weight, quantity, and the 8 lb limit.
    #
    # while quantity > 0:
    #     if weight * quantity <= 8:
    #         final_qty = quantity
    #         quantity = 0
    #     elif weight > 8:
    #         final_qty = 1
    #         quantity -= 1
    #     else:
    #         for split_qty in range(1, quantity + 1):
    #             if weight * split_qty > 8:
    #                 break
    #         final_qty = split_qty - 1 if split_qty > 1 else 1
    #         quantity -= final_qty
    # ==========================================================

    # ---------- New Logic ----------
    # No splitting.
    # One order/person = one label row only.
    final_qty = quantity
    final_units = final_qty * pack_of

    desc = f"[Unit:{final_units},{delivery_date}] {product_name} | Units: {final_units} | Reach by: {delivery_date}"

    final_row = [
        str(sequence_no),  # A: No
        *sender_info,  # B to I: Sender Info
        get("to name", row),  # J: ToName
        get("customer contact", row),  # K: PhoneTo
        get("to street", row),  # L: Street1To
        "",  # M: CompanyTo
        get("to street 2", row),  # N: Street2To
        get("to city", row),  # O: CityTo
        get("to postal", row),  # P: ZipTo
        get("to state", row),  # Q: StateTo
        # Total order weight/dimensions in one row
        str(round(weight * final_qty, 2)),  # R: Weight(lb)
        str(round(length * final_qty, 2)),  # S: Length
        str(round(width * final_qty, 2)),  # T: Width
        str(round(height * final_qty, 2)),  # U: Height
        desc,  # V: Description
        str(pack_of),  # W: Pack of
        get("amazon link", row),  # X: Amazon Link
        get("buyer name", row),  # Y: Buyer Name
        get("orderid", row),  # Z: Order ID
        str(final_qty),  # AA: Quantity
    ]

    batch_data.append(final_row)
    sequence_no += 1

# ---------- Append to Label Sheet ----------
if batch_data:
    try:
        dest_sheet = gc.open_by_key(DEST_SHEET_ID).worksheet(DEST_TAB_NAME)
        dest_sheet.append_rows(batch_data, value_input_option="RAW")
        print(
            f"✅ Successfully transferred {len(batch_data)} rows where 'Labels' == yes."
        )
    except gspread.exceptions.APIError as e:
        print("🚫 Google Sheets API error:", e)
        print("🔁 Waiting 60 seconds and retrying...")
        time.sleep(60)

        gc = get_client_with_rotating_credentials()
        dest_sheet = gc.open_by_key(DEST_SHEET_ID).worksheet(DEST_TAB_NAME)
        dest_sheet.append_rows(batch_data, value_input_option="RAW")
        print(f"✅ Successfully transferred after retrying {len(batch_data)} rows.")
else:
    print("ℹ️ No rows found with 'Labels' == yes. Nothing to transfer.")
