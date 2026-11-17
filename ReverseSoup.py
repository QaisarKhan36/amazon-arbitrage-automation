import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import unquote

# Google Sheets authentication
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials1.json", scope)
    return gspread.authorize(creds)

# Get data from Sheet1
def get_sheet_data(sheet_id, sheet_name):
    client = get_gspread_client()
    sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
    return sheet.get_all_values(), sheet

# Perform a Google search and return the HTML
def google_search(query):
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    response = requests.get(search_url, headers=headers)
    time.sleep(3)  # Avoid triggering bot detection
    return response.text

# Extract Amazon search results
def extract_amazon_results(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    
    for result in soup.find_all('div', class_='tF2Cxc'):
        link_tag = result.find('a', href=True)
        if not link_tag:
            continue
        
        raw_url = link_tag['href']
        if '/url?q=' in raw_url:
            link = raw_url.split('/url?q=')[1].split('&')[0]
        else:
            link = raw_url
        
        link = unquote(link)
        if 'amazon.com' not in link:
            continue  # Only include Amazon results
        
        title_tag = result.find('h3')
        amazon_title = title_tag.get_text(strip=True) if title_tag else "N/A"
        
        desc_tag = result.select_one('.VwiC3b')
        amazon_desc = desc_tag.get_text(strip=True) if desc_tag else "N/A"
        
        results.append((amazon_title, link, "N/A", amazon_desc))  # No direct price info from Google
        
    return results

# Beautify and save HTML content
def beautify_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    formatted_html = soup.prettify()

    # Save the formatted HTML
    with open("OutputSoup.html", "w", encoding="utf-8") as file:
        file.write(formatted_html)
    
    print("✅ HTML saved in OutputSoup.html")

# Update Sheet3 with extracted data
def update_sheet3(sheet_id, data):
    client = get_gspread_client()
    sheet = client.open_by_key(sheet_id).worksheet("sheet3")
    sheet.append_rows(data, value_input_option="RAW")

# Main function to extract and search
def extract_and_search():
    spreadsheet_id = "YOUR_SOURCING_SHEET_ID"
    sheet_data, sheet1 = get_sheet_data(spreadsheet_id, "sheet1")
    results = []
    
    for row in sheet_data[1:]:  # Skip header
        try:
            title, web_link, cost, *_ = row  # Extract relevant columns
            print(f"\n🔍 Searching: {title}")
            
            html_content = google_search(title)
            amazon_results = extract_amazon_results(html_content)
            
            if amazon_results:
                for amazon_title, amazon_link, amazon_price, amazon_desc in amazon_results:
                    print(f"🎯 Found: {amazon_title} | {amazon_link}")
                    results.append([title, web_link, cost, amazon_title, amazon_link, amazon_price, amazon_desc])
            else:
                print("❌ No Amazon results found. Saving full HTML for debugging.")
                beautify_html(html_content)
                results.append([title, web_link, cost, "N/A", "N/A", "N/A", "N/A"])
            
            time.sleep(3)  # Prevent excessive requests
        except Exception as e:
            print(f"⚠️ Error processing row {row}: {e}")
    
    if results:
        update_sheet3(spreadsheet_id, results)
    print("\n✅ Completed extraction and update.")

# Run the script
extract_and_search()
