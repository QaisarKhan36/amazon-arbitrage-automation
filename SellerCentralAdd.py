# sequence required in sheet1 "title	sales_rank	asin	web_link	amazon_url	buy_box	adjusted_price	fba_fees	referral_fee_pct	referral_fee	web_cost	cost_per_unit	profit	roi	fba_sellers	fbm_sellers	top_seller_90_days	lowest_buy_box	buy_box_drop_pct	winner_count_90_days	web_title	web_description	variation	web_variation	pack	web_pack" copy and paste in sheet1


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import time
import socket
from SharedFunc import retry_on_connection_error

# Internet wait checker
def wait_for_internet():
    while True:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            return
        except OSError:
            print("\n[!] Internet disconnected. Waiting to reconnect...")
            time.sleep(5)

# Google Sheets setup
SPREADSHEET_ID = "YOUR_SOURCING_SHEET_ID"
SHEET_NAME = "sheet1"
COLUMN_INDEX = 2

# Function to authenticate with Google Sheets using available credentials
def get_gspread_client(credentials_number):
    credentials_file = f"credentials{credentials_number}.json"
    if not os.path.exists(credentials_file):
        raise FileNotFoundError(f"{credentials_file} not found.")

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    return gspread.authorize(credentials)

# Function to fetch product data from sheet1
def fetch_product_data():
    for i in range(1, 25):
        try:
            wait_for_internet()
            client = get_gspread_client(i)
            sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
            data = sheet.get_all_values()
            return data
        except Exception as e:
            print(f"Failed with credentials{i}.json: {e}")
            if i == 24:
                raise Exception("All credentials exhausted.")
    return []

# Function to extract the limitation text from the page
def extract_limitation_text(driver):
    try:
        restriction_boxes = driver.find_elements(By.XPATH, "//kat-box[@data-testid='restriction-messages']")
        limitation_text = [box.text.strip() for box in restriction_boxes if box.text.strip()]
        return ", ".join(limitation_text) if limitation_text else "No limitations found"
    except Exception as e:
        print(f"Error extracting limitation text: {e}")
        return "Error extracting limitations"

# Selenium setup
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(options=options)

try:
    product_data = retry_on_connection_error(fetch_product_data)

    url = "https://sellercentral.amazon.com/product-search/keywords?ref=xx_catadd_dnav_xx"
    wait_for_internet()
    driver.get(url)

    input("Please log in and complete the OTP verification. Press Enter here to continue...")

    loop_count = 0

    for row in product_data[1:]:
        try:
            wait_for_internet()
            title = row[0]
            sales_rank = row[1]
            asin = row[2]
            web_link = row[3]
            amazon_url = row[4]
            buy_box = row[5]
            adjusted_price = row[6]
            fba_fees = row[7]
            referral_fee_pct = row[8]
            referral_fee = row[9]
            web_cost = row[10]
            cost_per_unit = row[11]
            profit = row[12]
            roi = row[13]
            fba_sellers = row[14]
            fbm_sellers = row[15]
            top_seller_90_days = row[16]
            lowest_buy_box = row[17]
            buy_box_drop_pct = row[18]
            winner_count_90_days = row[19]
            web_title = row[20]
            web_description = row[21]
            variation = row[22]
            web_variation = row[23]
            pack = row[24]
            web_pack = row[25]

            try:
                if loop_count == 0:
                    shadow_root = driver.execute_script(
                        "return document.querySelector('kat-predictive-input').shadowRoot"
                    )
                    input_field = shadow_root.find_element(By.CSS_SELECTOR, "input")
                else:
                    print("Targeting the second input field...")
                    second_predictive_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "div.YnNwpZA52_oVx83LfDu4 kat-predictive-input")
                        )
                    )
                    shadow_root = driver.execute_script("return arguments[0].shadowRoot", second_predictive_input)
                    input_field = shadow_root.find_element(By.CSS_SELECTOR, "input")

                input_field.clear()
                print("Cleared the input field.")
                input_field.send_keys(asin)
                print(f"Entered product title/ASIN in the input box: {asin}")

                try:
                    if loop_count == 0:
                        submit_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable(
                                (By.XPATH, '//kat-button[@data-testid="omnibox-submit-button"]')
                            )
                        )
                        print("Submit button found using the first method.")
                    else:
                        submit_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable(
                                (By.XPATH, '//kat-button[@data-testid="search-results-search-submit-button"]')
                            )
                        )
                        print("Submit button found using the new method.")

                except Exception:
                    if loop_count == 0:
                        print("First method failed, trying the second method.")
                        submit_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable(
                                (By.XPATH, '//kat-button[@label="Submit"]')
                            )
                        )
                        print("Submit button found using the second method.")
                    else:
                        print("Submit button could not be found in the new method.")
                        continue

                wait_for_internet()
                submit_button.click()
                print(f"Clicked submit for product title/ASIN: {asin}")

                time.sleep(5)

                try:
                    first_product = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//div[@data-testid='search-results-rows']/div"))
                    )
                    first_product.click()
                    print(f"Clicked on the first product listing for ASIN: {asin}")

                    time.sleep(2)

                except Exception as e:
                    print(f"Error clicking on the first product listing for ASIN {asin}: {e}")

            except Exception as e:
                print("Cannot find input field or submit button:", e)

            limitations_text = extract_limitation_text(driver)

            not_available_limit = any(
                keyword in limitations_text
                for keyword in ["This product has other listing limitations"]
            )

            requires_approval = any(
                keyword in limitations_text 
                for keyword in ["You need approval to list in this brand", "You need approval to list this product", "You need approval to list"]
            )

            if not_available_limit:
                print(f"ASIN {asin} is not available. Appending to sheet4.")
                sheetNumber = 4
            elif requires_approval:
                print(f"ASIN {asin} requires approval. Appending to sheet3.")
                sheetNumber = 3
            else:
                print(f"ASIN {asin} is available and does not require approval. Appending to sheet2.")
                sheetNumber = 2

            try:
                wait_for_internet()
                client = get_gspread_client(1)  
                sheet = client.open_by_key(SPREADSHEET_ID).worksheet(f"sheet{sheetNumber}")

                def append_to_sheet():
                    wait_for_internet()
                    current_rows = len(sheet.get_all_values())
                    start_row = current_rows + 1
                    sheet.update(
                        values=[[title, sales_rank, asin, web_link, amazon_url, buy_box, adjusted_price, fba_fees, referral_fee_pct, referral_fee,
                                web_cost, cost_per_unit, profit, roi, fba_sellers, fbm_sellers, top_seller_90_days, lowest_buy_box, buy_box_drop_pct,
                                winner_count_90_days, web_title, web_description, variation, web_variation, pack, web_pack, limitations_text]],
                        range_name=f"A{start_row}"
                    )
                    print(f"Data for ASIN {asin} appended to sheet{sheetNumber} starting from column 0.")

                retry_on_connection_error(append_to_sheet)

                try:
                    wait_for_internet()
                    back_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//kat-icon[@name='keyboard_arrow_left']"))
                    )
                    back_button.click()
                    print("Clicked the back button.")

                    time.sleep(3)

                    # with open("OutputSel.html", "w", encoding="utf-8") as file:
                    #     file.write(driver.page_source)
                    # print("Saved the updated source page HTML to OutputSel.html after clicking the back button.")

                except Exception as e:
                    print(f"Error clicking the back button: {e}")

            except Exception as e:
                print(f"Error appending data to sheet{sheetNumber} for ASIN {asin}: {e}")  

            loop_count += 1

        except Exception as e:
            print(f"Error processing ASIN {asin}: {e}")

finally:
    driver.quit()
