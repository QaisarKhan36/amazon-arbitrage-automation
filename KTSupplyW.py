from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from Reg import extract_pack_number, extract_variation

# Google Sheets authentication
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials1.json", scope)
    return gspread.authorize(creds)

def append_to_google_sheet(sheet_id, sheet_name, data_batch):
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
        sheet.append_rows(data_batch, value_input_option="USER_ENTERED")
        print(f"Uploaded {len(data_batch)} rows to Google Sheets.")
    except Exception as e:
        print(f"Error appending data to Google Sheets: {e}")

def extract_and_save_data(url, max_pages=None):
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    spreadsheet_id = "YOUR_SOURCING_SHEET_ID"
    sheet_name = "sheet1"
    batch = []
    current_page = 1
    
    try:
        driver.get(url)
        
        # Save the source HTML to OutputSel.html
        with open("OutputSel.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Saved page source to OutputSel.html")

        while True:
            time.sleep(5)  # Wait for the page to load
            products = driver.find_elements(By.CSS_SELECTOR, "div.product-slideup-content")
            
            for product in products:
                try:
                    title = product.find_element(By.CSS_SELECTOR, "h3.product-name a").text
                    price = product.find_element(By.CSS_SELECTOR, "ins.new-price").text
                    link = product.find_element(By.CSS_SELECTOR, "h3.product-name a").get_attribute("href")
                    
                    price = float(price.replace("$", "").replace(",", "").strip())
                    pack = extract_pack_number(title)
                    variation = extract_variation(f"{title} {link}")

                    # Ensure pack and variation are strings
                    variation_str = ", ".join(map(str, variation)) if isinstance(variation, (list, tuple)) else str(variation)
                    pack_str = ", ".join(map(str, pack)) if isinstance(pack, (list, tuple)) else str(pack)

                    row = [title, link, price, variation_str, pack_str]
                    batch.append(row)
                    
                    if len(batch) >= 10:
                        append_to_google_sheet(spreadsheet_id, sheet_name, batch)
                        batch.clear()
                except Exception as e:
                    print(f"Error extracting product details: {e}")
            
            # Pagination handling
            try:
                pagination_numbers = driver.find_elements(By.CSS_SELECTOR, "li.page-item a.page-link")
                next_button = driver.find_elements(By.CSS_SELECTOR, "li.next a")
                
                if pagination_numbers:
                    last_page_number = int(pagination_numbers[-1].text)
                    
                    if current_page < last_page_number:
                        next_page_selector = f"//li[contains(@class, 'page-item') and ./a[text()='{current_page + 1}']]/a"
                        next_page_element = driver.find_element(By.XPATH, next_page_selector)
                        next_page_element.click()
                        current_page += 1
                        time.sleep(3)
                        continue
                
                if next_button:
                    next_button[0].click()
                    time.sleep(3)
                    current_page += 1
                    continue
                else:
                    break
            except Exception:
                break
        
        if batch:
            append_to_google_sheet(spreadsheet_id, sheet_name, batch)
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

# Example usage
url = "https://ktsupplywholesale.com/collections/553/health-beauty/hair/treatment"
extract_and_save_data(url)