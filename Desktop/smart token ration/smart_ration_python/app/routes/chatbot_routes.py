from fastapi import APIRouter, Depends, HTTPException, Header
from ..database import execute_query
from ..middleware.auth import get_current_user
import jwt
from ..config import settings

router = APIRouter()

@router.post("/ask")
async def ask_bot(data: dict, authorization: str = Header(None)):
    message = data.get("message", "").lower()
    user_id = None
    user_data = None

    # Try to identify user if logged in
    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.split(" ")[1]
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
            user_id = payload.get("id")
            # Fetch real user data for "correct" answers
            rows = await execute_query("SELECT * FROM users WHERE id = %s", (user_id,))
            if rows:
                user_data = rows[0]
        except:
            pass

    # Knowledge Base
    FAQ = {
        "quota": "In Gadag, your monthly eligibility is 10kg Rice and 5kg Wheat per family member, free of cost.",
        "booking": "Slots are open from the 15th to the 30th of every month. Please use the 'Book Slot' dashboard.",
        "location": "Your assigned shop is based on your residential address. You can view it in the 'Book Slot' section.",
        "support": "Contact Gadag District Food & Civil Supplies at 08372-230000 for help."
    }

    response = ""

    # Personalized Status Check
    if ("my status" in message or "am i approved" in message) and user_data:
        status = user_data['status']
        if status == 'approved':
            response = f"Good news, {user_data['name']}! Your account is fully Approved. You can proceed to book your ration slots."
        elif status == 'pending':
            response = f"Hello {user_data['name']}, your account is currently Pending approval from the Admin. Please wait 24-48 hours."
        else:
            response = f"I see your account status is '{status}'. Please contact the district office for more details."
    
    # Check current tokens
    elif ("my token" in message or "my booking" in message) and user_id:
        tokens = await execute_query("SELECT * FROM tokens WHERE user_id = %s AND status = 'booked'", (user_id,))
        if tokens:
            response = f"You have an active booking (Token ID: {tokens[0]['token_id']}) scheduled for {tokens[0]['slot_time']}. Don't forget to carry your phone for the QR scan!"
        else:
            response = "You don't have any active ration bookings right now. You can book one in the 'Book Slot' section."

    # General FAQ
    elif any(word in message for word in ["rice", "wheat", "how much", "eligibility", "quota"]):
        response = FAQ["quota"]
    elif any(word in message for word in ["book", "slot", "when", "date"]):
        response = FAQ["booking"]
    elif any(word in message for word in ["shop", "where", "location", "center"]):
        response = FAQ["location"]
    elif any(word in message for word in ["help", "contact", "call", "support"]):
        response = FAQ["support"]
    elif any(word in message for word in ["hi", "hello", "namaste"]):
        response = f"Namaste! I am your SmartRation AI. I can help you check your status, quotas, or find your ration shop."
    else:
        response = "I'm not exactly sure about that. Try asking about your 'account status', 'ration quota', or 'how to book a slot'."

    return {"response": response}
