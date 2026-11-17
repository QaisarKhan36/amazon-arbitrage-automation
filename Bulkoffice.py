from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import os

# --- CAPTCHA/Bot Check Detection ---
def wait_for_bot_check(driver):
    while True:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        verifying_text = soup.find("p", class_="h2 spacer-bottom")
        challenge_notice = soup.find("div", id="CefdN0")

        if verifying_text and "verifying you are human" in verifying_text.text.lower():
            print("🛡️ Detected Cloudflare Verification: 'Verifying you are human'")
        elif challenge_notice and "review the security of your connection" in challenge_notice.text.lower():
            print("🛡️ Detected Cloudflare Review: 'Review the security of your connection'")
        elif any(term in driver.page_source.lower() for term in [
            "unusual traffic", "robot check", "captcha",
            "are you a human", "verifying you are human"
        ]):
            print("🛡️ General CAPTCHA or bot challenge detected")
        else:
            break

        input("🔐 Solve the CAPTCHA in browser, then press Enter to continue...")
        time.sleep(2)

# --- Google Sheet Authentication ---
def authenticate_with_google():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    for i in range(1, 24):
        cred_file = f"credentials{i}.json"
        if os.path.exists(cred_file):
            try:
                creds = ServiceAccountCredentials.from_json_keyfile_name(cred_file, scope)
                print(f"✅ Authenticated with {cred_file}")
                return gspread.authorize(creds)
            except Exception as e:
                print(f"❌ Failed {cred_file}: {e}")
    raise Exception("All credentials failed!")

# --- Extract Products from Soup ---
def extract_products(soup):
    product_tags = soup.find_all("lb:product")
    extracted_data = []

    for tag in product_tags:
        name_tag = tag.find("div", class_="recordname")
        price_tag = tag.find("div", class_="recordprice")
        link_tag = tag.find("a", class_="product_link")

        name = name_tag.text.strip() if name_tag else "N/A"
        price_text = price_tag.text.strip().replace("$", "") if price_tag else "0"
        link = f"https://www.bulkofficesupply.com{link_tag['href'].strip()}" if link_tag and "href" in link_tag.attrs else "N/A"

        try:
            price = float(price_text)
        except ValueError:
            price = 0.0

        extracted_data.append([name, price, link])

    return extracted_data

# --- Setup Selenium ---
chrome_options = Options()
# chrome_options.add_argument("--headless")  # Optional headless mode
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
driver = webdriver.Chrome(service=Service("/usr/local/bin/chromedriver"), options=chrome_options)
wait = WebDriverWait(driver, 10)

try:
    base_url = "https://www.bulkofficesupply.com/Categories/Wholesale-by-Manufacturer-BULK/Bic-BULK/Ballpoint-Pens.aspx"
    driver.get(base_url)
    wait_for_bot_check(driver)

    # Google Sheet Setup
    client = authenticate_with_google()
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/YOUR_SOURCING_SHEET_ID/edit#gid=1518946923")
    worksheet = sheet.worksheet("sheet1")
    worksheet.clear()
    worksheet.append_row(["Name", "Price", "Product Link"])

    while True:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "lb\\:product")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        data = extract_products(soup)

        print(f"🛒 Extracted {len(data)} products.")
        for row in data:
            worksheet.append_row(row)

        wait_for_bot_check(driver)

        try:
            pager = driver.find_element(By.ID, "ctl00_MainContentHolder_ProductGridView1_gridcontrolwrapBottom")
            next_link = pager.find_element(By.XPATH, ".//li[contains(@class, 'pgrNext')]/a")
            next_href = next_link.get_attribute("href")

            if next_href:
                print(f"➡️ Going to next page: {next_href}")
                driver.get(next_href)
                wait_for_bot_check(driver)
                time.sleep(1)
            else:
                print("❌ No valid 'Next' href found.")
                break

        except NoSuchElementException:
            print("✅ No 'Next' button. Scraping complete.")
            break
        except TimeoutException:
            print("⏱️ Page load timed out. Exiting.")
            break

    print("🎉 Scraping completed and data uploaded to Google Sheets!")

finally:
    driver.quit()
