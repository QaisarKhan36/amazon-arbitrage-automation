import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote
import random
import time
from Reg import extract_price_from_description, extract_pack_number, extract_variation

# Helper function to clean and convert price to float
def clean_price(price_text):
    try:
        price = float(price_text.replace('$', '').replace('US', '').replace(',', '').strip())
        return price
    except ValueError:
        return None

def random_delay():
    """Pause for a randomized period to mimic human interaction."""
    delay = random.uniform(1, 3)  # Random delay between 5 and 20 seconds
    print(f"Sleeping for {delay:.2f} seconds...")
    time.sleep(delay)

# Function to extract product details with Google bypass mechanisms and retry logic
def extract_product_details(product_name,variation,buybox):
    """Extracts link, title, description, and price from Google search results."""
    print("processing:",product_name)
    print("variation:",variation)
    random_delay()
    search_url = f"https://www.google.com/search?q={product_name.replace(' ', '+')}+USA+cheapestprice+'{variation}'"
    random_delay()
    
    # Retry logic for connection timeout
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.get(search_url, timeout=10)  # Set a timeout for the request
            break  # Exit loop if request is successful
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} of {max_retries} failed due to connection error: {e}")
            if attempt < max_retries - 1:
                print("Retrying in 3 minutes...")
                time.sleep(180)  # Wait for 3 minutes
            else:
                print(f"Max retries reached. Skipping '{product_name}' and moving to the next item.")
                return [], []  # Return empty lists if all retries fail

    soup = BeautifulSoup(response.text, 'html.parser')

    # Lists to store results based on price availability
    with_price = []
    without_price = []

    # Find all divs with the target class
    results = soup.find_all('div', class_='Gx5Zad xpd EtOod pkphOe')
    
    for result in results:
        # Extract and clean the link
        link_tag = result.find('a', href=True)
        if link_tag:
            raw_url = link_tag['href']
    
            # Direct extraction of actual link from href using string splitting
            if '/url?q=' in raw_url:
                link = raw_url.split('/url?q=')[1].split('&')[0]  # Split to isolate the URL
            else:
                link = raw_url  # For cases where the link is already direct

            # Decode the URL if needed
            link = unquote(link) if link else None

            # Skip links from unwanted domains
            excluded_domains = ["amazon.com", "aliexpress.com", "alibaba.com", "ubuy.com","poshmark.com","ebay.com","getuscart.com"]
            if not link or any(domain in link for domain in excluded_domains) or ".com" not in link:
                continue
        else:
            link = None

        # Extract title
        title_tag = result.select_one('.j039Wc h3 .BNeawe.vvjwJb.AP7Wnd')
        title = title_tag.get_text(strip=True) if title_tag else None

        # Extract description
        description_tag = result.select_one('.BNeawe.s3v9rd.AP7Wnd')
        description = description_tag.get_text(strip=True) if description_tag else None

        # Primary Price Extraction (span with price, specific div structure)
        price = None
        price_tag = result.find_all('span', class_='r0bn4c rQMQod')
        for tag in price_tag:
            if '$' in tag.text:
                price = clean_price(tag.text)
                if price is not None:
                    break

        # Fallback Price Extraction (from description if price not found above)
        if price is None and description:
            price = extract_price_from_description(description,buybox)

        combined_info = f"{title} {description} {link}" if title and description else ""
        web_pack = extract_pack_number(combined_info) or 1  # Default to 1 if no pack number found
        web_variation = extract_variation(combined_info)
        if isinstance(web_variation, list):
            web_variation = ", ".join(web_variation)

        # Prepare the result data
        result_data = (
            title, 
            link, 
            f"${price:.2f}" if price is not None and price > 0 else "$0.00", 
            description, 
            web_pack, 
            web_variation or ""
        )
        
        # Append to appropriate list based on price
        if price is not None and price > 0:
            with_price.append(result_data)
        else:
            without_price.append(result_data)

    return with_price, without_price
