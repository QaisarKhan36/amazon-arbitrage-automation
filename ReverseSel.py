# Input in sheet1 required {title,web_link, cost, web_variation,web_pack} this are required while infront of that you can include
# {extra_col1,extra_col2}

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import unquote
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import re
import random
from bs4 import BeautifulSoup
from Reg import extract_price_from_description, extract_pack_number, extract_variation

# Google Sheets authentication
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials1.json", scope)
    return gspread.authorize(creds)

# Read data from sheet1
def get_sheet1_data(sheet_id, sheet_name):
    client = get_gspread_client()
    sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
    return sheet.get_all_values()

# Append extracted data to sheet2
def append_to_google_sheet(sheet_id, sheet_name, data_batch):
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
        sheet.append_rows(data_batch, value_input_option="USER_ENTERED")
        print(f"Uploaded {len(data_batch)} rows to Google Sheets.")
    except Exception as e:
        print(f"Error appending data to Google Sheets: {e}")

# Extract ASIN from Amazon link
def AsinFromLink(url):
    match = re.search(r'/dp/([A-Z0-9]{10})(?:[/?]|$)', url)
    return match.group(1) if match else None

def wait_for_bot_check(driver):
    while True:
        if "Our systems have detected unusual traffic" in driver.page_source or "robot check" in driver.page_source:
            print("Bot check detected! Please solve it manually in the browser.")
            input("Press Enter to continue once you've solved the bot check...")
        else:
            break

def random_delay():
    delay = random.uniform(0.1, 2)  # Random delay between 1 and 100 seconds
    print(f"Sleeping for {delay:.2f} seconds...")
    time.sleep(delay)

# Clean price format
def clean_price(price_text):
    try:
        price = float(price_text.replace('$', '').replace('US', '').replace(',', '').strip())
        return price
    except ValueError:
        return None

# Extract product details from Google Search results
def extract_product_details(res):
    with_price = []
    results = res.find_all('div', class_='tF2Cxc')

    for result in results:
        link_tag = result.find('a', href=True)
        if link_tag:
            raw_url = link_tag['href']
            link = unquote(raw_url.split('/url?q=')[1].split('&')[0]) if '/url?q=' in raw_url else raw_url

            if 'amazon.com' in link and '/dp/' in link:
                asin = AsinFromLink(link)
                if asin:
                    title_tag = result.select_one('h3')
                    title = title_tag.get_text(strip=True) if title_tag else None

                    description_tag = result.select_one('.VwiC3b')
                    description = description_tag.get_text(strip=True) if description_tag else None

                    price = None
                    price_tag = result.find_all('span')
                    for tag in price_tag:
                        if '$' in tag.text:
                            price = clean_price(tag.text)
                            if price is not None:
                                break

                    if price is None and description:
                        price = extract_price_from_description(description)

                    combined_info = f"{title} {description}" if title and description else ""
                    web_pack = extract_pack_number(combined_info) or 1
                    web_variation = extract_variation(combined_info)
                    if isinstance(web_variation, list):
                        web_variation = ", ".join(web_variation)

                    result_data = (
                        title, asin, link, f"${price:.2f}" if price is not None and price > 0 else "$0.00",
                        description, web_pack, web_variation or ""
                    )
                    with_price.append(result_data)

    return with_price

# Perform Google search using Selenium
def google_search(driver, query):
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    driver.get(search_url)
    wait_for_bot_check(driver)
    random_delay()
    return driver.page_source

# Retry mechanism for connection issues
def retry_google_search(driver, query, retries=5, delay_minutes=3):
    attempt = 0
    while attempt < retries:
        try:
            print(f"Attempt {attempt + 1} for query: {query}")
            return google_search(driver, query)
        except Exception as e:
            attempt += 1
            print(f"❌ Connection error: {e}")
            if attempt < retries:
                wait_time = delay_minutes * 60
                print(f"Retrying in {delay_minutes} minutes...")
                time.sleep(wait_time)
            else:
                print("⚠️ All retries failed for query.")
                return None

# Process data from sheet1 and append to sheet2
def process_and_append():
    spreadsheet_id = "YOUR_SOURCING_SHEET_ID"
    sheet1_name = "sheet1"
    sheet2_name = "sheet2"

    sheet1_data = get_sheet1_data(spreadsheet_id, sheet1_name)
    batch = []

    # Initialize Selenium WebDriver only once
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        for row in sheet1_data[1:]:  # Skip headers
            try:
                title = row[0]
                web_link = row[1]
                cost = row[2]
                web_variation = row[3]
                web_pack = row[4]
                extra_col1 = row[5] if len(row) > 5 else ""
                extra_col2 = row[6] if len(row) > 6 else ""

                # ✅ ONLY use title for search, plus "amazon.com"
                search_query = f"{title} amazon.com"

                random_delay()
                search_html = retry_google_search(driver, search_query)

                if search_html:
                    soup = BeautifulSoup(search_html, "html.parser")
                    extracted_data = extract_product_details(soup)

                    if extracted_data:
                        for data in extracted_data:
                            amazon_title, asin, amazon_link, amazon_price, amazon_desc, amazon_pack, amazon_variation = data

                            batch.append([
                                title, web_link, cost, web_variation, web_pack,  # Web details from sheet1
                                amazon_title, asin, amazon_link, amazon_price, amazon_desc, amazon_pack, amazon_variation,  # Extracted Amazon details
                                extra_col1, extra_col2  # Additional columns
                            ])

                            if len(batch) >= 10:
                                append_to_google_sheet(spreadsheet_id, sheet2_name, batch)
                                batch.clear()


            except Exception as e:
                print(f"⚠️ Error processing row {row}: {e}")

        if batch:
            append_to_google_sheet(spreadsheet_id, sheet2_name, batch)

    finally:
        driver.quit()

# Run the script
process_and_append()
