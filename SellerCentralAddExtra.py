# sequence required in sheet1 
# "title	sales_rank	asin	web_link	amazon_url	buy_box	adjusted_price	fba_fees	referral_fee_pct	referral_fee	web_cost	cost_per_unit	profit	roi	fba_sellers	fbm_sellers	top_seller_90_days	lowest_buy_box	buy_box_drop_pct	winner_count_90_days	web_title	web_description	variation	web_variation	pack	web_pack"

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
# Function to extract the limitation text from the page (with wait)
def extract_limitation_text(driver, timeout=12):
    try:
        # Wait until at least one restriction message is visible
        WebDriverWait(driver, timeout).until(
            EC.presence_of_all_elements_located((By.XPATH, "//kat-box[@data-testid='restriction-messages']"))
        )

        # Now collect texts
        restriction_boxes = driver.find_elements(By.XPATH, "//kat-box[@data-testid='restriction-messages']")
        limitation_text = [box.text.strip() for box in restriction_boxes if box.text.strip()]

        if limitation_text:
            print(f"✅ Limitation text loaded: {limitation_text}")
            return ", ".join(limitation_text)
        else:
            print("⚠️ No limitation text found after waiting.")
            return "No limitations found"

    except Exception as e:
        print(f"⚠️ Error or timeout waiting for limitation text: {e}")
        return "Error extracting limitations"


# New helper: robust JS click to select the first dropdown option (searches document + shadow roots)
def click_dropdown_and_choose_first(driver, timeout_seconds=5, poll_interval=0.5):
    """
    After dropdown is clicked/opened, run JS that:
      - tries to find an option whose text contains "New" (case-insensitive) and clicks it
      - or as a fallback clicks the first visible option-like element
      - searches both regular DOM and shadow DOMs
    Returns True if clicked, False otherwise.
    """
    js = r"""
    return (function(){
      function isVisible(el){
        if(!el || typeof el.getBoundingClientRect !== 'function') return false;
        var r = el.getBoundingClientRect();
        // require small minimum size to avoid invisible placeholders
        return (r.width > 1 && r.height > 1) && window.getComputedStyle(el).visibility !== 'hidden' && window.getComputedStyle(el).display !== 'none';
      }
      var textPattern = /\bNew\b/i;
      var selectors = ['kat-option', '[role="option"]', 'li', 'div'];

      // Phase A: try to find visible elements that contain the text "New"
      for (var s = 0; s < selectors.length; s++){
        try {
          var nodes = Array.from(document.querySelectorAll(selectors[s]));
          for (var i = 0; i < nodes.length; i++){
            var n = nodes[i];
            try {
              if (!isVisible(n)) continue;
              var txt = (n.innerText || n.textContent || '').trim();
              if (textPattern.test(txt)){
                ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(ev){ n.dispatchEvent(new MouseEvent(ev, {view: window, bubbles: true, cancelable: true})); });
                return true;
              }
            } catch(e){}
          }
        } catch(e){}
      }

      // Phase B: search inside shadow roots for "New"
      function searchShadowForText(root){
        try {
          var all = root.querySelectorAll('*');
          for (var j=0;j<all.length;j++){
            var el = all[j];
            if (el.shadowRoot){
              for (var s=0; s<selectors.length; s++){
                try {
                  var nodes = Array.from(el.shadowRoot.querySelectorAll(selectors[s]));
                  for (var i=0;i<nodes.length;i++){
                    var n = nodes[i];
                    try {
                      if (!isVisible(n)) continue;
                      var txt = (n.innerText || n.textContent || '').trim();
                      if (textPattern.test(txt)){
                        ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(ev){ n.dispatchEvent(new MouseEvent(ev, {view: window, bubbles: true, cancelable: true})); });
                        return true;
                      }
                    } catch(e){}
                  }
                } catch(e){}
              }
              // recursive
              try {
                if (searchShadowForText(el.shadowRoot)) return true;
              } catch(e){}
            }
          }
        } catch(e){}
        return false;
      }
      if (searchShadowForText(document)) return true;

      // Phase C: fallback - click first visible option-like element in document
      for (var s = 0; s < selectors.length; s++){
        try {
          var nodes = Array.from(document.querySelectorAll(selectors[s]));
          for (var i=0;i<nodes.length;i++){
            var n = nodes[i];
            try {
              if (!isVisible(n)) continue;
              ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(ev){ n.dispatchEvent(new MouseEvent(ev, {view: window, bubbles: true, cancelable: true})); });
              return true;
            } catch(e){}
          }
        } catch(e){}
      }

      // Phase D: fallback - click first inside shadow roots
      function clickFirstInShadows(root){
        try {
          var all = root.querySelectorAll('*');
          for (var j=0;j<all.length;j++){
            var el = all[j];
            if (el.shadowRoot){
              for (var s = 0; s < selectors.length; s++){
                try {
                  var nodes = Array.from(el.shadowRoot.querySelectorAll(selectors[s]));
                  for (var i=0;i<nodes.length;i++){
                    var n = nodes[i];
                    try {
                      if (!isVisible(n)) continue;
                      ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(ev){ n.dispatchEvent(new MouseEvent(ev, {view: window, bubbles: true, cancelable: true})); });
                      return true;
                    } catch(e){}
                  }
                } catch(e){}
              }
              if (clickFirstInShadows(el.shadowRoot)) return true;
            }
          }
        } catch(e){}
        return false;
      }
      if (clickFirstInShadows(document)) return true;

      return false;
    })();
    """

    # Polling loop because the dropdown options may take some time to be rendered into DOM/portal
    end_time = time.time() + timeout_seconds
    attempt = 0
    while time.time() < end_time:
        attempt += 1
        try:
            res = driver.execute_script(js)
            if res:
                print(f"[OK] JS selection succeeded on attempt {attempt}")
                return True
        except Exception as e:
            print(f"[WARN] JS selection attempt {attempt} threw: {e}")
        time.sleep(poll_interval)
    print("[FAIL] JS selection could not find/click an option after retries")
    return False

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

                time.sleep(3)

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

            limitations_text = extract_limitation_text(driver, timeout=15)

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
                print(f"ASIN {asin} requires approval. Appending to sheet3")

                # Try to open the dropdown
                try:
                    dropdown = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//kat-dropdown[@data-testid='conditions-dropdown']"))
                    )
                    driver.execute_script("arguments[0].scrollIntoView(true);", dropdown)
                    time.sleep(0.3)
                    dropdown.click()
                    print("Clicked the 'Select a condition and sell' dropdown.")
                    time.sleep(0.6)  # let the overlay render
                except Exception as e:
                    print(f"Error clicking the dropdown: {e}")

                # Use robust JS-based click to pick the "New" option or the first visible option
                try:
                    success = click_dropdown_and_choose_first(driver, timeout_seconds=6, poll_interval=0.5)
                    if success:
                        print("✅ Successfully selected an option using JS click method.")
                    else:
                        print("⚠️ Could not select option with JS method; continuing and saving HTML for inspection.")
                except Exception as e:
                    print(f"Error running JS selection: {e}")

                # After selecting "New" OR waiting 5 seconds, output the page HTML
                try:
                    time.sleep(5)  # give page some time to update after condition selection
                    html_source = driver.page_source
                    with open("OutputSel.html", "w", encoding="utf-8") as f:
                        f.write(html_source)
                    print("✅ Saved OutputSel.html after selecting 'New' (or waiting 5s).")
                except Exception as e:
                    print(f"⚠️ Could not save OutputSel.html: {e}")

                # After selecting "New" condition, wait for the Apply to sell button and click it
                try:
                    # Try Apply to sell first
                    apply_button = WebDriverWait(driver, 12).until(
                        EC.element_to_be_clickable((By.XPATH, "//kat-button[@data-testid='apply-to-sell']"))
                    )
                    driver.execute_script("arguments[0].scrollIntoView(true);", apply_button)
                    time.sleep(0.5)  # small delay to ensure stable click
                    apply_button.click()
                    print("✅ 'Apply to sell' button clicked successfully.")

                except Exception as e:
                    print(f"⚠️ 'Apply to sell' not found or not clickable: {e}")
                    print("👉 Trying 'Sell this product' instead...")

                    try:
                        sell_button = WebDriverWait(driver, 12).until(
                            EC.element_to_be_clickable((By.XPATH, "//kat-button[@data-testid='sell-this-product']"))
                        )
                        driver.execute_script("arguments[0].scrollIntoView(true);", sell_button)
                        time.sleep(0.5)  # small delay to ensure stable click
                        sell_button.click()
                        print("✅ 'Sell this product' button clicked successfully.")
                    except Exception as e2:
                        print(f"❌ Neither 'Apply to sell' nor 'Sell this product' could be clicked. Skipping this ASIN. Error: {e2}")
                        continue



                # Dump HTML after interacting with dropdown (for debugging / inspection)
                # --- inside the "elif requires_approval:" block ---

                try:
                    # Wait for new tab
                    WebDriverWait(driver, 15).until(lambda d: len(d.window_handles) > 1)
                    driver.switch_to.window(driver.window_handles[-1])  # switch to approval tab
                    print("🔀 Switched to approval tab.")

                    time.sleep(3)

                    # --- click Request approval button ---
                    try:
                        request_button = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, "//input[@class='a-button-input' and @type='submit']"))
                        )
                        driver.execute_script("arguments[0].scrollIntoView(true);", request_button)
                        time.sleep(0.5)
                        driver.execute_script("arguments[0].click();", request_button)
                        print("✅ 'Request approval' button clicked successfully.")
                    except Exception as e:
                        print(f"⚠️ Could not click 'Request approval' button: {e}")

                    # wait for page load after request approval
                    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    time.sleep(3)

                    # get HTML text
                    html_source = driver.page_source
                    
                    print(f"✅ Saved post-approval page HTML for ASIN {asin}.")

                    # --- check for "does not qualify" ---
                    if "does not qualify" in html_source or "Your account does not qualify" in html_source:
                        print(f"❌ ASIN {asin} does not qualify → sheet4")
                        sheetNumber = 4
                    else:
                        print(f"✅ ASIN {asin} qualifies for approval → sheet3")
                        sheetNumber = 3

                    # close all extra tabs → return to first
                    while len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                    print("🔙 Returned to first tab.")

                except Exception as e:
                    print(f"⚠️ Error in approval flow for ASIN {asin}: {e}")
                    sheetNumber = 3  # default to sheet3 if error


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

                except Exception as e:
                    print(f"Error clicking the back button: {e}")

            except Exception as e:
                print(f"Error appending data to sheet{sheetNumber} for ASIN {asin}: {e}")  

            loop_count += 1

        except Exception as e:
            print(f"Error processing ASIN {asin}: {e}")

finally:
    driver.quit()
