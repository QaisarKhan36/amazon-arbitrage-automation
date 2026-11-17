from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

# ------------------- CONFIG -------------------
TARGET_URL = "https://sellercentral.amazon.com/orders-v3/mfn/unshipped"
OUTPUT_FILE = "OutputSel.html"
# ----------------------------------------------

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument("--start-maximized")

# Create WebDriver instance
driver = webdriver.Chrome(service=Service(), options=chrome_options)

# Visit the target page
print(f"Opening page: {TARGET_URL}")
driver.get(TARGET_URL)

# Wait for manual login
print("\nPlease log in manually if required.")
input("After you're fully logged in and the page has loaded, press ENTER to continue...")

# Wait for full load
time.sleep(3)

# Get and save the HTML
page_html = driver.page_source
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(page_html)
print(f"\n✅ HTML has been saved to {OUTPUT_FILE}")

# Parse the HTML
soup = BeautifulSoup(page_html, "html.parser")

# --- Extract Order Numbers and Quantities ---
print("\n📦 Extracting order numbers and quantities...\n")

orders_found = False

for row in soup.select('tr'):
    # Find the order number
    order_link = row.select_one('a[href*="/orders-v3/order/"]')
    if not order_link:
        continue

    order_number = order_link.text.strip()

    # Find the corresponding quantity in the same row or sibling cells
    quantity_label = row.find('span', string="Quantity")
    if quantity_label:
        quantity_value = quantity_label.find_next("b")
        if quantity_value:
            quantity = quantity_value.text.strip()
            print(f'the order number "{order_number}" and then its quantity: {quantity}')
            orders_found = True

if not orders_found:
    print("❌ No orders with quantities found.")

# Optional: Close the browser
# driver.quit()
