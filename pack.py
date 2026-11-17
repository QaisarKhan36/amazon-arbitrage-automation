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
    print(f"Processed text for pack extraction: {text}")

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
                print(f"Float number detected: {number_str}, skipping...")
                return find_additional_number(text, search_limit)
            if is_valid_number(number):
                return number
            # If the number is invalid (greater than 2000), perform second attempt
            print(f"Invalid number detected: {number}, greater than 2000, skipping...")
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

# Test cases
print(extract_pack_number("This is a pack of 2 items."))  # Expected: 2
print(extract_pack_number("Contains a 4 of count 3.48oz of liquid bottles."))  # Expected: 4 (after second attempt)
print(extract_pack_number("Pack x 10 pieces of set."))  # Expected: 10
print(extract_pack_number("https://www.walmart.com/ip/Tobacco-Touch-EDP-Perfume-By-Maison-Alhambra-80-ML-7-Fl-Oz-Pack-o-3.4/2398027700"))  # Expected: 1
