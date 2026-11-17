import requests
from bs4 import BeautifulSoup
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urlparse, parse_qs, unquote
from Reg import extract_pack_number, extract_variation, AsinFromLink
from GoogleAmz import extract_product_details

# Global variables to track credentials
credentials_number = 1
max_credentials = 24
batch_size = 10  # Batch size for Google Sheets updates

def get_gspread_client():
    """Get gspread client using the current credentials file."""
    global credentials_number
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(f"credentials{credentials_number}.json", scope)
    return gspread.authorize(creds)

def switch_credentials_if_needed(client, spreadsheet_key):
    """Switch credentials if quota errors occur."""
    try:
        return client.open_by_key(spreadsheet_key).get_worksheet(1)  # Access sheet2
    except gspread.exceptions.APIError as e:
        if 'Quota' in str(e):
            global credentials_number
            credentials_number += 1
            print(f"Switching to credentials{credentials_number}.json due to quota error...")
            client = get_gspread_client()
            if credentials_number > max_credentials:
                raise Exception("All credentials exhausted. Please check your API usage.")
            return switch_credentials_if_needed(client, spreadsheet_key)
        else:
            raise

def clean_walmart_url(url):
    if "sp/track" in url:
        query_params = parse_qs(urlparse(url).query)
        if 'rd' in query_params:
            return unquote(query_params['rd'][0])
    return url

def save_product_data(base_url, max_pages):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    spreadsheet_key = "YOUR_SOURCING_SHEET_ID"
    client = get_gspread_client()
    sheet = switch_credentials_if_needed(client, spreadsheet_key)

    batch = []  # Temporary storage for rows in the current batch
    counter = 0  # Counter to track rows added to the current batch

    for page in range(1, max_pages + 1):
        url = f"{base_url}&page={page}"
        print(f"Fetching page {page}: {url}")

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            with open(f"OutputSoup.html", "w", encoding="utf-8") as file:
                file.write(response.text)

            soup = BeautifulSoup(response.text, "html.parser")
            product_elements = soup.find_all(
                "div",
                class_="sans-serif mid-gray relative flex flex-column w-100 hide-child-opacity",
            )

            for product in product_elements:
                try:
                    title_element = product.select_one("a[link-identifier] span")
                    title = title_element.get_text(strip=True) if title_element else "N/A"

                    price_element = product.select_one(
                        'div[data-automation-id="product-price"] .black.green'
                    )
                    if price_element:
                        price_text = re.sub(r"[^\d]", "", price_element.get_text())
                        price = f"{int(price_text) / 100:.2f}" if price_text else "N/A"
                    else:
                        dollar_amount = product.select_one('div[data-automation-id="product-price"] .f2')
                        cents_amount = product.select_one('div[data-automation-id="product-price"] .f6.f5-l')
                        price = f"{dollar_amount.get_text(strip=True)}.{cents_amount.get_text(strip=True)}" if dollar_amount and cents_amount else "N/A"

                    link_element = product.select_one("a[link-identifier]")
                    if link_element:
                        href = link_element["href"]
                        raw_product_link = href if href.startswith("https://www.walmart.com") else f"https://www.walmart.com{href}"
                        product_link = clean_walmart_url(raw_product_link)
                    else:
                        product_link = "N/A"

                    pack = extract_pack_number(f"{title} {product_link}")
                    variation = extract_variation(f"{title}{product_link}")
                    variation_str = ", ".join(variation) if isinstance(variation, list) else variation
                    pack_str = ", ".join(pack) if isinstance(pack, list) else pack
                    price = float(price.replace("$", "").replace(",", "").strip())
                    AdjustedCost = price/pack

                    with_price = extract_product_details(title, variation_str, price)
                    for Amztitle, Amzlink, Amzprice, Amzdescription, web_pack, web_variation in with_price:
                        Asin = AsinFromLink(Amzlink)
                        Amzprice = float(Amzprice.replace("$", "").replace(",", "").strip())
                        print(web_pack)
                        AdjustedPrice = Amzprice/web_pack
                        web_variation_str = ", ".join(web_variation) if isinstance(web_variation, list) else web_variation
                        web_pack_str = ", ".join(web_pack) if isinstance(web_pack, list) else web_pack

                        row = [
                            Amztitle, Asin, product_link, Amzlink, AdjustedCost, AdjustedPrice,
                            title, Amzdescription, web_variation_str, variation_str, web_pack_str, pack_str
                        ]
                        batch.append(row)
                        counter += 1

                        if counter >= batch_size:
                            # Upload the batch to Google Sheets
                            try:
                                sheet.append_rows(batch)
                                print(f"Uploaded {len(batch)} rows.")
                                batch.clear()  # Clear batch
                                counter = 0  # Reset counter
                            except gspread.exceptions.APIError as e:
                                print(f"Error appending rows: {e}")

                except Exception as e:
                    print(f"Error processing product: {e}")

        except requests.exceptions.RequestException as e:
            print(f"An error occurred while fetching page {page}: {e}")
            continue

    # Upload any remaining rows in the batch
    if batch:
        try:
            sheet.append_rows(batch)
            print(f"Uploaded {len(batch)} rows.")
        except gspread.exceptions.APIError as e:
            print(f"Error appending remaining rows: {e}")

# Example usage with Walmart's savings page URL
base_url = "https://www.walmart.com/browse/food/bettergoods-fall-flavors/976759_7128585_8911633_8470515?povid=976759_itemcarousel_976759_bettergoodscomfortfoods_Shopall_rweb_Sep_03&seo=food&seo=bettergoods-fall-flavors&seo=976759_7128585_8911633_8470515&page=1&affinityOverride=default"
max_pages = 3
save_product_data(base_url, max_pages)