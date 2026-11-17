import re
import time
import gspread
import socket
import urllib3

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    WebDriverException
)


# =========================
# GOOGLE SHEETS SETTINGS
# =========================
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SOURCING_SHEET_ID/edit?gid=278435173#gid=278435173"
WORKSHEET_NAME = "sheet2"   # change to "Sheet2" if needed
SERVICE_ACCOUNT_FILE = "credentials1.json"


# =========================
# SELENIUM SETTINGS
# =========================
SELLER_URLS = [
    # Add the Amazon storefront links of the sellers you want to research, e.g.:
    "https://www.amazon.com/s?me=SELLER_ID_HERE&marketplaceID=ATVPDKIKX0DER",
]
CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"

HEADLESS = True
CHUNK_SIZE = 10
PAGE_WAIT = 20
SHORT_DELAY = 1.5
NEXT_PAGE_DELAY = 2.5
PRODUCT_PAGE_DELAY = 1.5

# =========================
# RETRY SETTINGS
# =========================
MAX_RETRIES = 10
RETRY_WAIT_SECONDS = 120


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def is_network_error(exc):
    msg = str(exc).lower()

    network_keywords = [
        "err_internet_disconnected",
        "err_name_not_resolved",
        "err_network_changed",
        "err_connection_reset",
        "err_connection_timed_out",
        "timeout",
        "timed out",
        "connection aborted",
        "connection refused",
        "remote disconnected",
        "temporary failure in name resolution",
        "dns",
        "network",
        "ssl",
        "proxy",
        "unable to connect",
        "connection error",
        "read timed out"
    ]

    if any(word in msg for word in network_keywords):
        return True

    return isinstance(exc, (
        TimeoutException,
        socket.timeout,
        ConnectionError,
        urllib3.exceptions.HTTPError,
        urllib3.exceptions.MaxRetryError,
        urllib3.exceptions.NewConnectionError,
        urllib3.exceptions.ConnectTimeoutError,
        urllib3.exceptions.ReadTimeoutError,
        WebDriverException
    ))


def retry_action(action, description, *args, **kwargs):
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return action(*args, **kwargs)
        except Exception as e:
            last_error = e

            if not is_network_error(e):
                raise

            print(f"[Retry {attempt}/{MAX_RETRIES}] Network issue during: {description}")
            print(f"Error: {e}")

            if attempt < MAX_RETRIES:
                print(f"Waiting {RETRY_WAIT_SECONDS} seconds before retry...\n")
                time.sleep(RETRY_WAIT_SECONDS)
            else:
                print(f"Max retries reached for: {description}")

    raise last_error


def wait_for_results(driver, timeout=PAGE_WAIT):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-main-slot"))
    )
    time.sleep(SHORT_DELAY)


def safe_wait_for_results(driver, timeout=PAGE_WAIT):
    return retry_action(wait_for_results, "waiting for Amazon results", driver, timeout)


def extract_price(card):
    try:
        whole = card.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.strip()
        try:
            frac = card.find_element(By.CSS_SELECTOR, "span.a-price-fraction").text.strip()
        except:
            frac = "00"

        whole = whole.replace(",", "").replace(".", "")
        return f"{whole}.{frac}"
    except:
        return ""


def extract_product_name(card):
    selectors = [
        "h2 a span",
        "a.a-link-normal h2 span",
        "span.a-size-base-plus",
        "span.a-size-medium"
    ]
    for sel in selectors:
        try:
            name = clean_text(card.find_element(By.CSS_SELECTOR, sel).text)
            if name:
                return name
        except:
            pass
    return ""


def normalize_amazon_url(url):
    if not url:
        return ""
    url = url.split("?")[0]
    m = re.search(r"(https?://www\.amazon\.com/.+?/(dp|gp/product)/[A-Z0-9]{10})", url)
    if m:
        return m.group(1)
    return url


def extract_product_url(card):
    selectors = [
        "h2 a",
        "a.a-link-normal.s-no-outline",
        "a.a-link-normal"
    ]
    for sel in selectors:
        try:
            href = card.find_element(By.CSS_SELECTOR, sel).get_attribute("href")
            if href:
                return normalize_amazon_url(href)
        except:
            pass
    return ""


def extract_asin(card, url=""):
    try:
        asin = card.get_attribute("data-asin")
        if asin and asin.strip():
            return asin.strip()
    except:
        pass

    if url:
        m = re.search(r"/dp/([A-Z0-9]{10})", url)
        if m:
            return m.group(1)

        m = re.search(r"/gp/product/([A-Z0-9]{10})", url)
        if m:
            return m.group(1)

    return ""


def extract_sales_rank_from_product_page(driver):
    time.sleep(PRODUCT_PAGE_DELAY)

    try:
        body_text = clean_text(driver.find_element(By.TAG_NAME, "body").text)

        patterns = [
            r"Best Sellers Rank\s*(.*?)(Customer Reviews|Date First Available|Manufacturer|ASIN|Item model number|Feedback)",
            r"Amazon Best Sellers Rank\s*(.*?)(Customer Reviews|Date First Available|Manufacturer|ASIN|Item model number|Feedback)"
        ]

        for pattern in patterns:
            m = re.search(pattern, body_text, re.IGNORECASE | re.DOTALL)
            if m:
                return clean_text(m.group(1))

        m = re.search(r"(#\d[\d,]*\s+in\s+.+)", body_text, re.IGNORECASE)
        if m:
            return clean_text(m.group(1))

    except:
        pass

    return ""


def _get_sales_rank_once(driver, product_url):
    if not product_url:
        return ""

    main_window = driver.current_window_handle
    sales_rank = ""

    try:
        driver.execute_script("window.open(arguments[0], '_blank');", product_url)
        driver.switch_to.window(driver.window_handles[-1])

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        sales_rank = extract_sales_rank_from_product_page(driver)

    finally:
        try:
            if len(driver.window_handles) > 1:
                driver.close()
        except:
            pass
        driver.switch_to.window(main_window)

    return sales_rank


def get_sales_rank(driver, product_url):
    try:
        return retry_action(
            _get_sales_rank_once,
            f"opening product page for sales rank: {product_url}",
            driver,
            product_url
        )
    except Exception as e:
        print(f"Could not get sales rank for {product_url}: {e}")
        return ""


def connect_google_sheet():
    gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
    sh = gc.open_by_url(GOOGLE_SHEET_URL)
    ws = sh.worksheet(WORKSHEET_NAME)
    return ws


def safe_connect_google_sheet():
    return retry_action(connect_google_sheet, "connecting to Google Sheet")


def append_to_sheet(ws, rows):
    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")


def safe_append_to_sheet(ws, rows):
    if rows:
        retry_action(append_to_sheet, "writing chunk to Google Sheet", ws, rows)


def flush_chunk(ws, chunk_rows):
    if chunk_rows:
        safe_append_to_sheet(ws, chunk_rows)
        print(f"Flushed {len(chunk_rows)} rows to Google Sheet")
        chunk_rows.clear()


def get_existing_asins(ws):
    existing = set()
    values = retry_action(ws.get_all_values, "reading existing rows from Google Sheet")

    if not values:
        return existing

    for row in values[1:]:
        if len(row) >= 3:
            asin = row[2].strip()
            if asin:
                existing.add(asin)

    return existing


def ensure_header(ws):
    values = retry_action(ws.get_all_values, "checking Google Sheet header")
    if not values:
        retry_action(
            ws.append_row,
            "creating Google Sheet header",
            ["Product Name", "Sales Rank", "ASIN", "Amazon URL", "Price"]
        )


def get_result_cards(driver):
    return driver.find_elements(By.CSS_SELECTOR, "div.s-result-item[data-asin]")


def process_current_page(driver, ws, existing_asins, page_number, chunk_rows):
    cards = get_result_cards(driver)
    print(f"\nPage {page_number}: Found {len(cards)} result cards")

    page_seen_asins = set()
    page_added = 0

    for i in range(len(cards)):
        try:
            cards = get_result_cards(driver)
            if i >= len(cards):
                break

            card = cards[i]

            asin = extract_asin(card)
            url = extract_product_url(card)

            if not asin:
                asin = extract_asin(card, url)

            if not asin:
                continue

            if asin in existing_asins or asin in page_seen_asins:
                print(f"Skipped duplicate ASIN: {asin}")
                continue

            name = extract_product_name(card)
            price = extract_price(card)
            sales_rank = get_sales_rank(driver, url)

            row = [name, sales_rank, asin, url, price]
            chunk_rows.append(row)

            existing_asins.add(asin)
            page_seen_asins.add(asin)
            page_added += 1

            print(f"{page_number}.{i+1} | {name} | {sales_rank} | {asin} | {price}")

            if len(chunk_rows) >= CHUNK_SIZE:
                flush_chunk(ws, chunk_rows)

        except StaleElementReferenceException:
            print(f"Stale element on item {i+1}, skipping.")
        except Exception as e:
            print(f"Error on page {page_number}, card {i+1}: {e}")

    return page_added


def _go_to_next_page_once(driver):
    next_selectors = [
        "a.s-pagination-next",
        "a[aria-label='Go to next page']",
        "a.s-pagination-item.s-pagination-next"
    ]

    next_button = None
    for sel in next_selectors:
        try:
            elem = driver.find_element(By.CSS_SELECTOR, sel)
            classes = (elem.get_attribute("class") or "").lower()
            aria_disabled = (elem.get_attribute("aria-disabled") or "").lower()

            if "s-pagination-disabled" in classes or aria_disabled == "true":
                continue

            next_button = elem
            break
        except:
            pass

    if not next_button:
        return False

    old_url = driver.current_url

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
    time.sleep(1)

    try:
        next_button.click()
    except:
        driver.execute_script("arguments[0].click();", next_button)

    time.sleep(NEXT_PAGE_DELAY)

    try:
        WebDriverWait(driver, 15).until(lambda d: d.current_url != old_url)
    except TimeoutException:
        pass

    wait_for_results(driver, timeout=PAGE_WAIT)
    return True


def go_to_next_page(driver):
    try:
        return retry_action(_go_to_next_page_once, "moving to next Amazon page", driver)
    except Exception as e:
        print(f"Could not go to next page: {e}")
        return False


def build_driver():
    chrome_options = Options()

    if HEADLESS:
        chrome_options.add_argument("--headless=new")

    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=en-US")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
    """)

    return driver


def safe_driver_get(driver, url):
    def _open():
        driver.get(url)
        return True
    return retry_action(_open, f"opening page: {url}")


def main():
    ws = safe_connect_google_sheet()
    ensure_header(ws)
    existing_asins = get_existing_asins(ws)
    print(f"Loaded {len(existing_asins)} existing ASINs from sheet")

    driver = build_driver()
    chunk_rows = []

    try:
        total_added = 0

        for seller_index, seller_url in enumerate(SELLER_URLS, start=1):
            print("\n" + "=" * 80)
            print(f"Starting seller {seller_index}/{len(SELLER_URLS)}")
            print(f"URL: {seller_url}")
            print("=" * 80)

            try:
                safe_driver_get(driver, seller_url)
                safe_wait_for_results(driver)

                page_number = 1
                seller_added = 0

                while True:
                    added = process_current_page(driver, ws, existing_asins, page_number, chunk_rows)
                    total_added += added
                    seller_added += added

                    has_next = go_to_next_page(driver)
                    if not has_next:
                        print(f"\nNo more next page for seller {seller_index}.")
                        break

                    page_number += 1

                flush_chunk(ws, chunk_rows)
                print(f"Finished seller {seller_index}. New rows added: {seller_added}")

            except Exception as e:
                print(f"Error while processing seller {seller_index}: {e}")
                flush_chunk(ws, chunk_rows)
                continue

        flush_chunk(ws, chunk_rows)

        print(f"\nDone. Total new rows added: {total_added}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()