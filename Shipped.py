from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# Google Sheets setup
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_ORDERS_SHEET_ID/edit?gid=1875445657#gid=1875445657"
SHIPPED_SHEET_NAME = "SHIPPED"
TOSHIP_SHEET_NAME = "TOSHIP"

# Function to authenticate with Google Sheets
def get_gspread_client():
    credentials_file = "credentials1.json"  # Update with the correct credentials file
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    return gspread.authorize(credentials)

# Extract order IDs from HTML content
def extract_order_ids(driver):
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")
    order_ids = []

    for div in soup.find_all("div", class_="cell-body-title"):
        link_tag = div.find("a", href=True)
        if link_tag:
            relative_url = link_tag["href"].strip()
            if relative_url.startswith("/orders-v3/order/"):
                order_id = link_tag.text.strip()
                order_ids.append(order_id)

    return order_ids

# Append unique orders to Google Sheets
def append_to_shipped_sheet(order_ids, client):
    shipped_sheet = client.open_by_url(SPREADSHEET_URL).worksheet(SHIPPED_SHEET_NAME)
    existing_orders = set(shipped_sheet.col_values(1))  # Column 1 contains order IDs

    new_order_ids = []
    for order_id in order_ids:
        if order_id in existing_orders:
            print(f"Duplicate order ID encountered: {order_id}. Stopping further extraction.")
            return False  # Stop further extraction when a duplicate is found
        new_order_ids.append(order_id)

    if not new_order_ids:
        print("No new orders to append.")
        return True

    # Append new order IDs starting from row[1]
    for order_id in new_order_ids:
        shipped_sheet.append_row([order_id], value_input_option="USER_ENTERED")

    print(f"Appended {len(new_order_ids)} new orders to the 'SHIPPED' sheet.")
    return True

# Update SHIPPED sheet with rows from TOSHIP sheet
def update_shipped_with_toship(client):
    shipped_sheet = client.open_by_url(SPREADSHEET_URL).worksheet(SHIPPED_SHEET_NAME)
    toship_sheet = client.open_by_url(SPREADSHEET_URL).worksheet(TOSHIP_SHEET_NAME)

    shipped_rows = shipped_sheet.get_all_values()[1:]
    toship_rows = toship_sheet.get_all_values()[1:]

    shipped_order_ids = {
        (index + 2, row[0])
        for index, row in enumerate(shipped_rows)
        if row[0] and (len(row) < 3 or not row[2])  # Ensure row[2] exists
    }

    for toship_index, toship_row in enumerate(toship_rows, start=2):
        if len(toship_row) > 1:
            toship_order_id = toship_row[1]

            for shipped_row_index, shipped_order_id in shipped_order_ids:
                if toship_order_id == shipped_order_id:
                    # Update using the full row, regardless of how many columns
                    col_count = len(toship_row)
                    end_col_letter = gspread.utils.rowcol_to_a1(1, col_count).rstrip('1')
                    range_str = f"A{shipped_row_index}:{end_col_letter}{shipped_row_index}"

                    shipped_sheet.update(range_name=range_str, values=[toship_row])
                    print(f"Updated order ID {toship_order_id} in SHIPPED at row {shipped_row_index}.")

                    # Remove the row from TOSHIP
                    toship_sheet.delete_rows(toship_index)
                    print(f"Removed order ID {toship_order_id} from TOSHIP.")
                    break

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

# Main function
def main():
    # Initialize WebDriver
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        # Open Amazon Seller Central Orders page
        print("Opening Amazon Seller Central Orders page...")
        driver.get("https://sellercentral.amazon.com/orders-v3/mfn/shipped?page=1")

        # Pause for manual login if necessary
        input("Please log in to Amazon Seller Central and press Enter to continue...")

        # Authenticate Google Sheets
        print("Authenticating with Google Sheets...")
        client = get_gspread_client()

        while True:
            # Extract order IDs from the current page
            print("Extracting order IDs...")
            order_ids = extract_order_ids(driver)
            print(f"Extracted {len(order_ids)} order IDs.")

            # Append order IDs to the SHIPPED sheet
            print("Appending order IDs to the 'SHIPPED' sheet...")
            should_continue = append_to_shipped_sheet(order_ids, client)

            if not should_continue:
                print("Duplicate order encountered or no new orders. Stopping.")
                break

            # Click the Next button to move to the next page
            print("Navigating to the next page...")
            if not click_next_button(driver):
                print("No more pages to navigate. Exiting.")
                break

        # Update SHIPPED with data from TOSHIP
        print("Updating SHIPPED with matching rows from TOSHIP...")
        update_shipped_with_toship(client)

    finally:
        driver.quit()
        print("WebDriver closed.")

# Run the script
if __name__ == "__main__":
    main()
