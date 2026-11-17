from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from Reg import extract_pack_number, extract_variation
import time
import random
from urllib.parse import urlparse, parse_qs, urlencode

# --- Setup Selenium WebDriver ---
options = Options()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 10)

# --- Google Sheets Setup with Rotating Credentials ---
def authorize_with_incremental_credentials(max_index=24):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    for i in range(1, max_index + 1):
        cred_file = f"credentials{i}.json"
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(cred_file, scope)
            client = gspread.authorize(creds)
            print(f"✅ Authorized with {cred_file}")
            return client
        except Exception as e:
            print(f"❌ Failed with {cred_file}: {e}")
    raise Exception("🚫 All credentials failed!")

client = authorize_with_incremental_credentials()
spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/YOUR_SOURCING_SHEET_ID/edit?gid=278435173")
sheet1 = spreadsheet.worksheet("sheet1")

# --- Helper Functions ---
def random_delay():
    delay = random.uniform(2, 5)
    print(f"Sleeping for {delay:.2f} seconds...")
    time.sleep(delay)

def append_to_sheet(data):
    for item in data:
        sheet1.append_row(item)

# --- Scraper Logic ---
max_pages = 34
current_page = 18

base_url = "https://www.yamibuy.com/en/c/beauty/2?cat_id=2&is_instock=1&sort_by=3&bu_type=category_tree&module_name=category_main&page="

while current_page <= max_pages:
    print(f"\n🌐 On page {current_page}")
    driver.get(f"{base_url}{current_page}")
    random_delay()

    try:
        wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "item-card")))
        product_cards = driver.find_elements(By.CLASS_NAME, "item-card")

        if not product_cards:
            print("No product cards found, moving to next page...")
            current_page += 1
            continue

        for index, card in enumerate(product_cards):
            try:
                link_element = card.find_element(By.TAG_NAME, "a")
                product_link = link_element.get_attribute("href")

                name_element = card.find_element(By.CLASS_NAME, "item-title")
                product_name = name_element.text.strip()

                price_element = card.find_element(By.CLASS_NAME, "price-valid")
                product_price = float(price_element.text.strip().replace("$", ""))

                brand_element = card.find_element(By.CLASS_NAME, "brand-title")
                product_brand = brand_element.text.strip()

                pack_number = extract_pack_number(product_name)
                variation_info = extract_variation(product_name)
                if isinstance(variation_info, list):
                    variation_info = ", ".join(set(variation_info))
                elif variation_info is None:
                    variation_info = ""

                row_data = [
                    product_link,
                    product_name,
                    product_price,
                    product_brand,
                    pack_number,
                    variation_info
                ]

                print(f"✅ Product {index + 1}: {row_data}")
                append_to_sheet([row_data])
                random_delay()

            except Exception as e:
                print(f"❌ Error extracting product {index + 1}: {e}")
                continue

        current_page += 1

    except Exception as e:
        print(f"🚫 Error on page {current_page}: {e}")
        break

driver.quit()
