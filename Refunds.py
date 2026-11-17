from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re

# Google Sheets setup
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_PARTNER_A_ORDERS_SHEET_ID/edit?gid=628548376#gid=628548376"
SHEET_NAME = "SHIPPED"
OUTPUT_HTML_FILE = "OutputSoup.html"

# Function to authenticate with Google Sheets
def get_gspread_client():
    credentials_file = "credentials1.json"  # Update with your credentials file
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    return gspread.authorize(credentials)

def main():
    # Initialize WebDriver
    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Step 1: Open Amazon Seller Central and wait for login
    driver.get("https://sellercentral.amazon.com/")
    print("Please log in to Amazon Seller Central...")
    time.sleep(30)  # give time to login manually
    input("Press Enter once logged in and ready to continue...")

    # Step 2: Open Google Sheets and read links
    client = get_gspread_client()
    sheet = client.open_by_url(SPREADSHEET_URL).worksheet(SHEET_NAME)
    all_links = sheet.col_values(1)  # column A
    links = all_links[1:]  # skip header row (row 1)

    print(f"Found {len(links)} links to process.")

    # Step 3: Visit each link and check for refunds
    for idx, link in enumerate(links, start=2):  # row 2 onward
        if not link.strip():
            continue

        try:
            print(f"\nVisiting row {idx}, link: {link}")
            driver.get(link)
            time.sleep(8)  # wait for page load

            html = driver.page_source
            with open(OUTPUT_HTML_FILE, "w", encoding="utf-8") as f:
                f.write(html)

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            refund_value = None

            # Find the div with "Refund"
            refund_label = soup.find("span", string="Refund")
            if refund_label:
                parent_div = refund_label.find_parent("div", class_="a-column")
                if parent_div and parent_div.find_next_sibling("div"):
                    refund_text = parent_div.find_next_sibling("div").get_text(strip=True)
                    match = re.search(r"-US\$(\d+(\.\d{1,2})?)", refund_text)
                    if match:
                        refund_value = "-" + match.group(1)

            # If refund found, update column O (15th column)
            if refund_value:
                print(f"➡️ Found refund {refund_value} for row {idx}, updating column O")
                sheet.update_cell(idx, 15, refund_value)  # column O = 15
            else:
                print(f"No refund for row {idx}")

            time.sleep(10)  # wait before next page

        except Exception as e:
            print(f"⚠️ Failed to process row {idx}: {e}")

    driver.quit()
    print("Done visiting all links.")

if __name__ == "__main__":
    main()
