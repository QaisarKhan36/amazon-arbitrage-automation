from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

# Setup Chrome options
options = Options()
options.add_argument("--start-maximized")

# Initialize WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    # Visit the website
    url = "https://shop.thriftywhite.com/beauty/"
    driver.get(url)

    # Wait for page to load (adjust sleep if needed)
    time.sleep(5)

    # Get page source
    page_source = driver.page_source

    # Save HTML to file
    with open("OutputSel.html", "w", encoding="utf-8") as f:
        f.write(page_source)

    print("Page source saved to OutputSel.html")

finally:
    driver.quit()
