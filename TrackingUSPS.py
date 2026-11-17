import os
import re
import gspread
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# ---------- Config ----------
SPREADSHEET_KEY = "YOUR_ORDERS_SHEET_ID"
SHEET_NAME = "SHIPPED"
CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"

START_ROW = 3
END_ROW = None
BATCH_SIZE = 5

# ---------- Globals ----------
credential_index = 1
sheet = 'SHIPPED'

# ---------- Helpers ----------
def get_sheet():
    global credential_index
    while credential_index <= 23:
        try:
            scope = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file(f"credentials{credential_index}.json", scopes=scope)
            client = gspread.authorize(creds)
            return client.open_by_key(SPREADSHEET_KEY).worksheet(SHEET_NAME)
        except Exception as e:
            print(f"🔄 Rotating credential... credentials{credential_index}.json failed: {e}")
            credential_index += 1
    raise RuntimeError("❌ All credentials exhausted.")

def extract_tracking_info(html):
    carrier = re.search(r'<span class="a-text-bold">Carrier<\/span><\/div><div[^>]*>\s*(.*?)<\/div>', html)
    tracking_id = re.search(r'data-test-id="tracking-id-value">(\d+)<', html)
    shipping_total = re.search(r'Shipping total.*?US\$([\d\.]+)', html, re.DOTALL)
    return {
        "carrier": carrier.group(1).strip() if carrier else "",
        "tracking": tracking_id.group(1).strip() if tracking_id else "",
        "shipping": shipping_total.group(1).strip() if shipping_total else ""
    }

def extract_usps_short_status(html):
    match = re.search(r'<p class="tb-status">(.*?)<\/p>', html)
    return match.group(1).strip() if match else ""

def wait_for(driver, by, value, timeout=20):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))

def init_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    return webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)

def update_cell_force(sheet, row, col, value):
    for _ in range(2):  # try twice
        try:
            sheet.update_cell(row, col, value)
            actual_value = sheet.cell(row, col).value
            if actual_value == value:
                print(f"✅ Updated row {row} col {col} with: {value}")
            else:
                print(f"⚠️ Update mismatch at row {row} col {col}: expected '{value}', got '{actual_value}'")
            break
        except Exception as e:
            print(f"⚠️ Error updating row {row} col {col}: {e}")
            rotate_sheet()


def rotate_sheet():
    global sheet
    global credential_index
    credential_index += 1
    if credential_index > 23:
        raise RuntimeError("❌ All credentials exhausted during sheet rotation.")
    print(f"🔄 Switching to credentials{credential_index}.json")
    sheet = get_sheet()

# ---------- Main ----------
def main():
    global sheet
    sheet = get_sheet()
    driver = init_driver()

    usps_tab_created = False
    all_links = sheet.col_values(1)
    total_rows = len(all_links)
    start = START_ROW or 2
    end = END_ROW if END_ROW else total_rows

    for batch_start in range(start, end + 1, BATCH_SIZE):
        for row in range(batch_start, min(batch_start + BATCH_SIZE, end + 1)):
            try:
                link = sheet.cell(row, 1).value
                if not link or not link.startswith("http"):
                    continue

                print(f"\n🔗 Visiting Amazon order page (row {row}): {link}")
                driver.switch_to.window(driver.window_handles[0]) if driver.window_handles else None
                driver.get(link)

                if row == start:
                    input("🔐 Login if needed, then press ENTER to continue...")

                time.sleep(3)
                html = driver.page_source
                data = extract_tracking_info(html)
                print(f"📦 Extracted: {data}")

                update_cell_force(sheet, row, 13, data["shipping"])  # M
                update_cell_force(sheet, row, 36, data["carrier"])   # AJ
                update_cell_force(sheet, row, 37, data["tracking"])  # AK

                if not usps_tab_created:
                    driver.execute_script("window.open('');")
                    driver.switch_to.window(driver.window_handles[1])
                    driver.get("https://tools.usps.com/go/TrackConfirmAction_input")
                    usps_tab_created = True
                else:
                    driver.switch_to.window(driver.window_handles[1])
                    driver.get("https://tools.usps.com/go/TrackConfirmAction_input")

                try:
                    textarea = wait_for(driver, By.ID, "tracking-input")
                    textarea.clear()
                    textarea.send_keys(data["tracking"])
                    time.sleep(1)
                    button = driver.find_element(By.CLASS_NAME, "tracking-btn")
                    driver.execute_script("arguments[0].click();", button)
                    print("📨 Submitted tracking number")
                except Exception as e:
                    print(f"❌ Failed to submit tracking: {e}")
                    continue

                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.latest-update-banner-wrapper p.banner-content"))
                    )
                except:
                    print("⚠️ Couldn't detect tracking result; continuing anyway.")

                html = driver.page_source
                soup = BeautifulSoup(html, "html.parser")
                latest_update_elem = soup.select_one("div.latest-update-banner-wrapper p.banner-content")
                if latest_update_elem:
                    status = latest_update_elem.get_text(strip=True)
                    update_cell_force(sheet, row, 38, status)  # AL
                else:
                    print("⚠️ Could not extract USPS full status.")

                short_status = extract_usps_short_status(html)
                if short_status:
                    update_cell_force(sheet, row, 39, short_status)  # AM - status like "Delivered", "In Transit"
                else:
                    print("⚠️ Could not extract USPS short status.")


            except Exception as err:
                print(f"🔥 Error processing row {row}: {err}")

    driver.quit()

if __name__ == "__main__":
    main()