from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium.webdriver.common.action_chains import ActionChains
import time
from Reg import extract_pack_number,extract_variation
from GoogleAmz import extract_product_details
from Reg import AsinFromLink

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials1.json", scope)
client = gspread.authorize(creds)

# Open the Google Sheet
spreadsheet = client.open_by_url("https://docs.google.com/spreadsheets/d/YOUR_SOURCING_SHEET_ID/edit?gid=2131888024")
sheet1 = spreadsheet.get_worksheet(0)  # Sheet with URLs in column A
sheet2 = spreadsheet.get_worksheet(1)  # Destination sheet for extracted data

# Retrieve all links from column 0 starting from row 1
links = sheet1.col_values(1)[1:]  # Adjust to 1 for 0-indexed and skipping the header

# Set up Selenium
driver = webdriver.Chrome()

# Define function to extract data from a single page and append to Google Sheet
def extract_and_append_to_sheet(soup, sheet):
    products = soup.select('li.product')
    for product in products:
        title = product.select_one('.card-title a').get_text(strip=True)
        product_url = product.select_one('.card-title a')['href']
        pack = extract_pack_number(title) or 1
        variations = ", ".join(extract_variation(f"{title} {product_url}") or [""])
        sale_price = product.select_one('.price--withoutTax').get_text(strip=True) if product.select_one('.price--withoutTax') else "N/A"
        # regular_price = product.select_one('.price--non-sale small')
        # regular_price = regular_price.get_text(strip=True) if regular_price else "N/A"

        with_price = extract_product_details(title,variations,sale_price)

        for Amztitle, Amzlink, Amzprice, Amzdescription, web_pack, web_variation in with_price:
            Asin = AsinFromLink(Amzlink)

            row = [
                Amztitle,Asin,product_url,Amzlink,sale_price,Amzprice,title,Amzdescription,web_variation,variations,web_pack,pack
            ]
            sheet2.append_row(row)

# Define function to visit all pages and extract data
def visit_all_pages_and_extract(url):
    driver.get(url)
    
    while True:
        time.sleep(3)  # Adjust delay for loading
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        extract_and_append_to_sheet(soup, sheet2)  # Save data to sheet2
        
        # Check if there's a "Next" button and click it to continue
        try:
            # Locate the pagination link
            next_page = driver.find_element(By.XPATH, "//a[@aria-label='Next']")
            
            # Use JavaScript to click
            driver.execute_script("arguments[0].click();", next_page)

        except Exception as e:
            print("Error:", e)


# Main loop: Visit each link in the list and retrieve data
for url in links:
    print(f"Visiting: {url}")
    visit_all_pages_and_extract(url)

# Close Selenium driver
driver.quit()
