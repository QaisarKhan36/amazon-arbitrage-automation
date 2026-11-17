# PriceTarget.py
from bs4 import BeautifulSoup
import re
import threading

def find_price(soup):
    """Attempts to extract price information from a BeautifulSoup object, with a timeout of 5 seconds."""
    
    def extract_numeric_price(text):
        """Helper function to extract numeric value from price text."""
        match = re.search(r"\d+(\.\d{2})?", text)
        return match.group() if match else None

    def attempt_price_patterns():
        """Attempts all defined patterns to locate a price."""
        price = None
        try:
            # Pattern 1: Check for 'price' meta tag (highest priority)
            meta_price = soup.find("meta", property="product:price:amount")
            if meta_price and meta_price.get("content"):
                price = meta_price["content"]

            # Pattern 2: If no main price, check for 'sale price' meta tag
            if not price:
                sale_meta = soup.find("meta", property="product:sale_price:amount")
                if sale_meta and sale_meta.get("content"):
                    price = sale_meta["content"]

            # Pattern 3: If still no price, check for 'regular price' meta tag as a fallback
            if not price:
                regular_meta = soup.find("meta", property="product:regular_price:amount")
                if regular_meta and regular_meta.get("content"):
                    price = regular_meta["content"]

            # Pattern 4: Check for itemprop attribute for the price (schema.org)
            if not price:
                price_tag = soup.find(attrs={"itemprop": "price"})
                if price_tag:
                    price = price_tag.get_text(strip=True)

            # Pattern 5: Common class names for price (e.g., 'price', 'sale-price', 'regular-price')
            if not price:
                price_tag = soup.find(class_="price") or soup.find(class_="sale-price") or soup.find(class_="regular-price")
                if price_tag:
                    price = price_tag.get_text(strip=True)

            # Pattern 6: Check specific 'ProductPricing' div or 'Text-ds' span for the price
            if not price:
                pricing_div = soup.find("div", class_="ProductPricing")
                if pricing_div:
                    span_price = pricing_div.find("span", class_="Text-ds")
                    if span_price:
                        price = span_price.get_text(strip=True)

            # Pattern 7: Target the nested 'price__current' class with 'money' class for the current price
            if not price:
                current_price_div = soup.find("div", class_="price__current")
                if current_price_div:
                    money_span = current_price_div.find("span", class_="money")
                    if money_span:
                        price = money_span.get_text(strip=True)

            # Pattern 8: Search for IDs commonly associated with price information
            if not price:
                price_tag = soup.find(id="price") or soup.find(id="sale-price") or soup.find(id="regular-price")
                if price_tag:
                    price = price_tag.get_text(strip=True)

            # Pattern 9: Check for 'item_price' class
            if not price:
                item_price_div = soup.find("div", class_="item_price")
                if item_price_div:
                    price = item_price_div.get_text(strip=True)

            # Pattern 10: Fallback to any text containing "$" or similar symbols
            if not price:
                price_tag = soup.find(text=lambda t: "$" in t or "€" in t or "£" in t)
                if price_tag:
                    price = price_tag.strip()

            # Pattern 11: Search for JSON-like price formats in text
            if not price:
                price_pattern = re.search(r'"price"\s*[:=]\s*["\']?(\d+(\.\d{2})?)["\']?', soup.get_text())
                if price_pattern:
                    price = price_pattern.group(1)

        except Exception as e:
            print(f"Error occurred while attempting to find price: {e}")

        return price

    # Wrapper to handle the timeout
    class PriceThread(threading.Thread):
        def __init__(self):
            super().__init__()
            self.price = None

        def run(self):
            self.price = attempt_price_patterns()

    # Start the price-finding thread with a 5-second timeout
    price_thread = PriceThread()
    price_thread.start()
    price_thread.join(timeout=5)  # Wait up to 5 seconds

    # If the thread is still running, skip and return None
    if price_thread.is_alive():
        print("Price extraction timed out.")
        return None

    # Extract and return numeric value only, if available, else skip (return None)
    return extract_numeric_price(price_thread.price) if price_thread.price else None