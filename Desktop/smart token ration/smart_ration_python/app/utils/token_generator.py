import uuid
import time
import random
import string
from datetime import datetime, timedelta

def generate_token_id():
    prefix = 'TKN'
    timestamp = hex(int(time.time()))[2:].upper()
    unique = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{timestamp}-{unique}"

def calculate_expiry(slot_time_str):
    if isinstance(slot_time_str, str):
        slot_time = datetime.fromisoformat(slot_time_str.replace('Z', '+00:00'))
    else:
        slot_time = slot_time_str
    return slot_time + timedelta(hours=2)

def generate_receipt_number():
    prefix = 'RCP'
    date_str = datetime.now().strftime('%Y%m%d')
    unique = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{date_str}-{unique}"
