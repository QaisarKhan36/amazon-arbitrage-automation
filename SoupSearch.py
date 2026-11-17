import gspread
from oauth2client.service_account import ServiceAccountCredentials
from ExtractSoup import extract_product_details
from Reg import extract_pack_number, extract_variation

# Configuration for credentials and limits
credentials_number = 1
max_credentials = 24
spreadsheet_key = "YOUR_SOURCING_SHEET_ID"
batch_size = 10
counter = 0  # Initialize counter

def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_filename = f'credentials{credentials_number}.json'
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_filename, scope)
    return gspread.authorize(creds)

def switch_credentials_if_needed(client):
    try:
        return client.open_by_key(spreadsheet_key).sheet1
    except gspread.exceptions.APIError as e:
        if 'Quota' in str(e):
            global credentials_number
            credentials_number += 1
            client = get_gspread_client()
            return switch_credentials_if_needed(client)
        else:
            raise

# Comparison function to check if variations match
def compare_variations(var, web_var):
    existing_variation_list = [v.strip().lower() for v in var.split(",") if v.strip()]
    new_variation_list = [v.strip().lower() for v in web_var.split(",") if v.strip()]
    if not existing_variation_list and not new_variation_list:
        return "Yes"
    elif not existing_variation_list and new_variation_list:
        return "Yes"
    elif any(new_var in existing_variation_list for new_var in new_variation_list):
        return "Yes"
    else:
        return "No"

client = get_gspread_client()
sheet1 = switch_credentials_if_needed(client)
sheet2 = client.open_by_key(spreadsheet_key).worksheet("sheet2")
sheet3 = client.open_by_key(spreadsheet_key).worksheet("sheet3")
sheet4 = client.open_by_key(spreadsheet_key).worksheet("sheet4")

print("Fetching data from Google Sheets...")
data = sheet1.get_all_values()

product_data = {row[0]: {
    "title": row[0], "sales_rank": row[1], "asin": row[2], "amazon_url": row[3],
    "buy_box": float(row[4].replace('$', '').strip()) if row[4] and row[4] not in ['-', 'N/A'] else 0.0,
    "fba_fee": float(row[5].replace('$', '').strip()) if row[5] else 0.0,
    "referral_fee_pct": float(row[6].replace('%', '').strip()) if row[6] else 0.0,
    "referral_fee": float(row[7].replace('$', '').strip()) if row[7] else 0.0,
    "new_fba_count": row[8], "new_fbm_count": row[9], "top_seller_pct": row[10],
    "lowest_buy_box": float(row[11].replace('$', '').strip()) if row[11] else 0.0,
    "buy_box_drop_pct": float(row[12].replace('%', '').strip()) if row[12] else 0.0,
    "winner_count": row[13],
    "type":row[14]
} for row in data[1:]}

sheet2_batch = []
sheet4_batch = []

for product_name, info in product_data.items():
    # Extract product details
    pack_number = extract_pack_number(info['title']) or extract_pack_number(info['type']) or 1
    variations = ", ".join(extract_variation(info['title']) or extract_variation(info['type']) or [""])
    with_price, without_price = extract_product_details(product_name,variations,info['buy_box'])
    print("With price found:", len(with_price))
    print("Without price found:", len(without_price))

    # Process insufficient price results
    if len(with_price) < 3:
        row_data = [
            info['title'], info['sales_rank'], info['asin'], info['amazon_url'], info['buy_box'],
            info['fba_fee'], info['referral_fee_pct'], info['referral_fee'], info['new_fba_count'],
            info['new_fbm_count'], info['top_seller_pct'], info['lowest_buy_box'], info['buy_box_drop_pct'],
            info['winner_count']
        ]
        sheet3.append_row(row_data)
        print(f"Row for '{product_name}' appended to sheet3 due to insufficient with_price results.")
        continue

    # Process with-price results for sheet2
    sorted_with_price = sorted(with_price, key=lambda x: float(x[2].replace('$', '').strip()))
    selected_rows = [sorted_with_price[0]]
    matching_variations = [
        row for row in sorted_with_price[1:]
        if compare_variations(variations, row[5]) == "Yes"
    ][:2]

    selected_rows.extend(matching_variations)

    for title, link, price, description, web_pack, web_variations in selected_rows:
    # Ensure web_pack is a single number or find a match with variations if it's a list
        if isinstance(web_pack, list):
            print("web pack",web_pack)
            if len(web_pack) == 1:
                # Convert the single element to float
                web_pack_value = float(str(web_pack[0]))
            else:
                # Try to find the pack number that matches the pack_number
                matching_pack = next((float(p) for p in web_pack if p == pack_number), None)

                if matching_pack is not None:
                    # If a match is found, use it
                    web_pack_value = matching_pack
                else:
                    # Fallback: Find the closest pack number to pack_number
                    if web_pack:  # Ensure the list isn't empty
                        web_pack_value = min([float(p) for p in web_pack], key=lambda x: abs(x - float(pack_number)))
                    else:
                        # Default to 1 if no valid pack numbers in the list
                        web_pack_value = 1
        else:
            # If web_pack is not a list, convert web_pack directly
            web_pack_value = float(web_pack) if web_pack else 1  # Default to 1 if empty

        # Now we can safely calculate price_per_unit
        price_float = float(price.replace('$', '').strip()) if price.startswith('$') else 0.0
        price_per_unit = price_float / web_pack_value if web_pack_value != 0 else 0

        # Adjusted costs and calculations remain the same
        adjusted_buy_box = info['buy_box'] / float(pack_number) if float(pack_number) != 0 else 0
        adjusted_fba_fee = info['fba_fee'] / float(pack_number) if float(pack_number) != 0 else info['fba_fee']
        adjusted_referral_fee = info['referral_fee'] / float(pack_number) if float(pack_number) != 0 else info['referral_fee']
        total_costs = price_per_unit + adjusted_fba_fee + adjusted_referral_fee
        profit = adjusted_buy_box - total_costs
        roi = (profit / total_costs * 100) if total_costs > 0 else 0

        row = [
            info['title'], info['sales_rank'], info['asin'], link, info['amazon_url'], info['buy_box'],
            adjusted_buy_box, adjusted_fba_fee, info['referral_fee_pct'], adjusted_referral_fee, price_float,
            price_per_unit, f"${profit:.2f}", f"{roi:.2f}%", info['new_fba_count'], info['new_fbm_count'],
            info['top_seller_pct'], info['lowest_buy_box'], info['buy_box_drop_pct'],info['winner_count'], title, description,
            variations, web_variations, pack_number, web_pack
        ]
        sheet2_batch.append(row)

    # Process without-price results for sheet4
    for title, link, _, description, web_pack, web_variations in without_price:
        web_pack = web_pack or 1
        row = [
            info['title'], info['sales_rank'], info['asin'], link, info['amazon_url'], info['buy_box'],
            adjusted_buy_box, adjusted_fba_fee, info['referral_fee_pct'], adjusted_referral_fee, "price float",
            "price/unit", "profit", "roi", info['new_fba_count'], info['new_fbm_count'],
            info['top_seller_pct'], info['lowest_buy_box'], info['buy_box_drop_pct'],info['winner_count'], title, description,
            variations, web_variations, pack_number, web_pack
        ]
        sheet4_batch.append(row)

    # Increment counter
    counter += 1

    # Check if counter has reached the batch size
    if counter >= batch_size:
        if sheet2_batch:
            sheet2.append_rows(sheet2_batch)
            sheet2_batch.clear()
        if sheet4_batch:
            sheet4.append_rows(sheet4_batch)
            sheet4_batch.clear()
        counter = 0  # Reset counter after batch processing

# Final append for remaining rows
if sheet2_batch:
    sheet2.append_rows(sheet2_batch)
if sheet4_batch:
    sheet4.append_rows(sheet4_batch)
