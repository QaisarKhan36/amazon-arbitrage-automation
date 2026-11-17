from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException

# === Global credential counter ===
credentials_number = 1
max_credentials = 23
sheet_url = "https://docs.google.com/spreadsheets/d/YOUR_SOURCING_SHEET_ID/edit"
spreadsheet_key = sheet_url.split("/d/")[1].split("/")[0]

# === Setup Google Sheets client ===
def get_gspread_client():
    global credentials_number
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    json_path = f"credentials{credentials_number}.json"
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
    return gspread.authorize(creds)

# === Switch credentials if quota is hit ===
def switch_credentials_if_needed():
    global credentials_number
    if credentials_number < max_credentials:
        credentials_number += 1
        print(f"🔄 Switching to credentials{credentials_number}.json")
        return get_gspread_client().open_by_key(spreadsheet_key).worksheet("sheet1")
    else:
        raise Exception("❌ All credentials exhausted or failed.")

# === Scrape product data from current page ===
def scrape_products(driver):
    products = []
    product_boxes = driver.find_elements(By.CLASS_NAME, "product-box")
    for box in product_boxes:
        try:
            name_elem = box.find_element(By.CLASS_NAME, "product-name")
            price_elem = box.find_element(By.CLASS_NAME, "price")
            link = name_elem.get_attribute("href")
            name = name_elem.text.strip()
            price_text = price_elem.text.strip()
            products.append([name, price_text, link])
        except NoSuchElementException:
            continue
    return products

# === Check if there's a next page and return the link ===
def go_to_next_page(driver, current_page):
    try:
        footer = driver.find_element(By.CLASS_NAME, "products-listing-footer")
        links = footer.find_element(By.CLASS_NAME, "links").find_elements(By.TAG_NAME, "a")
        for link in links:
            if link.text.strip() == str(current_page + 1):
                print(f"➡️ Going to page {current_page + 1}")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
                time.sleep(1)
                try:
                    driver.execute_script("arguments[0].click();", link)
                except (ElementClickInterceptedException, StaleElementReferenceException) as e:
                    print(f"⚠️ JS click failed: {e}. Retrying after delay...")
                    time.sleep(2)
                    driver.execute_script("arguments[0].click();", link)
                time.sleep(2)
                return True
    except NoSuchElementException:
        print("❌ Pagination footer or link not found.")
    return False

# === Main scraping routine ===
def main():
    global credentials_number
    options = Options()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    start_url = "https://pricemaster.com/Consumer-Electronics/Electronics-Accessories"
    driver.get(start_url)

    print("🔐 Please log in manually in the browser window.")
    input("✅ After logging in, press Enter here to continue...")

    client = get_gspread_client()
    sheet = client.open_by_key(spreadsheet_key).worksheet("sheet1")

    existing_data = sheet.get_all_values()
    if not existing_data:
        sheet.append_row(["Product Name", "Price per Unit", "Product Link"])

    page = 1
    buffer = []
    while True:
        print(f"📄 Scraping page {page}...")
        products = scrape_products(driver)
        for row in products:
            buffer.append(row)
            if len(buffer) == 10:
                success = False
                while not success:
                    try:
                        sheet.append_rows(buffer)
                        buffer = []
                        success = True
                    except Exception as e:
                        print(f"⚠️ Error writing 10 rows: {e}")
                        sheet = switch_credentials_if_needed()

        if not go_to_next_page(driver, page):
            break
        page += 1

    # Write remaining rows in buffer
    if buffer:
        success = False
        while not success:
            try:
                sheet.append_rows(buffer)
                success = True
            except Exception as e:
                print(f"⚠️ Error writing final rows: {e}")
                sheet = switch_credentials_if_needed()

    print("✅ Scraping completed and data saved to Google Sheets.")
    driver.quit()

if __name__ == "__main__":
    main()
