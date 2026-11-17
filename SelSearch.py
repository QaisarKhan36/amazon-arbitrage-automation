# Input in Sheet1 required {Product Name, Variation, BuyBox Price, Attributes} → used as {product_name, variation, BuyBox, Attributes}

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from Reg import extract_pack_number, extract_variation,extract_attribute_values
from ExtractSel import extract_price_and_link_with_selenium  # Import from ExtractSel.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Configuration for credentials and limits
credentials_number = 1
max_credentials = 24
spreadsheet_key = "YOUR_SOURCING_SHEET_ID"
batch_size = 2
counter = 0  # Initialize counter

# Initialize Google Sheets API client
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_filename = f'credentials{credentials_number}.json'
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_filename, scope)
    return gspread.authorize(creds)

def switch_credentials_if_needed(client):
    global credentials_number
    try:
        return client.open_by_key(spreadsheet_key).sheet1
    except gspread.exceptions.APIError as e:
        if 'Quota' in str(e) and credentials_number < max_credentials:
            credentials_number += 1
            client = get_gspread_client()
            return switch_credentials_if_needed(client)
        else:
            raise Exception("Reached max credential switches or encountered a non-quota error.")

# Initialize the Selenium driver
def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service('/usr/local/bin/chromedriver')  # Update with your chromedriver path
    return webdriver.Chrome(service=service, options=chrome_options)


# Function to compare variations
def compare_variations_and_Attributes(existing_variations, new_variations, Attributes, Combine_Data):
    # Handle None for Attributes
    if Attributes is None:
        Attributes = []

    # Handle None for Combine_Data to avoid errors
    if Combine_Data is None:
        Combine_Data = ""

    # Check for attribute matches
    attribute_match = any(Attribute in Combine_Data for Attribute in Attributes)

    # Check for variation matches
    variation_match = any(
        new_var.strip() in [var.strip() for var in existing_variations.split(",")]
        for new_var in new_variations.split(",")
    )

    # Return result based on matches
    if attribute_match and variation_match:
        return "Yes"
    return "No"

# Google Sheets API setup
client = get_gspread_client()
sheet1 = switch_credentials_if_needed(client)
sheet2 = client.open_by_key(spreadsheet_key).worksheet("sheet2")
sheet4 = client.open_by_key(spreadsheet_key).worksheet("sheet4")

# Fetch data from sheet1
data = sheet1.get_all_values()

# Process data into a dictionary
product_data = {
    row[0]: {
        "title": row[0],
        "sales_rank": row[1],
        "asin": row[2],
        "amazon_url": row[3],
        "buy_box": float(row[4].replace('$', '').strip()) if row[4] and row[4] not in ['-', 'N/A'] else 0.0,
        "fba_fee": float(row[5].replace('$', '').strip()) if row[5] and row[5] not in ['-', 'N/A'] else 0.0,
        "referral_fee_pct": float(row[6].replace('%', '').strip()) if row[6] and row[6] not in ['-', 'N/A'] else 0.0,
        "referral_fee": float(row[7].replace('$', '').strip()) if row[7] and row[7] not in ['-', 'N/A'] else 0.0,
        "new_fba_count": row[8],
        "new_fbm_count": row[9],
        "top_seller_pct": row[10],
        "lowest_buy_box": float(row[11].replace('$', '').strip()) if row[11] and row[11] not in ['-', 'N/A'] else 0.0,
        "buy_box_drop_pct": float(row[12].replace('%', '').strip()) if row[12] and row[12] not in ['-', 'N/A'] else 0.0,
        "winner_count": row[13],
        "type":row[14]
    } for row in data[1:]
}

total_products = len(product_data)
driver = init_driver()

all_results_with_price, all_results_without_price = [], []  # Initialize batch lists

# Main loop to process products in batches
for start_index in range(0, total_products, batch_size):
    end_index = min(start_index + batch_size, total_products)
    batch_data = list(product_data.items())[start_index:end_index]

    for product_name, info in batch_data:
        pack_number = extract_pack_number(info['title']) or extract_pack_number(info['type']) or 1
        Attributes = extract_attribute_values(info['type'])
        variations = ", ".join(extract_variation(info['title']) or extract_variation(info['type']) or [""])
        adjusted_buy_box = info['buy_box'] / float(pack_number) if float(pack_number) != 0 else 0
        selenium_results_with_price, selenium_results_without_price = extract_price_and_link_with_selenium(product_name,variations,info['buy_box'],Attributes)
        
        product_entries, duplicate_entries = [], []

        # Process results with prices
        for title, link, price, description, web_pack, web_variations in selenium_results_with_price:
            web_pack = web_pack or 1
            price_float = float(price.replace('$', '').strip())
            price_per_unit = price_float / float(web_pack) if float(web_pack) != 0 else 0
            total_costs = price_per_unit + info['fba_fee'] + info['referral_fee']
            profit = adjusted_buy_box - total_costs
            roi = (profit / total_costs * 100) if total_costs > 0 else 0
            adjusted_fba_fee = info['fba_fee'] / float(pack_number) if float(pack_number) != 0 else info['fba_fee']
            adjusted_referral_fee = info['referral_fee'] / float(pack_number) if float(pack_number) != 0 else info['referral_fee']
            Combine_Data = f"{title}{description}{link}"
            
            row = [
            info['title'], info['sales_rank'], info['asin'], link, info['amazon_url'], info['buy_box'],
            adjusted_buy_box, adjusted_fba_fee, info['referral_fee_pct'], adjusted_referral_fee, price_float,
            price_per_unit, f"{profit:.2f}", f"{roi:.2f}%", info['new_fba_count'], info['new_fbm_count'],
            info['top_seller_pct'], info['lowest_buy_box'], info['buy_box_drop_pct'],info['winner_count'], title, description,
            variations, web_variations, pack_number, web_pack
        ]
            
            if compare_variations_and_Attributes(variations, web_variations,Attributes,Combine_Data) == "Yes":
                duplicate_entries.append(row)
            else:
                product_entries.append(row)

        # Select the cheapest rows and sort for sheet consistency
        sorted_product_entries = sorted(product_entries, key=lambda x: x[11])[:1]
        sorted_duplicate_entries = sorted(duplicate_entries, key=lambda x: x[11])[:2]
        all_results_with_price.extend(sorted_product_entries + sorted_duplicate_entries)

        # Process results without price
        for title, link, _, description, web_pack, web_variations in selenium_results_without_price:
            row = [
                info['title'], info['sales_rank'], info['asin'], link, info['amazon_url'], info['buy_box'], 
                adjusted_buy_box, info['fba_fee'], info['referral_fee_pct'], info['referral_fee'], 
                "Price Not Found", "No adjusted price", "Profit Placeholder", "ROI Placeholder", info['new_fba_count'], 
                info['new_fbm_count'], info['top_seller_pct'], info['lowest_buy_box'], info['buy_box_drop_pct'], info["winner_count"], 
                title, description, variations, web_variations, pack_number, web_pack
            ]
            all_results_without_price.append(row)

        # Increment counter and check if batch size reached
        counter += 1
        if counter >= batch_size:
            if all_results_with_price:
                sheet2.append_rows(all_results_with_price)
                all_results_with_price.clear()
            if all_results_without_price:
                sheet4.append_rows(all_results_without_price)
                all_results_without_price.clear()
            counter = 0  # Reset counter after batch processing

# Final append for any remaining rows
if all_results_with_price:
    sheet2.append_rows(all_results_with_price)
if all_results_without_price:
    sheet4.append_rows(all_results_without_price)

driver.quit()
print("Process completed successfully.")