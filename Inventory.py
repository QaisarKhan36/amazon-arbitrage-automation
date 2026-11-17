import gspread
from google.oauth2.service_account import Credentials
from time import sleep

# Import advanced inventory concepts
from InventoryConcepts import (
    compile_inventory_data,
    update_shipped_cost_column
)

# -------------- CONFIG -------------------
SERVICE_ACCOUNT_FILE = 'credentials1.json'

INVENTORY_SPREADSHEET_ID = 'YOUR_INVENTORY_SHEET_ID'
PARTNER_A_INVENTORY_SHEET_NAME = 'PartnerAPurchase'
PARTNER_B_INVENTORY_SHEET_NAME = 'PartnerBPurchase'

PARTNER_A_2STEP_SPREADSHEET_ID = 'YOUR_PARTNER_A_ORDERS_SHEET_ID'
PARTNER_B_2STEP_SPREADSHEET_ID = 'YOUR_PARTNER_B_ORDERS_SHEET_ID'
TWO_STEP_SHEET_NAME = '2StepInventory'
# -----------------------------------------

scopes = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
gc = gspread.authorize(creds)

# -------- BASIC CONCEPTS --------
def fetch_2step_map(sheet):
    """Maps ASIN → (Name, Amazon Link) from 2StepInventory sheet"""
    asin_map = {}
    all_data = sheet.get_all_values()
    for row in all_data[1:]:
        if len(row) >= 5:
            asin = row[2].strip()
            if asin:
                name = row[0].strip()
                amazon_link = row[4].strip()
                asin_map[asin] = (name, amazon_link)
    return asin_map

def process_inventory(inventory_ws, asin_map):
    """Fills in missing Name & Amazon Link in inventory sheets (PartnerA/PartnerB Purchase)"""
    records = inventory_ws.get_all_values()
    if not records:
        return
    headers = records[0]

    asin_col = headers.index("Asin")
    name_col = headers.index("Name")
    amazonlink_col = headers.index("Amazon Link")

    for idx, row in enumerate(records[1:], start=2):
        try:
            asin = row[asin_col].strip() if asin_col < len(row) else ''
            if not asin:
                continue

            already_has_data = all([
                row[name_col].strip() if name_col < len(row) else '',
                row[amazonlink_col].strip() if amazonlink_col < len(row) else ''
            ])
            if already_has_data:
                continue

            if asin not in asin_map:
                print(f"[SKIP] ASIN {asin} not found in 2StepInventory")
                continue

            name, amazon_link = asin_map[asin]

            if (name_col < len(row)) and not row[name_col].strip():
                inventory_ws.update_cell(idx, name_col + 1, name)
            if (amazonlink_col < len(row)) and not row[amazonlink_col].strip():
                inventory_ws.update_cell(idx, amazonlink_col + 1, amazon_link)

            print(f"[UPDATED] Row {idx} - ASIN {asin}")
            sleep(1)

        except Exception as e:
            print(f"[ERROR] Row {idx} - {str(e)}")

# -------- MAIN EXECUTION --------
def main():
    print("Loading Inventory Spreadsheet...")
    inventory_sheet = gc.open_by_key(INVENTORY_SPREADSHEET_ID)

    print("Processing PartnerA Inventory...")
    partner_a_inventory_ws = inventory_sheet.worksheet(PARTNER_A_INVENTORY_SHEET_NAME)
    partner_a_2step_ws = gc.open_by_key(PARTNER_A_2STEP_SPREADSHEET_ID).worksheet(TWO_STEP_SHEET_NAME)
    partner_a_asin_map = fetch_2step_map(partner_a_2step_ws)
    process_inventory(partner_a_inventory_ws, partner_a_asin_map)

    print("Processing PartnerB Inventory...")
    partner_b_inventory_ws = inventory_sheet.worksheet(PARTNER_B_INVENTORY_SHEET_NAME)
    partner_b_2step_ws = gc.open_by_key(PARTNER_B_2STEP_SPREADSHEET_ID).worksheet(TWO_STEP_SHEET_NAME)
    partner_b_asin_map = fetch_2step_map(partner_b_2step_ws)
    process_inventory(partner_b_inventory_ws, partner_b_asin_map)

    print("Compiling InventoryInStock sheet...")
    try:
        compile_inventory_data(gc)
    except Exception as e:
        print(f"[ERROR] Failed to compile InventoryInStock: {e}")
        raise

    print("Updating SHIPPED sheet costs...")
    update_shipped_cost_column(gc)

if __name__ == "__main__":
    main()
