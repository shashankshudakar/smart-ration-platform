async def send_sms(mobile, message):
    print(f"📱 SMS [{mobile}]: {message}")
    # Stub for actual SMS API integration
    return {"success": True, "message": "SMS sent (stub)"}

async def send_token_booking_sms(mobile, token_id, slot_time, shop_name):
    message = f"🎫 Smart Ration Token Booked!\nToken: {token_id}\nSlot: {slot_time}\nShop: {shop_name}\nPlease arrive 10 mins before your slot."
    return await send_sms(mobile, message)

async def send_distribution_sms(mobile, items, receipt_number):
    message = f"✅ Ration Distributed!\nItems: {items}\nReceipt: {receipt_number}\nThank you for using Smart Ration."
    return await send_sms(mobile, message)
