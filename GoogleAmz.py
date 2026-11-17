from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import unquote
import re
from Reg import extract_price_from_description, extract_pack_number, extract_variation

def clean_price(price_text):
    try:
        price = float(price_text.replace('$', '').replace('US', '').replace(',', '').strip())
        return price
    except ValueError:
        return None

def AsinFromLink(url):
    match = re.search(r'/dp/([A-Z0-9]{10})(?:[/?]|$)', url)
    return match.group(1) if match else None

def extract_product_details(res):
    
    with_price = []
    results = res.find_all('div', class_='tF2Cxc')

    for result in results:
        link_tag = result.find('a', href=True)
        if link_tag:
            raw_url = link_tag['href']
            link = unquote(raw_url.split('/url?q=')[1].split('&')[0]) if '/url?q=' in raw_url else raw_url

            if 'amazon.com' in link and '/dp/' in link:
                asin = AsinFromLink(link)
                if asin:
                    title_tag = result.select_one('h3')
                    title = title_tag.get_text(strip=True) if title_tag else None
                    
                    description_tag = result.select_one('.VwiC3b')
                    description = description_tag.get_text(strip=True) if description_tag else None
                    
                    price = None
                    price_tag = result.find_all('span')
                    for tag in price_tag:
                        if '$' in tag.text:
                            price = clean_price(tag.text)
                            if price is not None:
                                break
                    
                    if price is None and description:
                        price = extract_price_from_description(description)  # Now it works without buybox

                    
                    combined_info = f"{title} {description}" if title and description else ""
                    web_pack = extract_pack_number(combined_info) or 1
                    web_variation = extract_variation(combined_info)
                    if isinstance(web_variation, list):
                        web_variation = ", ".join(web_variation)
                    
                    result_data = (
                        title, 
                        asin,
                        link, 
                        f"${price:.2f}" if price is not None and price > 0 else "$0.00", 
                        description, 
                        web_pack, 
                        web_variation or ""
                    )
                    with_price.append(result_data)
    
    return with_price
