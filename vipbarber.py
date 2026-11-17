from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import json
import socket
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === CONFIGURATION ===
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SOURCING_SHEET_ID/edit#gid=337653138"
SHEET_NAME = "Sheet10"
BASE_URL = "https://www.vipbarbersupply.com/collections/brands-t-z?page="

# === BROWSER SETUP ===
chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
# chrome_options.add_argument("--headless")  # Optional

driver = webdriver.Chrome(service=Service(), options=chrome_options)

# === UTILITIES ===
def wait_for_connection(retry_interval=30):
    while True:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return
        except OSError:
            print("No internet. Retrying in 30 seconds...")
            time.sleep(retry_interval)

def get_sheet():
    for i in range(1, 24):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                f"credentials{i}.json",
                ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            )
            client = gspread.authorize(creds)
            sheet = client.open_by_url(SPREADSHEET_URL).worksheet(SHEET_NAME)
            print(f"Using credentials{i}.json")
            return sheet
        except Exception as e:
            print(f"credentials{i}.json failed: {e}")
    raise Exception("All credentials failed.")

sheet = get_sheet()
row_index = len(sheet.get_all_values()) + 1

# === PRODUCT SCRAPING ===
def scrape_product():
    global row_index
    try:
        ld_json_script = driver.find_element(By.XPATH, "//script[@type='application/ld+json']")
        ld_json = json.loads(ld_json_script.get_attribute("innerHTML"))
        breadcrumbs = ld_json.get("itemListElement", [])
        product_info = breadcrumbs[-1]["item"]
        product_link = product_info.get("@id", driver.current_url)
        product_title = product_info.get("name", "N/A")
    except:
        product_link = driver.current_url
        product_title = "Unknown"

    variations = driver.find_elements(
        By.CSS_SELECTOR, "input.options-selection__option-value-input[data-variant-option-available='true']"
    )

    if variations:
        for var in variations:
            try:
                label = var.get_attribute("aria-label")
                driver.execute_script("arguments[0].click();", var)
                time.sleep(2)
                try:
                    price = driver.find_element(By.CSS_SELECTOR, "div.price__current span.money[data-price]").text.strip()
                except:
                    price = "N/A"
                sheet.update(f"A{row_index}", [[product_title, label, price, product_link]])
                row_index += 1
            except Exception as e:
                print(f"Variation click failed: {e}")
    else:
        try:
            price = driver.find_element(By.CSS_SELECTOR, "div.price__current span.money[data-price]").text.strip()
        except:
            price = "N/A"
        sheet.update(f"A{row_index}", [[product_title, "", price, product_link]])
        row_index += 1

# === MAIN SCRIPT ===
wait_for_connection()
page = 1  # Start from page 1
visited_links = set()

while True:
    current_url = BASE_URL + str(page)
    print(f"\n🔄 Visiting Page {page} → {current_url}")
    driver.get(current_url)
    time.sleep(5)

    # Get all product links
    product_links = driver.find_elements(By.CSS_SELECTOR, 'h2.productitem--title a')
    links = [link.get_attribute("href") for link in product_links if link.get_attribute("href")]

    # Remove duplicates and already visited
    links = list(dict.fromkeys(links))  # Deduplicate while keeping order
    links = [link for link in links if link not in visited_links]
    print(f"📦 {len(links)} new product links to visit.")

    if not links:
        print("✅ No new products found on this page. Scraping complete.")
        break

    for link in links:
        wait_for_connection()
        try:
            print(f"➡️ Visiting product: {link}")
            visited_links.add(link)
            driver.get(link)
            time.sleep(3)
            scrape_product()
        except Exception as e:
            print(f"❌ Failed to process product: {e}")
            continue

    page += 1

driver.quit()
