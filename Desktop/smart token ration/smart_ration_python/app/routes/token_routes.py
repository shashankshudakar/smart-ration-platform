from fastapi import APIRouter, Depends, HTTPException, Request
from ..database import execute_query, execute_commit
from ..middleware.auth import get_current_user, role_check
from ..utils.token_generator import generate_token_id, calculate_expiry
from ..utils.qr_generator import generate_qr_code
from ..utils.sms_service import send_token_booking_sms
from datetime import datetime
from pydantic import BaseModel

router = APIRouter()

class TokenBookRequest(BaseModel):
    shop_id: int
    slot_time: str

@router.post("/book")
async def book_token(req: TokenBookRequest, user: dict = Depends(get_current_user), request: Request = None):
    # Check if user is approved
    users = await execute_query('SELECT status, name, mobile FROM users WHERE id = %s', (user['id'],))
    if not users or users[0]['status'] != 'approved':
        raise HTTPException(status_code=403, detail="Your account must be approved before booking tokens")

    # Validate booking date is between 15th and 30th of the month
    slot_date = req.slot_time.split('T')[0]
    slot_time_only = req.slot_time.split('T')[1]
    booking_day = int(slot_date.split('-')[2])
    if booking_day < 15 or booking_day > 30:
        raise HTTPException(status_code=400, detail="Booking is only allowed between 15th and 30th of the month")

    # Prevent booking past slots for today
    now = datetime.now()
    if slot_date == now.strftime('%Y-%m-%d'):
        slot_hour = int(slot_time_only.split(':')[0])
        if now.hour >= slot_hour:
            raise HTTPException(status_code=400, detail="This time slot has already passed for today")

    existing = await execute_query(
        "SELECT id FROM tokens WHERE user_id = %s AND shop_id = %s AND DATE(slot_time) = %s AND status IN ('booked', 'active')",
        (user['id'], req.shop_id, slot_date)
    )
    if existing:
        raise HTTPException(status_code=409, detail="You already have a token booked for this shop on this date")

    # Daily limit check (30)
    shop_bookings = await execute_query(
        "SELECT COUNT(*) as count FROM tokens WHERE shop_id = %s AND DATE(slot_time) = %s AND status != 'cancelled'",
        (req.shop_id, slot_date)
    )
    if shop_bookings[0]['count'] >= 30:
        raise HTTPException(status_code=403, detail="This shop has reached its daily limit of 30 bookings.")

    # Slot limit check (10)
    slot_bookings = await execute_query(
        "SELECT COUNT(*) as count FROM tokens WHERE shop_id = %s AND slot_time = %s AND status != 'cancelled'",
        (req.shop_id, req.slot_time)
    )
    if slot_bookings[0]['count'] >= 10:
        raise HTTPException(status_code=403, detail="This slot is full. Please select another time.")

    token_id = generate_token_id()
    expiry_time = calculate_expiry(req.slot_time)
    
    qr_data = {
        "tokenId": token_id,
        "userId": user['id'],
        "shopId": req.shop_id,
        "slotTime": req.slot_time,
        "timestamp": int(datetime.now().timestamp() * 1000)
    }
    qr_code = await generate_qr_code(qr_data)

    queue_count = await execute_query(
        "SELECT COUNT(*) as count FROM tokens WHERE shop_id = %s AND DATE(slot_time) = %s AND status IN ('booked', 'active')",
        (req.shop_id, slot_date)
    )
    queue_pos = queue_count[0]['count'] + 1

    await execute_commit(
        'INSERT INTO tokens (token_id, user_id, shop_id, slot_time, qr_code, status, expiry_time, queue_position) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
        (token_id, user['id'], req.shop_id, req.slot_time, qr_code, 'booked', expiry_time, queue_pos)
    )

    await execute_commit(
        'INSERT INTO notifications (user_id, message, type) VALUES (%s, %s, %s)',
        (user['id'], f'Token {token_id} booked! Pos: #{queue_pos}', 'success')
    )

    # Get shop name for SMS
    shops = await execute_query('SELECT shop_name FROM shops WHERE id = %s', (req.shop_id,))
    shop_name = shops[0]['shop_name'] if shops else 'Ration Shop'
    await send_token_booking_sms(users[0]['mobile'], token_id, req.slot_time, shop_name)

    # Socket updates
    socket = request.app.state.socket
    await socket.notify_user(user['id'], 'token_booked', {"tokenId": token_id, "queuePosition": queue_pos})
    await socket.broadcast_queue_update(req.shop_id, {"totalInQueue": queue_pos, "date": slot_date})

    return {
        "message": "Token booked successfully",
        "token": {"token_id": token_id, "qr_code": qr_code, "queue_position": queue_pos, "shop_name": shop_name}
    }

@router.get("/my-tokens")
async def my_tokens(user: dict = Depends(get_current_user)):
    tokens = await execute_query(
        "SELECT t.*, s.shop_name, s.address as shop_address FROM tokens t LEFT JOIN shops s ON t.shop_id = s.id WHERE t.user_id = %s ORDER BY t.created_at DESC",
        (user['id'],)
    )
    # Check expiry in logic (as per original JS)
    now = datetime.now()
    for t in tokens:
        if t['status'] == 'booked' and t['expiry_time'] < now:
            await execute_commit("UPDATE tokens SET status = 'expired' WHERE id = %s", (t['id'],))
            t['status'] = 'expired'
            
    return {"tokens": tokens}

@router.put("/{token_id}/cancel")
async def cancel_token(token_id: str, user: dict = Depends(get_current_user)):
    await execute_commit(
        "UPDATE tokens SET status = 'cancelled' WHERE token_id = %s AND user_id = %s AND status = 'booked'",
        (token_id, user['id'])
    )
    return {"message": "Token cancelled successfully"}

@router.get("/availability/{shop_id}")
async def get_availability(shop_id: int, date: str = None):
    target_date = date or datetime.now().strftime('%Y-%m-%d')
    # Per-slot bookings
    slot_bookings = await execute_query(
        "SELECT slot_time, COUNT(*) as count FROM tokens WHERE shop_id = %s AND DATE(slot_time) = %s AND status != 'cancelled' GROUP BY slot_time",
        (shop_id, target_date)
    )
    # Total daily bookings
    daily = await execute_query(
        "SELECT COUNT(*) as count FROM tokens WHERE shop_id = %s AND DATE(slot_time) = %s AND status != 'cancelled'",
        (shop_id, target_date)
    )
    return {
        "availability": slot_bookings,
        "dailyTotal": daily[0]['count'] if daily else 0,
        "dailyLimit": 30,
        "slotLimit": 10
    }

@router.get("/{shop_id}/queue")
async def get_queue(shop_id: int):
    today = datetime.now().strftime('%Y-%m-%d')
    queue = await execute_query(
        "SELECT t.token_id, t.slot_time, t.status, t.queue_position, u.name FROM tokens t LEFT JOIN users u ON t.user_id = u.id WHERE t.shop_id = %s AND DATE(t.slot_time) = %s AND t.status IN ('booked', 'active') ORDER BY t.queue_position ASC",
        (shop_id, today)
    )
    return {"queue": queue}

@router.get("/my-history/year")
async def my_history(user: dict = Depends(get_current_user)):
    # Tokens booked in the last 1 year
    tokens = await execute_query(
        """SELECT t.token_id, t.slot_time, t.status, t.created_at, s.shop_name
           FROM tokens t LEFT JOIN shops s ON t.shop_id = s.id
           WHERE t.user_id = %s AND t.created_at >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
           ORDER BY t.created_at DESC""",
        (user['id'],)
    )
    # Distributions in the last 1 year
    distributions = await execute_query(
        """SELECT dh.distributed_items, dh.quantity, dh.receipt_number, dh.distribution_date, s.shop_name
           FROM distribution_history dh LEFT JOIN shops s ON dh.shop_id = s.id
           WHERE dh.user_id = %s AND dh.distribution_date >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
           ORDER BY dh.distribution_date DESC""",
        (user['id'],)
    )
    return {"tokens": tokens, "distributions": distributions}
