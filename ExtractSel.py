from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import re
import random
from Reg import extract_pack_number, extract_variation, extract_price_from_description  # Import from Reg.py

# Setup for Selenium WebDriver
chrome_options = Options()
# chrome_options.add_argument("--headless")  # Run in headless mode for performance
service = Service('/usr/local/bin/chromedriver')
driver = webdriver.Chrome(service=service, options=chrome_options)

def random_delay():
    """Pause for a randomized period to mimic human interaction."""
    delay = random.uniform(0.1, 1.5)  # Random delay between 1 and 10 seconds
    print(f"Sleeping for {delay:.2f} seconds...")
    time.sleep(delay)

def wait_for_bot_check():
    """Detects if a bot check page appears and waits for manual resolution."""
    while True:
        if "Our systems have detected unusual traffic" in driver.page_source or "robot check" in driver.page_source:
            print("Bot check detected! Please solve it manually in the browser.")
            input("Press Enter to continue once you've solved the bot check...")
        else:
            break

# Helper function to clean and convert price to float
def clean_price(price_text):
    try:
        # Ensure the input is a string
        if not isinstance(price_text, str):
            price_text = str(price_text)
        price = float(price_text.replace('US$', '').replace('$', '').replace(',', '').strip())
        return price
    except ValueError:
        return 0.0

# Function to extract product details
def extract_price_and_link_with_selenium(product_name, variation, BuyBox, Attributes):
    print(f"Processing: {product_name} with attributes: {Attributes}")
    search_url = f"https://www.google.com/search?q={product_name.replace(' ', '+')}+{variation}+vipbarbersupply"
    random_delay()
    driver.get(search_url)
    wait_for_bot_check()  # Check for bot verification
    random_delay()

    # Save page source for debugging
    with open("OutputSoup.html", "w", encoding="utf-8") as file:
        file.write(driver.page_source)

    results_with_price, results_without_price = [], []

    # Function to extract data from a page
    def extract_data_from_page():
        try:
            # Locate all the result divs
            entity_divs = driver.find_elements(By.XPATH, "//h3[@class='LC20lb MBeuO DKV0Md']/ancestor::a[1]/ancestor::div[starts-with(@class, 'N54PNb')]")
            print(f"Found {len(entity_divs)} results on current page.")
            for div in entity_divs:
                # Extract title
                title_element = div.find_element(By.XPATH, ".//h3[contains(@class, 'LC20lb')]")
                title = title_element.text if title_element else "No title available"

                # Extract link
                link_element = div.find_element(By.XPATH, ".//a[@jsname='UWckNb']")
                link = link_element.get_attribute("href") if link_element else "No link available"

                # Skip excluded domains
                excluded_domains = ["dhgate.com", "aliexpress.com", "alibaba.com", "ubuy.com", "poshmark.com", "ebay.com", "getuscart.com","picclick.com","doba.com","shopabunda.com","tiktok.com","tiendamia.com","mercari.com","temptalia.com","quora.com","youtube.com","noon.com","bong.com","reddit.com","merriam-webster.com","techtarget.com","marykay.com","camelcamelcamel.com"]
                if not link or any(domain in link for domain in excluded_domains) or not (".com" in link or ".us" in link):
                    continue

                # Initialize price_text
                price_text = ""

                # First, check for any div or span containing $ or US$
                price_containers = div.find_elements(By.XPATH, ".//span[contains(text(), '$') or contains(text(), 'US$')] | .//div[contains(text(), '$') or contains(text(), 'US$')] | .//b[contains(text(), '$') or contains(text(), 'US$')]")
                # Process and print the extracted prices
                for price_element in price_containers:
                    # Get the text of the element
                    price_text = price_element.text.strip()
                    if len(price_text) < 14:
                        price_text = price_text
                    elif len(price_text) > 14 and len(price_text) < 45:
                        price_match = re.search(r"(US?\$\d+\.\d+|\$\d+\.\d+)", price_text)
                        if price_match:
                            price_text = price_match.group(1)
                    elif "to" in price_text:
                        price_text = price_text.split("to")[0].strip()

                # Extract description
                description_elements = div.find_elements(By.XPATH, ".//div[contains(@class, 'VwiC3b')]")
                description = description_elements[0].text if description_elements else "No description available"

                # Fallback: Extract price from description if not found
                if not price_text and description:
                    price_text = extract_price_from_description(description, BuyBox)

                # Clean the extracted price
                price_float = clean_price(price_text) if price_text else 0.0

                if ".com" in link:
                    linkTrim = link.split(".com", 1)[1] if ".com" in link else ""
                elif ".us" in link:
                    linkTrim = link.split(".us", 1)[1] if ".us" in link else ""
                else:
                    linkTrim = link

                # Extract additional info (Pack and Variation)
                combined_info = f"{title} {description} {linkTrim}"
                combined_info_all = f"{title} {description} {linkTrim}"
                web_pack = extract_pack_number(combined_info) or 1  # Default to 1 if not found
                web_variations = ", ".join(extract_variation(combined_info_all))

                # Prepare the result data
                result = (
                    title,
                    link,
                    f"${price_float:.2f}" if price_float > 0 else "$0.00",
                    description,
                    web_pack,
                    web_variations
                )
                
                print("------")
                print("Title:", title)
                print("Link:", link)
                print("Price:", price_text)
                print("Description:", description)
                print("------\n")


                # Append to appropriate list
                if price_float > 0:
                    results_with_price.append(result)
                else:
                    results_without_price.append(result)
        except Exception as e:
            print(f"Error processing: {e}")

    # Extract data from the first page
    extract_data_from_page()

    # Try navigating to the second page
    try:
        next_button = driver.find_element(By.ID, "pnnext")
        next_button.click()
        wait_for_bot_check()  # Check for bot verification before continuing
        random_delay()  # Allow the second page to load
        extract_data_from_page()  # Extract data from the second page
    except Exception as e:
        print(f"No 'Next' button found or error navigating to the next page")

    return results_with_price, results_without_price
