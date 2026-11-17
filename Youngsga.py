from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Path to your ChromeDriver
chrome_driver_path = "/usr/local/bin/chromedriver"  # Update if necessary

# Set Chrome options (non-headless so you can log in)
options = Options()
options.add_argument("--window-size=1200,800")
# options.add_argument("--headless")  # Don't use headless so you can interact

# Initialize the browser
service = Service(executable_path=chrome_driver_path)
driver = webdriver.Chrome(service=service, options=options)

# Open the target URL
url = "https://youngsga.com/collections/wholesale-hair-styling-tools"
driver.get(url)

# Prompt for manual login
print("🔒 Please log in using the browser window.")
input("✅ After logging in and the page has fully loaded, press Enter here to continue...")

# Capture the fully rendered HTML
html = driver.page_source

# Save to file
with open("OutputSel.html", "w", encoding="utf-8") as f:
    f.write(html)

print("✅ HTML content saved to OutputSel.html")

# Close the browser
driver.quit()
