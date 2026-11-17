from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time

# --- Setup Selenium Chrome Driver ---
chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

driver = webdriver.Chrome(service=Service("/usr/local/bin/chromedriver"), options=chrome_options)

try:
    # --- Visit the target page ---
    url = "https://www.eedistribution.com/hitlist.asp?eeshop=300&collect=Funko+Pop%21+Vinyl+Figures&SearchOrder=col"
    driver.get(url)

    # --- Prompt for manual login ---
    print("🔐 Please log in manually in the browser window.")
    input("✅ After logging in successfully, press Enter here to continue...")

    # --- Save page source to file ---
    with open("OutputSel.html", "w", encoding="utf-8") as file:
        file.write(driver.page_source)
    print("💾 Page source saved to OutputSel.html")

finally:
    driver.quit()
