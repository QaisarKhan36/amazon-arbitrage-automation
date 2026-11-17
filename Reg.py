# Reg.py
import re

def adjust_text_for_pack(text):
    # Normalize text: Replace special patterns, collapse spaces, and clean non-alphanumeric characters
    text = re.sub(r'(?<=\d)-(?=\d)', '.', text)  # Replace '-' with '.' between numbers
    text = re.sub(r'[-_/]', ' ', text)          # Replace other separators with spaces
    text = re.sub(r'[^\w\s.]', '', text)        # Remove special characters except periods
    return re.sub(r'\s+', ' ', text).strip()    # Collapse multiple spaces into one

def is_valid_number(num):
    return num < 2000  # Only consider numbers less than 2000 as valid

def find_additional_number(text, search_limit):
    pack_words = r"(pack|packs|pcs|pk|piece|pieces|set|sets|bundle|bundles|count|counts|case|cases|unit|units|lot|lots|bag|bottles?)"
    matches = re.finditer(pack_words, text, re.IGNORECASE)
    
    closest_number = None
    closest_distance = float('inf')
    
    # Find the closest valid number
    for match in matches:
        start, end = match.start(), match.end()
        left_context = text[max(0, start - search_limit):start]
        right_context = text[end:end + search_limit]

        # Look for integers in the context
        left_number = re.search(r"\b\d+(\.\d+)?\b", left_context[::-1])  # Reverse to search from right to left
        right_number = re.search(r"\b\d+(\.\d+)?\b", right_context)     # Search from left to right

        # Check left context number
        if left_number:
            number_str = left_number.group(0)[::-1]  # Reverse the string to get the actual number
            number = float(number_str) if '.' in number_str else int(number_str)
            if is_valid_number(number) and not isinstance(number, float):
                left_distance = start - len(left_context)  # Distance to the match from the left side
                if left_distance < closest_distance:
                    closest_number = number
                    closest_distance = left_distance

        # Check right context number
        if right_number:
            number_str = right_number.group(0)
            number = float(number_str) if '.' in number_str else int(number_str)
            if is_valid_number(number) and not isinstance(number, float):
                right_distance = end + len(right_context)  # Distance to the match from the right side
                if right_distance < closest_distance:
                    closest_number = number
                    closest_distance = right_distance

    return closest_number if closest_number is not None else 1  # Default to 1 if no valid number is found

def extract_pack_number(text, search_limit=10):
    text = adjust_text_for_pack(text)

    # Main regex to find numbers with pack-related keywords
    pattern = re.compile(
        r"((?:pack|packs|pcs|pk|piece|pieces|set|sets|bundle|bundles|count|counts|case|cases|unit|units|lot|lots|bag|bottle|bottles?)\s+\d+(\.\d+)?(?:\s+\w+)*)",
        re.IGNORECASE
    )
    match = pattern.search(text)
    if match:
        full_match = match.group(1)  # Get the full matched text
        # Extract just the number
        number_match = re.search(r"\d+(\.\d+)?", full_match)
        if number_match:
            number_str = number_match.group()
            number = float(number_str) if '.' in number_str else int(number_str)
            if isinstance(number, float):  # Skip float numbers and perform second attempt
                return find_additional_number(text, search_limit)
            if is_valid_number(number):
                return number
            # If the number is invalid (greater than 2000), perform second attempt
            return find_additional_number(text, search_limit)

    # Fallback methods if the main regex doesn't work
    def first_method(text):
        pack_pattern = re.compile(
            r"(?i)\b(\d+)\b\s*(?:-|x|of)?\s*(?:pack|pcs|pieces?|sets?|bundles?|counts?|cases?|units?|bottles?)|"
            r"(?:pack|pcs|pieces?|sets?|bundles?|counts?|cases?|units?|bottles?)\s*(?:-|x|of)?\s*\b(\d+)\b|"
            r"(?:pack|pcs|pieces?|sets?|bundles?|counts?|cases?|units?|bottles?)\s*\b(\d+)\b"
        )
        match = pack_pattern.search(text)
        if match:
            for group in match.groups():
                if group and group.isdigit():
                    number = int(group)
                    if is_valid_number(number):
                        return number
        return None

    # Try fallback methods
    pack_number = first_method(text)
    if pack_number is not None:
        return pack_number

    return find_additional_number(text, search_limit)

def adjust_text(text):
    # Specifically replace '-' with '.' only when it is between two numbers
    text = re.sub(r'(?<=\d)-(?=\d)', '.', text)
    
    # Replace other special characters like _ or - with a space
    text = re.sub(r'[-_/]', ' ', text)
    
    # Remove any non-alphanumeric characters except spaces
    text = re.sub(r'[^\w\s.]', '', text)
    
    # Collapse multiple spaces into one
    return re.sub(r'\s+', ' ', text).strip()

variation_pattern = re.compile(
    r"(?i)(\d+\.?\d*)\s*(ml|oz|fl\.?\s*oz|g|kg|lbs?|L|liters?|gal|gallons?|W|V|A|Ah|kWh|in\.?|cm|mm|ft|qt|mL|mg|cc|grams|milliliters|ounces?|pints?|pounds?)"
)
# Adjusting extract_variation to return formatted strings
def extract_variation(text):
    # Adjust the text if needed (this function should handle any cleaning)
    text = adjust_text(text)
    
    # Updated regex pattern to capture numbers with optional decimal points and units
    variation_pattern = re.compile(r'\b\d+(?:\.\d+)?\s*(?:oz|ml|g|lb|kg|fl oz|liters?)\b', re.IGNORECASE)

    # Find all matches in the text
    matches = variation_pattern.findall(text)

    # Filter and clean matches
    variations = [match.strip() for match in matches]

    return variations if variations else []

def extract_attribute_values(text):
    # Create regex patterns for ScentName and Color
    patterns = [
        r"ScentName:\s*([^;]+);?",
        r"Color:\s*([^;]+);?"
    ]
    
    # Find matches for both attributes and combine results
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text, re.IGNORECASE))
    
    # Strip whitespace and check for 'unscented' in ScentName
    matches = [match.strip() for match in matches]
    if any("unscented" in match.lower() for match in matches):
        return None  # Return None if 'unscented' is found in ScentName
    
    return matches if matches else []

def AsinFromLink(url):
    # Regular expression to capture the ASIN in the URL
    match = re.search(r'/([A-Z0-9]{10})(?:[/?]|$)', url)
    if match:
        return match.group(1)
    return None

def extract_price_from_description(description, buybox=None):  # Set buybox to None by default
    if buybox:
        buybox = re.sub(r'[^\d.]', '', str(buybox))  # Remove any non-numeric characters
        try:
            buybox = float(buybox)
        except ValueError:
            print(f"Invalid buybox value: {buybox}")
            buybox = None  # Set buybox to None if it's not a valid float

    # Find all potential price-like patterns in the description
    matches = re.finditer(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', description)
    potential_prices = []

    for match in matches:
        price_text = match.group(0)
        start, end = match.span()
        
        # Convert to float after removing any symbols like commas or extra currency symbols
        cleaned_price_text = re.sub(r'[^\d.]', '', price_text)
        
        # Get the text around the price to check for "$" or "US$"
        left_side = description[max(0, start - 10):start].lower()
        right_side = description[end:end + 20].lower()

        # Check for valid currency symbols near the price
        if ('$' in left_side or '$' in right_side or "us$" in left_side or "us$" in right_side):
            # Exclude prices with non-USD symbols
            if "a$" in left_side or "ca$" in left_side or "a$" in right_side or "ca$" in right_side:
                continue
            # Exclude prices related to delivery
            if "delivery" not in left_side and "delivery" not in right_side:
                # Convert the cleaned price text to a float
                try:
                    price = float(cleaned_price_text)
                except ValueError:
                    continue
                
                # If `buybox` is available, apply percentage condition
                if buybox:
                    if (price > 20 and 50 <= price * 100 / buybox <= 100) or \
                       (price <= 20 and 40 <= price * 100 / buybox <= 100):
                        potential_prices.append(price)
                else:
                    # If `buybox` is None, just collect valid prices without percentage check
                    potential_prices.append(price)

    # Return the filtered list of prices or None if no valid prices found
    return min(potential_prices) if potential_prices else None

