# NoRes.py
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
import requests
from PriceTarget import find_price  # Import the find_price function

# Configuration for credentials
spreadsheet_key = "YOUR_SOURCING_SHEET_ID"
credentials_file = 'credentials1.json'

def get_gspread_client():
    """Create a gspread client using the specified credentials file."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    return gspread.authorize(creds)

# Initialize the Google Sheets client and fetch sheets
client = get_gspread_client()
sheet4 = client.open_by_key(spreadsheet_key).worksheet("sheet4")
sheet2 = client.open_by_key(spreadsheet_key).worksheet("sheet2")

# Fetch all rows from sheet4
data = sheet4.get_all_values()
header = data[0]  # Get header row for reference
rows = data[1:]  # Exclude header

# Process each row in sheet4
rows_to_remove = []
for index, row in enumerate(rows):
    if len(row) >= 4 and row[3]:  # Ensure there's a link in the fourth column
        link = row[3]
        print(f"Visiting link: {link}")

        # Send a request to the link with a 5-second timeout
        try:
            response = requests.get(link, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")

                # Extract the price using find_price function from PriceTarget.py
                price = find_price(soup)
                if price:
                    print(f"Price for {link}: {price}")
                    
                    # Define additional fields
                    web_cost = float(price)  # Assuming Web: Cost is the price found

                    # Parse other values needed for calculations
                    buy_box_current = float(row[5]) if row[5] else 0
                    fba_fees = float(row[7]) if row[7] else 0
                    referral_fee_current = float(row[9]) if row[9] else 0
                    pack = float(row[24]) if row[24] else 1  # Default to 1 if Pack is missing
                    web_pack = float(row[25]) if row[25] else 1  # Default to 1 if Web: Pack is missing

                    # Calculate Adjusted Price and Adjusted Cost
                    adjusted_price = buy_box_current / pack if pack else 0
                    adjusted_cost = web_cost / web_pack if web_pack else 0

                    # Calculate Profit and ROI
                    profit = adjusted_price - (fba_fees + referral_fee_current + adjusted_cost)
                    roi = (profit * 100 / adjusted_cost) if adjusted_cost else 0

                    # Construct the row for sheet2 in the specified column format
                    sheet2_row = [
                        row[0],  # Title
                        row[1],  # Sales Rank
                        row[2],  # ASIN
                        row[3],  # Web: Link
                        row[4] if len(row) > 4 else "",  # Amazon URL
                        row[5] if len(row) > 5 else "",  # Buy Box: Current
                        adjusted_price,  # Adjusted Price
                        row[7] if len(row) > 7 else "",  # FBA Fees
                        row[8] if len(row) > 8 else "",  # Referral Fee %
                        row[9] if len(row) > 9 else "",  # Referral Fee based on current Buy Box price
                        web_cost,  # Web: Cost
                        adjusted_cost,  # Web: Cost per unit
                        profit,  # Profit
                        roi,  # ROI
                        row[13] if len(row) > 13 else "",  # Buy Box: % Top Seller 90 days
                        row[14] if len(row) > 14 else "",  # Buy Box: % Top Seller 90 days
                        row[15] if len(row) > 15 else "",  # Buy Box: Lowest
                        row[16] if len(row) > 16 else "",  # Buy Box: 90 days drop %
                        row[17] if len(row) > 17 else "",  # Buy Box: Winner Count 90 days
                        row[18] if len(row) > 18 else "",  # Web: Title
                        row[19] if len(row) > 19 else "",  # Web: Description
                        row[20] if len(row) > 20 else "",  # Variation
                        row[21] if len(row) > 21 else "",  # Web: Variation
                        row[22] if len(row) > 22 else "",  # Pack
                        row[23] if len(row) > 23 else "",  # Web: Pack
                        row[24] if len(row) > 24 else "",  # Web: Pack
                    ] + [""] * (500 - 20)  # Extend row to match the exact column count with empty strings

                    # Append the row to sheet2
                    sheet2.append_row(sheet2_row, value_input_option="USER_ENTERED")

                    # Mark this row for removal from sheet4
                    rows_to_remove.append(index + 2)  # Adjust for header offset in Google Sheets
                else:
                    print(f"No price found for {link}")
            else:
                print(f"Failed to fetch {link}: Status code {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"Request to {link} timed out after 5 seconds. Skipping.")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {link}: {e}")

# Remove processed rows from sheet4 in reverse order to avoid indexing issues
for row_index in sorted(rows_to_remove, reverse=True):
    sheet4.delete_rows(row_index)  # Change to delete_rows

print("Data extraction complete.")