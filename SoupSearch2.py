import gspread
import time
import requests
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from urllib.parse import unquote

# Global variable to keep track of credential file number
credentials_number = 1

spreadsheet_key = "YOUR_SOURCING_SHEET_ID"

def get_gspread_client():
    """Create a gspread client using the specified credentials file."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_filename = f'credentials{credentials_number}.json'
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_filename, scope)
    return gspread.authorize(creds)

# Function to switch credentials when quota is reached
def switch_credentials_if_needed(client):
    try:
        # Attempt to get data from the Google Sheet
        return client.open_by_key(spreadsheet_key).sheet1
    except gspread.exceptions.APIError as e:
        print(f"API Error: {e}")
        if 'Quota' in str(e):
            print("Quota reached, switching credentials...")
            global credentials_number
            credentials_number += 1  # Increment to switch to the next credentials
            client = get_gspread_client()  # Recreate the client with the next credentials
            return switch_credentials_if_needed(client)  # Try fetching data again
        else:
            raise  # Re-raise if it's not a quota error

# Google Sheets API Setup
client = get_gspread_client()

# Open Google Spreadsheet
sheet1 = switch_credentials_if_needed(client)
sheet2 = client.open_by_key(spreadsheet_key).worksheet("sheet2")  # Access sheet2
sheet3 = client.open_by_key(spreadsheet_key).worksheet("sheet3")  # Access sheet3

# Get all data from Google Sheets (assuming it starts from the first row)
print("Fetching data from Google Sheets...")
data = sheet1.get_all_values()

product_data = {
    row[0]: {
        "title": row[0],           # Column A: Product Title
        "sales_rank": row[1],      # Column B: Sales Rank
        "asin": row[2],            # Column C: ASIN
        "amazon_url": row[3],      # Column D: Amazon URL
        "buy_box": float(row[4].replace('$', '').strip()) if row[4] and row[4] not in ['-', 'N/A'] else 0.0,  # Buy Box price
        "fba_fee": float(row[5].replace('$', '').strip()) if row[5] and row[5] not in ['-', 'N/A'] else 0.0,  # FBA Fees
        "referral_fee_pct": float(row[6].replace('%', '').strip()) if row[6] and row[6] not in ['-', 'N/A'] else 0.0,  # Referral Fee %
        "referral_fee": float(row[7].replace('$', '').strip()) if row[7] and row[7] not in ['-', 'N/A'] else 0.0,  # Referral Fee based on current Buy Box price
        "new_fba_count": row[8],  # Column I: Buy Box Eligible Offer Count: New FBA
        "new_fbm_count": row[9],  # Column J: Buy Box Eligible Offer Count: New FBM
        "top_seller_pct": row[10],  # Column K: Buy Box: % Top Seller 90 days
        "lowest_buy_box": float(row[11].replace('$', '').strip()) if row[11] and row[11] not in ['-', 'N/A'] else 0.0,  # Buy Box: Lowest
        "buy_box_drop_pct": float(row[12].replace('%', '').strip()) if row[12] and row[12] not in ['-', 'N/A'] else 0.0,  # Buy Box: 90 days drop %
        "winner_count": row[13]    # Column N: Buy Box: Winner Count 90 days
    } 
    for row in data[1:]  # Skip header row
}

# Selenium WebDriver Setup
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode
service = Service('/usr/local/bin/chromedriver')  # Update path as needed
driver = webdriver.Chrome(service=service, options=chrome_options)

def clean_price(text):
    """Clean price by removing 'US$', '$' prefix, and any trailing words, then round it to two decimal places."""
    price = text.replace('US$', '').replace('$', '').strip()
    price = ''.join(char for char in price if char.isdigit() or char == '.')
    try:
        price = float(price)
    except ValueError:
        price = None
    return price

def extract_price_and_link_with_soup(product_name):
    search_url = f"https://www.google.com/search?q={product_name.replace(' ', '+')}+USA"
    response = requests.get(search_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    results = []
    for g in soup.find_all('div', class_='BNeawe s3v9rd AP7Wnd'):
        text = g.get_text(strip=True)
        if 'US$' in text or '$' in text:
            price = clean_price(text)
            link_tag = g.find_previous('a', href=True)
            if link_tag:
                link = link_tag['href'].split('q=')[1].split('&')[0]
                decoded_link = unquote(link)
                results.append((product_name, decoded_link, price))

    return results

def extract_price_and_link_with_selenium(product_name):
    search_url = f"https://www.google.com/search?q={product_name.replace(' ', '+')}+USA"
    driver.get(search_url)
    time.sleep(2)

    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')

    results = []
    for g in soup.find_all('div', class_='BNeawe s3v9rd AP7Wnd'):
        text = g.get_text(strip=True)
        if 'US$' in text or '$' in text:
            price = clean_price(text)
            link_tag = g.find_previous('a', href=True)
            if link_tag:
                link = link_tag['href'].split('q=')[1].split('&')[0]
                decoded_link = unquote(link)
                results.append((product_name, decoded_link, price))

    return results

def calculate_profit_and_roi(buy_box_price, cost, fba_fee, referral_fee):
    profit = buy_box_price - cost - fba_fee - referral_fee
    roi = (profit / cost) * 100 if cost != 0 else 0
    return profit, roi

# Prepare a list to store results for Google Sheets and CSV
all_results = []
failed_products = []  # List to track details of failed products
successful_products = set()  # Set to track unique ASINs of successful products

# Loop through each product name, searching in batches of 100
batch_size = 100
total_products = len(product_data)
for start_index in range(0, total_products, batch_size):
    end_index = min(start_index + batch_size, total_products)
    batch_data = list(product_data.items())[start_index:end_index]

    for idx, (product_name, info) in enumerate(batch_data, start=1):
        print(f"Processing product {start_index + idx}/{total_products}: {product_name}...")

        # Try extracting price and link data with BeautifulSoup first
        soup_results = extract_price_and_link_with_soup(product_name)

        # If BeautifulSoup extraction fails or finds no prices, then try Selenium
        if not soup_results:
            print(f"No results with BeautifulSoup, trying Selenium for {product_name}...")
            selenium_results = extract_price_and_link_with_selenium(product_name)
            combined_results = selenium_results
        else:
            combined_results = soup_results

        # Filter out rows with 'amazon.com' or 'ebay.com' in the link (Column C)
        combined_results = [
            (product_name, link, price) 
            for product_name, link, price in combined_results 
            if 'amazon.com' not in link and 'ebay.com' not in link and price is not None
        ]

        if combined_results:
            successful_products.add(info["asin"])

            # Sort the results by cost (price) and take the top 3
            combined_results = sorted(combined_results, key=lambda x: x[2])[:3]

            # Select the first result
            selected_result = combined_results[0]
            product_name, link, cost = selected_result

            # Calculate profit and ROI
            profit, roi = calculate_profit_and_roi(info["buy_box"], cost, info["fba_fee"], info["referral_fee"])

            # Store results for Google Sheets and CSV
            all_results.append([
                info["title"], info["sales_rank"], info["asin"], link, info["amazon_url"],
                info["buy_box"], info["fba_fee"], info["referral_fee_pct"], info["referral_fee"],
                cost, profit, roi, info["new_fba_count"], info["new_fbm_count"],
                info["top_seller_pct"], info["lowest_buy_box"], info["buy_box_drop_pct"], info["winner_count"]
            ])
        else:
            failed_products.append(info)  # Keep track of failed products

    # Update the sheet with the successful results
    if all_results:
        # Append the successful results to sheet2
        sheet2.append_rows(all_results)
        all_results.clear()  # Clear results for next batch

# Mark successful products in sheet1
if successful_products:
    for idx, row in enumerate(sheet1.get_all_values()[1:], start=2):  # Start from row 2 to skip header
        if row[2] in successful_products:  # Check the ASIN
            sheet1.format(f'A{idx}:Z{idx}', {'backgroundColor': {'red': 0.678, 'green': 1.0, 'blue': 0.678}})  # Light green for successful
        else:
            sheet1.format(f'A{idx}:Z{idx}', {'backgroundColor': {'red': 1.0, 'green': 1.0, 'blue': 0.678}})  # Light yellow for unsuccessful

# Append unsuccessful products to sheet3 with the same structure
if failed_products:
    sheet3.append_rows([[info["title"], info["sales_rank"], info["asin"], info["amazon_url"],
                          info["buy_box"], info["fba_fee"], info["referral_fee_pct"],
                          info["referral_fee"], info["new_fba_count"],
                          info["new_fbm_count"], info["top_seller_pct"],
                          info["lowest_buy_box"], info["buy_box_drop_pct"],
                          info["winner_count"]] for info in failed_products])

# Clean up the driver session
driver.quit()

print("Finished processing products.")
