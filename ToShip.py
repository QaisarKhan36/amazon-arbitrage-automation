from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
)
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets setup
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_ORDERS_SHEET_ID/edit?gid=1875445657#gid=1875445657"
SHEET_NAME = "TOSHIP"
DROPSHIPINVENTORY = "2StepInventory"
OUTPUT_HTML_FILE = "OutputSoup.html"

# Global variables for credentials management
credentials_number = 1  # Start with the first credentials file
max_credentials = 24  # Maximum number of credential files available


# Function to authenticate with Google Sheets
def get_gspread_client():
    global credentials_number
    credentials_file = f"credentials{credentials_number}.json"
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        credentials_file, scope
    )
    return gspread.authorize(credentials)


# Handle API quota errors and switch credentials
def switch_credentials_if_needed(client, spreadsheet_url):
    global credentials_number
    try:
        return client.open_by_url(spreadsheet_url).worksheet(SHEET_NAME)
    except gspread.exceptions.APIError as e:
        if "Quota" in str(e) and credentials_number < max_credentials:
            credentials_number += 1
            print(f"Quota exceeded. Switching to credentials {credentials_number}...")
            client = get_gspread_client()
            return switch_credentials_if_needed(client, spreadsheet_url)
        else:
            raise Exception(
                "Reached max credential switches or encountered a non-quota error."
            )


# Extract order IDs from HTML content
def extract_order_ids(driver):
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    order_links = []
    for row in soup.select("tr"):
        # Find the order number link
        link_tag = row.select_one('a[href*="/orders-v3/order/"]')
        if not link_tag:
            continue

        order_id = link_tag.text.strip()
        full_url = f"https://sellercentral.amazon.com{link_tag['href'].strip()}"

        # Find quantity in the same row (default 1)
        quantity = 1
        quantity_label = row.find("span", string="Quantity")
        if quantity_label:
            quantity_value = quantity_label.find_next("b")
            if quantity_value:
                try:
                    quantity = int(float(quantity_value.text.strip()))
                except Exception:
                    quantity = 1

        order_links.append((order_id, full_url, quantity))

    return order_links


def get_dropship_inventory_sheet(client):
    spreadsheet = client.open_by_url(
        SPREADSHEET_URL
    )  # Open the spreadsheet directly here
    return spreadsheet.worksheet(DROPSHIPINVENTORY)  # Now access the specific worksheet


def get_inventory_sheets(client):
    """
    Return a dict of inventory worksheet objects (or None if missing).
    Keys: "2StepInventory", "OnlineArbitrage", "wholesaleInventory"
    """
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    names = [DROPSHIPINVENTORY, "OnlineArbitrage", "wholesaleInventory"]
    sheets = {}
    for name in names:
        try:
            sheets[name] = spreadsheet.worksheet(name)
        except Exception as e:
            print(f"⚠️ Could not open inventory sheet '{name}': {e}")
            sheets[name] = None
    return sheets


# Get the Next button and click it if available
def click_next_button(driver):
    try:
        next_button = driver.find_element(By.XPATH, "//li[@class='a-last']/a")
        if next_button.is_displayed():
            next_button.click()
            time.sleep(5)  # Wait for the page to load
            return True
    except (NoSuchElementException, ElementClickInterceptedException):
        return False
    return False


# Append unique orders to Google Sheets in batches
def append_unique_orders(order_links):
    client = get_gspread_client()
    sheet_toship = switch_credentials_if_needed(client, SPREADSHEET_URL)

    # Also open the labelCreatedNotShipped sheet
    try:
        sheet_label = client.open_by_url(SPREADSHEET_URL).worksheet(
            "labelCreatedNotShipped"
        )
        existing_label_orders = set(sheet_label.col_values(2))  # Order IDs in column 2
    except Exception as e:
        print(f"Error accessing 'labelCreatedNotShipped': {e}")
        existing_label_orders = set()

    # Existing orders in TOSHIP
    existing_toship_orders = set(sheet_toship.col_values(2))
    all_existing_orders = existing_toship_orders.union(existing_label_orders)

    # new_orders must unpack the 3-tuple (order_id, order_url, quantity)
    new_orders = [
        (order_id, order_url, quantity)
        for order_id, order_url, quantity in order_links
        if order_id not in all_existing_orders
    ]

    if not new_orders:
        print("No new orders to append.")
        return

    batch_data = []
    for order_id, order_url, quantity in new_orders:
        row_data = ["", ""] * 0  # placeholder initialization not needed here

        # Create a row with exactly 28 columns (AB is column 28)
        row_data = [""] * 28
        row_data[0] = order_url  # Column A
        row_data[1] = order_id  # Column B
        row_data[27] = quantity  # Column AB (index 27 because 0-based list)

        batch_data.append(row_data)

    if batch_data:
        sheet_toship.append_rows(batch_data, value_input_option="USER_ENTERED")
        print(f"Uploaded {len(batch_data)} remaining rows.")

    print(f"{len(new_orders)} new orders appended to the TOSHIP sheet.")


# Extract all row[0] values with no corresponding row[2]
def get_row0_with_missing_row2(sheet):
    row0_values = []
    all_values = sheet.get_all_values()

    for row in all_values:
        if len(row) > 2 and row[0].strip() and not row[2].strip():
            row0_values.append(row[0])

    return row0_values


def simplify(price_text):
    try:
        # Remove 'US$' and any surrounding whitespace, then convert to float
        return float(price_text.replace("US$", "").strip())
    except ValueError:
        return None


def get_column_letter(col_index):
    col_letter = ""
    while col_index > 0:
        col_index, remainder = divmod(col_index - 1, 26)
        col_letter = chr(65 + remainder) + col_letter
    return col_letter


def process_batch(sheet, batch_updates):
    if not batch_updates:
        return

    requests = []

    for update in batch_updates:
        row_number = update["row_number"]
        for col_index, value in update["updates"].items():
            if value is not None:
                try:
                    col_letter = get_column_letter(col_index)
                    cell_range = f"{col_letter}{row_number}"
                    requests.append(
                        {
                            "range": cell_range,
                            "values": [[str(value)]],
                        }
                    )
                except Exception as e:
                    print(f"Failed to prepare batch update for cell {cell_range}: {e}")

    try:
        # Break requests into chunks of 50 (to avoid large batch payload)
        for i in range(0, len(requests), 50):
            chunk = requests[i : i + 50]
            sheet.batch_update(chunk)
        print(f"Successfully batch updated {len(requests)} cells.")
    except gspread.exceptions.APIError as e:
        print(f"Batch update failed: {e}")

    batch_updates.clear()


def visit_links_and_update_sheet(
    driver, sheet, dropship_sheet, inventory_sheets, links
):
    column_map = {
        "OrderID": 1,
        "Order Item ID": 2,
        "Fulfillment": 3,
        "Buyer Name": 4,
        "ProductName": 5,
        "Asin": 6,
        "Web: Link": 7,
        "Amazon Link": 8,
        "Cost": 9,
        "FBAPickFee": 10,
        "ReferralFeePct": 11,
        "ReferralFee": 12,
        "Shipping": 13,
        "Price": 14,
        "Subtotal": 15,
        "Profit": 16,
        "Roi": 17,  # Ship to was 18 — removed
        "To Name": 18,
        "To Street": 19,
        "To Second Street": 20,
        "To City": 21,
        "To State": 22,
        "To Postal": 23,
        "Purchase Date": 24,
        "Ship By": 25,
        "Deliver By": 26,
        "customer contact": 27,  # was 28
        "shipping status": 28,  # was 30
        "pack of": 29,  # was 32
        "Length": 30,  # was 33
        "Width": 31,  # was 34
        "height": 32,  # was 35
        "Weight": 33,  # was 36
        "status": 34,  # was 37
    }

    batch_updates = []  # This will store the updates for up to 10 rows

    # Build an ASIN -> (sheet_name, sheet_obj, row_index) lookup using column C of each inventory sheet.
    inventory_lookup = {}  # asin_str -> (sheet_name, sheet_obj, row_idx)
    if isinstance(inventory_sheets, dict):
        for inv_name, inv_sheet in inventory_sheets.items():
            if not inv_sheet:
                continue
            try:
                col_c = inv_sheet.col_values(3)  # column C
                for idx, val in enumerate(col_c, start=1):
                    if val and val.strip():
                        key = val.strip()
                        # first occurrence wins
                        if key not in inventory_lookup:
                            inventory_lookup[key] = (inv_name, inv_sheet, idx)
            except Exception as e:
                print(f"⚠️ Could not build lookup for {inv_name}: {e}")

    for link in links:
        try:
            # Identify the row to update
            try:
                cell = sheet.find(link)
            except gspread.exceptions.CellNotFound:
                print(f"Link {link} not found in sheet. Skipping...")
                continue

            row_number = cell.row
            print(f"Processing row {row_number} for link {link}...")

            updates = {}

            # Visit the link
            driver.get(link)
            time.sleep(5)  # Wait for the page to load

            # Extract details
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            extracted_details = {}

            extraction_targets = {
                "ASIN": lambda: (
                    soup.find("div", class_="product-name-column-word-wrap-break-all")
                    .find("b")
                    .text.strip()
                    if soup.find(
                        "div", class_="product-name-column-word-wrap-break-all"
                    )
                    and soup.find(
                        "div", class_="product-name-column-word-wrap-break-all"
                    ).find("b")
                    else None
                ),
                "Subtotal": lambda: (
                    soup.find("span", class_="a-color-")
                    .text.strip()
                    .replace("US$", "")
                    .strip()
                    if soup.find("span", class_="a-color-")
                    else None
                ),
                "Ship By": lambda: (
                    soup.find(
                        "span", {"data-test-id": "order-summary-shipby-value"}
                    ).text.strip()
                    if soup.find("span", {"data-test-id": "order-summary-shipby-value"})
                    else None
                ),
                "Deliver By": lambda: (
                    soup.find(
                        "span", {"data-test-id": "order-summary-deliverby-value"}
                    ).text.strip()
                    if soup.find(
                        "span", {"data-test-id": "order-summary-deliverby-value"}
                    )
                    else None
                ),
                "Purchase Date": lambda: (
                    soup.find(
                        "span", {"data-test-id": "order-summary-purchase-date-value"}
                    ).text.strip()
                    if soup.find(
                        "span", {"data-test-id": "order-summary-purchase-date-value"}
                    )
                    else None
                ),
                "Ship To": lambda: (
                    "\n".join(
                        [
                            span.text.strip()
                            for span in soup.find(
                                "div",
                                {"data-test-id": "shipping-section-buyer-address"},
                            ).find_all("span")
                        ]
                    )
                    if soup.find(
                        "div", {"data-test-id": "shipping-section-buyer-address"}
                    )
                    else None
                ),
                "Phone": lambda: (
                    soup.find(
                        "span", {"data-test-id": "shipping-section-phone"}
                    ).text.strip()
                    if soup.find("span", {"data-test-id": "shipping-section-phone"})
                    else None
                ),
                "Buyer Name": lambda: (
                    soup.find(
                        "a", {"data-test-id": "buyer-name-with-link"}
                    ).text.strip()
                    if soup.find("a", {"data-test-id": "buyer-name-with-link"})
                    else None
                ),
                "Status": lambda: (
                    soup.find("span", {"class": "main-status"}).text.strip()
                    if soup.find("span", {"class": "main-status"})
                    else None
                ),
                "Shipping Service": lambda: (
                    soup.find(
                        "span", {"data-test-id": "order-summary-shipping-service-value"}
                    )
                    .find("span")
                    .text.strip()
                    if soup.find(
                        "span", {"data-test-id": "order-summary-shipping-service-value"}
                    )
                    else None
                ),
                "Fulfillment": lambda: (
                    soup.find(
                        "span",
                        {"data-test-id": "order-summary-fulfillment-channel-value"},
                    )
                    .find("span")
                    .text.strip()
                    if soup.find(
                        "span",
                        {"data-test-id": "order-summary-fulfillment-channel-value"},
                    )
                    else None
                ),
            }

            extraction_targets.update(
                {
                    "Title": lambda: (
                        soup.find("span", {"id": "productTitle"}).text.strip()
                        if soup.find("span", id="productTitle")
                        else None
                    ),
                    "Sales Rank": lambda: (
                        soup.find(string="Best Sellers Rank").find_next().text.strip()
                        if soup.find(string="Best Sellers Rank")
                        else None
                    ),
                    "Buy Box Price": lambda: (
                        soup.select_one("#priceblock_ourprice, #priceblock_dealprice")
                        .text.strip()
                        .replace("US$", "")
                        if soup.select_one(
                            "#priceblock_ourprice, #priceblock_dealprice"
                        )
                        else None
                    ),
                    "FBAPickFee": lambda: (
                        soup.find(string="FBA Pick&Pack Fee")
                        .find_next()
                        .text.strip()
                        .replace("US$", "")
                        if soup.find(string="FBA Pick&Pack Fee")
                        else None
                    ),
                    "ReferralFeePct": lambda: (
                        soup.find(string="Referral Fee")
                        .find_next()
                        .text.strip()
                        .replace("%", "")
                        if soup.find(string="Referral Fee")
                        else None
                    ),
                    "Variation": lambda: (
                        soup.select_one("#variation_size_name .selection").text.strip()
                        if soup.select_one("#variation_size_name .selection")
                        else None
                    ),
                    "PackageLength": lambda: (
                        soup.find(string="Package Dimensions")
                        .find_next("td")
                        .text.split(" x ")[0]
                        .strip()
                        if soup.find(string="Package Dimensions")
                        else None
                    ),
                    "PackageWidth": lambda: (
                        soup.find(string="Package Dimensions")
                        .find_next("td")
                        .text.split(" x ")[1]
                        .strip()
                        if soup.find(string="Package Dimensions")
                        else None
                    ),
                    "PackageHeight": lambda: (
                        soup.find(string="Package Dimensions")
                        .find_next("td")
                        .text.split(" x ")[2]
                        .strip()
                        if soup.find(string="Package Dimensions")
                        else None
                    ),
                    "PackageWeight": lambda: (
                        soup.find(string="Item Weight").find_next("td").text.strip()
                        if soup.find(string="Item Weight")
                        else None
                    ),
                }
            )

            # Extract details
            for key, extractor in extraction_targets.items():
                try:
                    extracted_details[key] = extractor()
                except Exception:
                    extracted_details[key] = None

            # ----------------------------
            # Extract shipping price (put into extracted_details["Shipping"])
            # This will end up in column M because column_map maps "Shipping": 13
            # ----------------------------
            try:
                # Search the raw HTML for patterns like: "Shipping total ... US$4.99"
                shipping_match = re.search(
                    r"Shipping total.*?US\$([\d\.,]+)", html, re.DOTALL
                )
                if shipping_match:
                    # Normalize (remove thousands comma) and convert to float if possible
                    shipping_str = shipping_match.group(1).replace(",", "").strip()
                    try:
                        shipping_val = float(shipping_str)
                        extracted_details["Shipping"] = shipping_val
                    except Exception:
                        # fallback to raw string if float conversion fails
                        extracted_details["Shipping"] = shipping_str
                else:
                    # keep existing value (if any) or set empty
                    if "Shipping" not in extracted_details:
                        extracted_details["Shipping"] = ""
            except Exception as e:
                print(f"⚠️ Shipping extraction failed for link {link}: {e}")
                if "Shipping" not in extracted_details:
                    extracted_details["Shipping"] = ""

            asin = extracted_details.get("ASIN")
            pack_of_value = None  # default: not found

            if asin:
                target_asin = asin.strip()
                # 1) Try fast lookup built from inventory col C's
                try:
                    entry = inventory_lookup.get(target_asin)
                    if entry:
                        inv_name, inv_sheet_obj, inv_row_idx = entry
                        try:
                            inv_row_vals = inv_sheet_obj.row_values(inv_row_idx)
                            # Column T is the 20th column -> index 19 in the returned list
                            pack_val = (
                                inv_row_vals[19] if len(inv_row_vals) >= 20 else ""
                            )
                            if pack_val is not None and str(pack_val).strip() != "":
                                try:
                                    pack_of_value = int(float(str(pack_val).strip()))
                                except Exception:
                                    pack_of_value = str(pack_val).strip()
                            # If this matched sheet is the dropship (2StepInventory), keep dropship_row too:
                            if inv_name == DROPSHIPINVENTORY and inv_row_vals:
                                extracted_details["dropship_row"] = inv_row_vals
                            print(
                                f"Found ASIN {target_asin} in {inv_name} row {inv_row_idx}, pack_of={pack_of_value}"
                            )
                        except Exception as e:
                            print(
                                f"⚠️ Error reading row {inv_row_idx} from {inv_name}: {e}"
                            )
                    else:
                        # fallback: attempt to find in dropship_sheet directly (older behavior)
                        try:
                            if dropship_sheet:
                                dropship_cell = dropship_sheet.find(target_asin)
                                if dropship_cell:
                                    dropship_row = dropship_sheet.row_values(
                                        dropship_cell.row
                                    )
                                    if dropship_row:
                                        extracted_details["dropship_row"] = dropship_row
                                else:
                                    print(
                                        "No match found in DropshipInventory (fallback)"
                                    )
                        except Exception as e:
                            print(
                                f"Error finding ASIN in DropshipInventory (fallback): {e}"
                            )
                except Exception as e:
                    print(f"Error during inventory lookup for ASIN {target_asin}: {e}")
            else:
                print("No ASIN extracted.")

            if pack_of_value is None or str(pack_of_value).strip() == "":
                pack_of_value = 1

            # Format Ship To as a single line
            ship_to_address = extracted_details.get("Ship To")
            if ship_to_address:
                address_lines = [
                    line.strip() for line in ship_to_address.split("\n") if line.strip()
                ]
                single_line_ship_to = ", ".join(address_lines)

                if len(address_lines) == 6:
                    to_name = address_lines[0]
                    to_street = address_lines[1]
                    to_street2 = address_lines[2]
                    to_city = address_lines[3]
                    to_state = address_lines[4]
                    to_postal = address_lines[5]
                else:
                    to_name = address_lines[0] if len(address_lines) > 0 else None
                    to_street = address_lines[1] if len(address_lines) > 1 else None
                    to_street2 = ""
                    to_city = address_lines[2] if len(address_lines) > 2 else None
                    to_state = address_lines[3] if len(address_lines) > 3 else None
                    to_postal = address_lines[4] if len(address_lines) > 4 else None

                extracted_details["Ship To"] = single_line_ship_to
                extracted_details["To Name"] = to_name
                extracted_details["To Street"] = to_street
                extracted_details["To Street 2"] = to_street2
                extracted_details["To City"] = to_city
                extracted_details["To State"] = to_state
                extracted_details["To Postal"] = to_postal

            # Main update values
            updates = {}
            for field, col_index in column_map.items():
                val = extracted_details.get(field)
                if val is not None:
                    updates[col_index] = val

            phone = extracted_details.get("Phone")
            # Write Phone to column AA (27)
            if extracted_details.get("Phone"):
                updates[27] = extracted_details["Phone"]

            # Write Shipping Service to column AC (29)
            if extracted_details.get("Shipping Service"):
                updates[29] = extracted_details["Shipping Service"]

            if "dropship_row" in extracted_details:
                dropship_row = extracted_details["dropship_row"]

                # F column - ASIN
                asin_match = dropship_row[2] if len(dropship_row) > 2 else ""
                updates[6] = asin_match

                # I column - Cost
                try:
                    cost = float(dropship_row[9]) if len(dropship_row) > 9 else 0
                except ValueError:
                    cost = 0
                updates[9] = cost

                # J column - FBA/FBM Fees
                try:
                    fba_fee = float(dropship_row[6]) if len(dropship_row) > 6 else 0
                except ValueError:
                    fba_fee = 0
                updates[10] = fba_fee

                # K column - Referral Fee %
                try:
                    referral_pct = (
                        float(dropship_row[7]) if len(dropship_row) > 7 else 0
                    )
                except ValueError:
                    referral_pct = 0
                updates[11] = referral_pct

                # L column - Referral Fee Value
                try:
                    referral_fee_val = (
                        float(dropship_row[8]) if len(dropship_row) > 8 else 0
                    )
                except ValueError:
                    referral_fee_val = 0
                updates[12] = referral_fee_val

                # Read quantity from the TOSHIP sheet (column C). If missing, default to 1.
                try:
                    q_val = sheet.cell(
                        row_number, 28
                    ).value  # AB is column 28 (1-based)
                    if q_val is None or str(q_val).strip() == "":
                        quantity = 1
                    else:
                        quantity = int(float(str(q_val).strip()))
                        if quantity < 1:
                            quantity = 1
                except Exception:
                    quantity = 1

                # Unit price from dropship_row index 5 (if present)
                try:
                    price = (
                        float(dropship_row[5])
                        if len(dropship_row) > 5 and dropship_row[5]
                        else 0
                    )
                except Exception:
                    price = 0

                # Subtotal scraped from the order page (if present)
                subtotal = 0
                try:
                    subtotal_str = extracted_details.get("Subtotal")
                    if subtotal_str:
                        subtotal = float(
                            str(subtotal_str)
                            .replace(",", "")
                            .replace("US$", "")
                            .strip()
                        )
                except Exception:
                    subtotal = 0

                # prefer explicit price from dropship inventory, otherwise derive from subtotal / quantity
                if price > 0:
                    final_price = price
                elif subtotal > 0 and quantity > 0:
                    final_price = round(subtotal / quantity, 2)
                else:
                    final_price = 0

                # Column L (referral fee numeric value) based on final_price and referral_pct
                try:
                    column_12_value = round(referral_fee_val * final_price / 100, 2)
                except Exception:
                    column_12_value = 0

                # Shipping and product cost (use different var names to avoid collisions)
                try:
                    shipping = (
                        float(dropship_row[7])
                        if len(dropship_row) > 7 and dropship_row[7]
                        else 0
                    )
                except Exception:
                    shipping = 0

                try:
                    product_cost = (
                        float(dropship_row[10])
                        if len(dropship_row) > 10 and dropship_row[10]
                        else 0
                    )
                except Exception:
                    product_cost = 0

                total_cost = (column_12_value + shipping + product_cost) * quantity
                profit = round(subtotal - total_cost, 2)

                try:
                    cost_basis = (shipping + product_cost) * quantity
                    roi = round(profit / cost_basis, 2) if cost_basis else 0
                except ZeroDivisionError:
                    roi = 0

                updates[30] = pack_of_value

                updates.update(
                    {
                        5: dropship_row[0],  # E - Product Name
                        7: dropship_row[3],  # G - Web Link
                        8: dropship_row[4],  # H - Amazon Link
                        12: column_12_value,  # L - Referral Fee value
                        14: final_price,  # N - Price
                        16: profit,  # P - Profit
                        17: roi,  # Q - ROI
                        24: extracted_details.get(
                            "Purchase Date"
                        ),  # Z - Purchase Date (moved from 27)
                        25: extracted_details.get(
                            "Ship By"
                        ),  # X - Ship By (moved from 25)
                        26: extracted_details.get(
                            "Deliver By"
                        ),  # Y - Deliver By (moved from 26)
                        27: extracted_details.get("Phone"),  # AA - Phone
                        29: extracted_details.get(
                            "Shipping Service"
                        ),  # AC - Shipping Service
                    }
                )

            updates[31] = dropship_row[20] if len(dropship_row) > 19 else ""
            updates[32] = dropship_row[21] if len(dropship_row) > 20 else ""
            updates[33] = dropship_row[22] if len(dropship_row) > 21 else ""
            updates[34] = dropship_row[23] if len(dropship_row) > 22 else ""

            # Set Phone to AA (column 27)
            if extracted_details.get("Phone"):
                updates[27] = extracted_details["Phone"]

            # Set Shipping Service to AC (column 29)
            if extracted_details.get("Shipping Service"):
                updates[29] = extracted_details["Shipping Service"]

            batch_updates.append({"row_number": row_number, "updates": updates})

            if len(batch_updates) >= 10:
                process_batch(sheet, batch_updates)

        except Exception as e:
            print(f"Failed to process {link}: {e}")

    process_batch(sheet, batch_updates)


def main():
    # Initialize WebDriver with ChromeDriver service
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Visit Amazon Seller Central orders page
    driver.get("https://sellercentral.amazon.com/orders-v3/mfn/unshipped?page=1")
    print("Please log in to Amazon Seller Central...")
    time.sleep(30)  # Adjust this time as needed for manual login
    input(
        "Press Enter to continue once you have logged in and are on the orders page..."
    )

    # Step 1: Extract and append order IDs
    while True:
        print("Extracting order IDs from the current page...")
        order_links = extract_order_ids(driver)
        append_unique_orders(order_links)

        if not click_next_button(driver):
            print("No 'Next' button found. Stopping pagination.")
            break

    # Step 2: Process rows with missing row[2]
    client = get_gspread_client()
    sheet = switch_credentials_if_needed(client, SPREADSHEET_URL)
    dropship_sheet = get_dropship_inventory_sheet(
        client
    )  # Add this line to get the dropship inventory sheet
    row0_values = get_row0_with_missing_row2(sheet)

    # Load all three inventory sheets (may be None if missing)
    inventory_sheets = get_inventory_sheets(client)

    print(f"Found {len(row0_values)} links to process.")
    with open("OutputSoup.html", "w", encoding="utf-8") as file:
        file.write(driver.page_source)

    # Pass inventory_sheets dict into the processor (new 4th arg)
    visit_links_and_update_sheet(
        driver, sheet, dropship_sheet, inventory_sheets, row0_values
    )

    # Close the browser
    driver.quit()


if __name__ == "__main__":
    main()
