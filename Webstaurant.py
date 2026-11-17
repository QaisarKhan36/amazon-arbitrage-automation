from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import time
import re
import os

# ---------------- CONFIG ----------------
SPREADSHEET_ID = "YOUR_SOURCING_SHEET_ID"
SHEET_LINKS = "sheet1"   # where links are stored (column A)
SHEET_PRODUCTS = "sheet2"  # where extracted data will go
CREDENTIALS_FILE = "credentials1.json"
OUTPUT_FILE = "OutputSoup.html"

# ---------------- GOOGLE SHEETS SETUP ----------------
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
client = gspread.authorize(creds)
sheet_links = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_LINKS)
sheet_products = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_PRODUCTS)

# Load all links from Sheet1 column A (ignore empty rows and header)
links = [row[0] for row in sheet_links.get_all_values()[1:] if row and row[0].strip()]
print(f"🔗 Found {len(links)} links to process from sheet1.")

# ---------------- WEBDRIVER SETUP ----------------
def setup_webdriver():
    """Ensure ChromeDriver is available and start browser."""
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    except WebDriverException as e:
        print("⚠️ WebDriver not found. Installing ChromeDriver...")
        os.system("pip install webdriver-manager")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

chrome_options = Options()
chrome_options.add_argument("--start-maximized")

# ---------------- PRODUCT EXTRACTION FUNCTION ----------------
def extract_products_from_page(html):
    soup = BeautifulSoup(html, "html.parser")
    products = []

    for product in soup.select('div[data-testid="productBoxContainer"]'):
        title_tag = product.select_one('[data-testid="itemDescription"]')
        link_tag = product.select_one('a[data-testid="itemLink"]')
        price_tag = product.select_one('[data-testid="price"]')
        each_tag = product.select_one('[data-testid="divideByPricing"]')

        title = title_tag.get_text(strip=True) if title_tag else "N/A"
        link = f"https://www.webstaurantstore.com{link_tag['href']}" if link_tag and link_tag.has_attr('href') else "N/A"

        case_price = price_tag.get_text(strip=True) if price_tag else ""
        each_price = each_tag.get_text(strip=True) if each_tag else ""

        # Choose cost and clean it
        if "/Each" in each_price:
            cost = re.sub(r"[^\d.]", "", each_price)
            price_type = "Each"
        elif "/Pack" in each_price:
            cost = re.sub(r"[^\d.]", "", each_price)
            price_type = "Pack"
        elif "/Case" in case_price:
            cost = re.sub(r"[^\d.]", "", case_price)
            price_type = "Case"
        else:
            cost = re.sub(r"[^\d.]", "", case_price) if case_price else "N/A"
            price_type = "N/A"

        products.append({
            "title": title,
            "link": link,
            "cost": cost,
            "type": price_type
        })
    return products

# ---------------- SCRAPE SINGLE LINK ----------------
def scrape_link(driver, base_url, sheet_products):
    page = 1
    all_products = []
    seen_titles = set()
    seen_links = set()

    while True:
        current_url = base_url if page == 1 else f"{base_url}?page={page}"
        print(f"\n🟢 Extracting page {page}: {current_url}")
        driver.get(current_url)
        time.sleep(4)

        html = driver.page_source
        products = extract_products_from_page(html)

        if not products:
            print("🚫 No products found on this page. Skipping link.")
            break

        new_rows = []
        repeated_found = False
        for p in products:
            if p["title"] in seen_titles or p["link"] in seen_links:
                repeated_found = True
                break
            seen_titles.add(p["title"])
            seen_links.add(p["link"])
            new_rows.append([p["title"], p["link"], p["cost"], p["type"], base_url])

        if not new_rows:
            print("⚠️ No new products to add. Skipping link.")
            break

        try:
            sheet_products.append_rows(new_rows)
            print(f"✅ Added {len(new_rows)} products from page {page}.")
        except Exception as e:
            print(f"❌ Error writing to Google Sheet: {e}")

        all_products.extend(new_rows)

        # Save current HTML for debugging
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)

        if repeated_found:
            print("⚠️ Repeated data detected — likely last page.")
            break

        page += 1

    return len(all_products)


# ---------------- MAIN ----------------
def main():
    driver = setup_webdriver()
    driver.get("https://www.webstaurantstore.com/")
    input("⚠️ Complete CAPTCHA if shown, then press ENTER to start scraping...")

    total_added = 0
    for link in links:
        print(f"\n🔗 Starting scrape for: {link}")
        try:
            added_count = scrape_link(driver, link, sheet_products)
            total_added += added_count
            print(f"✅ Finished {link} → Added {added_count} products.\n")
        except Exception as e:
            print(f"❌ Error scraping {link}: {e}")
            continue

    driver.quit()
    print(f"\n🏁 All done! Total {total_added} products added to Sheet2.")

if __name__ == "__main__":
    main()
