import re

def extract_amount(note: str):
    if not note:
        return None

    text = note.lower().replace(',', '').replace('₹', '').strip()
    match = re.search(r'(\d+(?:\.\d+)?)(k)?', text)

    if not match:
        return None

    amount = float(match.group(1))
    if match.group(2):
        amount *= 1000

    return round(amount, 2)
