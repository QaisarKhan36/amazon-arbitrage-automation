import time
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from Reg import extract_pack_number, extract_variation

# Google Sheets setup
SPREADSHEET_ID = "YOUR_SOURCING_SHEET_ID"
SHEET_NAME = "sheet1"

# Authenticate Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials1.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# Selenium setup
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("start-maximized")
chrome_options.add_argument("disable-infobars")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

service = Service("/usr/local/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=chrome_options)
wait = WebDriverWait(driver, 10)

# Open the login page
driver.get("https://regowholesale.com/collections/all?page=1")
print("🚀 Please log in manually. Press Enter in the terminal when done...")
input()

# Save the page source
html_source = driver.page_source
with open("OutputSoup.html", "w", encoding="utf-8") as file:
    file.write(html_source)
print("✅ Saved HTML to OutputSoup.html")

def scrape_page():
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-item")))

        try:
            navigation_section = driver.find_element(By.CSS_SELECTOR, "div.pagination")
            navigation_y = navigation_section.location["y"]
        except:
            print("⚠️ Navigation section not found!")
            navigation_y = None

        product_count = len(driver.find_elements(By.CSS_SELECTOR, "div.product-item"))
        data_to_append = []

        for i in range(product_count):
            try:
                # Re-fetch the product to avoid stale reference
                product = driver.find_elements(By.CSS_SELECTOR, "div.product-item")[i]

                if navigation_y and product.location["y"] > navigation_y:
                    break

                # Skip sold-out products
                if product.find_elements(By.XPATH, ".//button[contains(text(), 'Sold out')]"):
                    continue

                title_elem = product.find_elements(By.CSS_SELECTOR, "a.product-item__title")
                title = title_elem[0].text.strip() if title_elem else "N/A"
                link = title_elem[0].get_attribute("href") if title_elem else "N/A"

                price = "N/A"
                price_clean = "0.00"
                try:
                    # Try to get sale price first
                    sale_price_elem = product.find_elements(By.CSS_SELECTOR, "span.price.price--highlight .hidePrice")
                    if sale_price_elem:
                        price = sale_price_elem[0].text.strip()
                    else:
                        # Fall back to regular price
                        regular_price_elem = product.find_elements(By.CSS_SELECTOR, "span.price .hidePrice")
                        if regular_price_elem:
                            price = regular_price_elem[0].text.strip()
                        else:
                            alt_price_elem = product.find_elements(By.CSS_SELECTOR, "span.price--compare .hidePrice")
                            if alt_price_elem:
                                price = alt_price_elem[0].text.strip()

                    price_clean = price.replace("$", "").replace(",", "").strip()
                    price_float = float(price_clean)
                except:
                    print(f"⚠️ Price missing or invalid for {title}")
                    price_float = 0.0

                # Pack and variation
                pack = extract_pack_number(f"{title} {link}")
                variation = extract_variation(f"{title} {link}")
                variation_str = ", ".join(variation) if isinstance(variation, list) else variation or ""
                pack_str = ", ".join(pack) if isinstance(pack, list) else pack or ""

                # Adjusted cost
                adjusted_cost = "N/A"
                try:
                    pack_text = " ".join(pack) if isinstance(pack, list) else str(pack)
                    match = re.search(r'\d+', pack_text)
                    pack_value = int(match.group()) if match else 1

                    if pack_value == 0:
                        raise ValueError("Pack value is zero")

                    adjusted_cost = round(price_float / pack_value, 2)
                except Exception as e:
                    print(f"⚠️ Error calculating adjusted cost for {title}: {e}")

                data_to_append.append([
                    title, link, adjusted_cost, variation_str, pack_str, price_clean
                ])

            except Exception as e:
                print(f"❌ Error extracting product at index {i}: {e}")
                continue

        if data_to_append:
            sheet.append_rows(data_to_append, value_input_option="RAW")
            print(f"✅ Appended {len(data_to_append)} products to Google Sheet.")
    except Exception as e:
        print(f"❌ Error during page scrape: {e}")

# Start scraping
while True:
    scrape_page()
    try:
        next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.pagination__next")))
        next_button.send_keys(Keys.RETURN)
        time.sleep(3)
    except:
        print("🚀 No more pages found.")
        break

driver.quit()
