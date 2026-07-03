from fastapi import APIRouter, Depends, HTTPException, Request
from ..database import execute_query, execute_commit
from ..middleware.auth import get_current_user, role_check
from ..utils.token_generator import generate_receipt_number
from ..utils.sms_service import send_distribution_sms
from datetime import datetime
from pydantic import BaseModel
from typing import List

router = APIRouter()

class DistributionItem(BaseModel):
    category: str
    quantity: float
    unit: str = "kg"

class DistributionRequest(BaseModel):
    token_id: str
    items: List[DistributionItem]

@router.post("/scan")
async def scan_token(req: dict, user: dict = Depends(role_check(['shopkeeper', 'admin']))):
    token_id = req.get('token_id')
    if not token_id: raise HTTPException(status_code=400, detail="Token ID required")

    tokens = await execute_query(
        """SELECT t.*, u.name as user_name, u.mobile as user_mobile, u.aadhaar_number, u.ration_card_number, 
                  u.address as user_address, s.shop_name, s.shop_type
           FROM tokens t LEFT JOIN users u ON t.user_id = u.id LEFT JOIN shops s ON t.shop_id = s.id
           WHERE TRIM(t.token_id) = TRIM(%s)""", (token_id,)
    )
    if not tokens: raise HTTPException(status_code=404, detail="Invalid token")

    token = tokens[0]
    if token['status'] == 'used': raise HTTPException(status_code=400, detail="Token already used")
    if token['status'] == 'expired' or token['expiry_time'] < datetime.now():
        await execute_commit("UPDATE tokens SET status = 'expired' WHERE id = %s", (token['id'],))
        raise HTTPException(status_code=400, detail="Token expired")

    # Date check: Token must be used on the booked date
    booked_date = token['slot_time'].date()
    today = datetime.now().date()
    if booked_date != today:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid Date! This token is booked for {booked_date}. It can only be used on that day."
        )

    # Shop ownership check
    if user['role'] == 'shopkeeper' and token['shop_id'] != user.get('shop_id'):
        raise HTTPException(status_code=403, detail=f"Invalid Shop! This token belongs to '{token['shop_name']}'")

    month_year = datetime.now().strftime('%Y-%m')
    stock = await execute_query(
        """SELECT rs.*, mq.allocated_qty, mq.sold_qty, (mq.allocated_qty - mq.sold_qty) as remaining_qty
           FROM ration_stock rs LEFT JOIN monthly_quota mq ON rs.shop_id = mq.shop_id 
           AND rs.category_name = mq.category_name AND mq.month_year = %s
           WHERE rs.shop_id = %s AND rs.quantity > 0""",
        (month_year, token['shop_id'])
    )
    
    await execute_commit("UPDATE tokens SET status = 'active' WHERE id = %s", (token['id'],))
    return {"message": "Token verified", "valid": True, "token": {**token, "status": "active"}, "availableStock": stock}

@router.post("/distribute")
async def distribute_ration(req: DistributionRequest, user: dict = Depends(role_check(['shopkeeper', 'admin'])), request: Request = None):
    tokens = await execute_query(
        "SELECT t.*, u.mobile as user_mobile FROM tokens t LEFT JOIN users u ON t.user_id = u.id WHERE TRIM(t.token_id) = TRIM(%s)",
        (req.token_id,)
    )
    if not tokens: raise HTTPException(status_code=404, detail="Token not found")
    token = tokens[0]

    if user['role'] == 'shopkeeper' and token['shop_id'] != user.get('shop_id'):
        raise HTTPException(status_code=403, detail="Unauthorized: This token does not belong to your shop.")
    
    if token['status'] == 'used': raise HTTPException(status_code=400, detail="Already distributed")

    month_year = datetime.now().strftime('%Y-%m')
    receipt_num = generate_receipt_number()

    for item in req.items:
        # Stock check
        quota = await execute_query(
            "SELECT (allocated_qty - sold_qty) as remaining FROM monthly_quota WHERE shop_id = %s AND month_year = %s AND category_name = %s",
            (token['shop_id'], month_year, item.category)
        )
        if quota and item.quantity > float(quota[0]['remaining']):
            raise HTTPException(status_code=400, detail=f"Insufficient quota for {item.category}. Remaining: {quota[0]['remaining']}kg")

        # Deduct stock
        await execute_commit(
            "UPDATE ration_stock SET quantity = quantity - %s WHERE shop_id = %s AND category_name = %s AND quantity >= %s",
            (item.quantity, token['shop_id'], item.category, item.quantity)
        )
        # Update quota
        await execute_commit(
            "UPDATE monthly_quota SET sold_qty = sold_qty + %s WHERE shop_id = %s AND month_year = %s AND category_name = %s",
            (item.quantity, token['shop_id'], month_year, item.category)
        )
        # Record history
        await execute_commit(
            "INSERT INTO distribution_history (user_id, token_id, shop_id, distributed_items, quantity, receipt_number) VALUES (%s, %s, %s, %s, %s, %s)",
            (token['user_id'], req.token_id, token['shop_id'], item.category, item.quantity, receipt_num)
        )

    await execute_commit("UPDATE tokens SET status = 'used' WHERE token_id = %s", (req.token_id,))
    
    item_summary = ", ".join([f"{i.category}: {i.quantity}{i.unit}" for i in req.items])
    await execute_commit(
        'INSERT INTO notifications (user_id, message, type) VALUES (%s, %s, %s)',
        (token['user_id'], f"Ration distributed: {item_summary}. Receipt: {receipt_num}", 'success')
    )
    
    await send_distribution_sms(token['user_mobile'], item_summary, receipt_num)
    
    socket = request.app.state.socket
    await socket.send_notification(token['user_id'], {"message": "Ration distributed!", "type": "success"})
    await socket.broadcast_stock_update(token['shop_id'], {"updated": True})

    return {"message": "Distribution successful", "receiptNumber": receipt_num}

@router.get("/bookings")
async def get_bookings(date: str = None, user: dict = Depends(role_check(['shopkeeper', 'admin']))):
    shop_id = user.get('shop_id')
    # Auto-expire tokens from past dates
    now = datetime.now()
    await execute_commit(
        "UPDATE tokens SET status = 'expired' WHERE status = 'booked' AND expiry_time < %s",
        (now,)
    )

    query = "SELECT t.*, u.name as user_name, u.mobile, u.ration_card_number FROM tokens t LEFT JOIN users u ON t.user_id = u.id WHERE (t.status = 'booked' OR t.status = 'active' OR t.status = 'used' OR t.status = 'expired')"
    params = []
    
    if user['role'] == 'shopkeeper':
        query += " AND t.shop_id = %s"
        params.append(shop_id)
    
    if date:
        query += " AND DATE(t.slot_time) = %s"
        params.append(date)
    else:
        query += " AND DATE(t.slot_time) = CURDATE()"
    
    query += " ORDER BY t.slot_time ASC"
    bookings = await execute_query(query, tuple(params))
    return {"bookings": bookings}

@router.get("/transactions")
async def get_transactions(date: str = None, user: dict = Depends(get_current_user)):
    shop_id = user.get('shop_id')
    query = "SELECT dh.*, u.name as user_name FROM distribution_history dh LEFT JOIN users u ON dh.user_id = u.id WHERE dh.shop_id = %s"
    params = [shop_id]
    if date:
        query += " AND DATE(dh.distribution_date) = %s"
        params.append(date)
    else:
        query += " AND DATE(dh.distribution_date) = CURDATE()"
    
    query += " ORDER BY dh.distribution_date DESC"
    transactions = await execute_query(query, tuple(params))
    return {"transactions": transactions}

@router.get("/receipt/{receipt_number}")
async def get_receipt(receipt_number: str):
    receipt = await execute_query(
        "SELECT dh.*, u.name as user_name, s.shop_name FROM distribution_history dh LEFT JOIN users u ON dh.user_id = u.id LEFT JOIN shops s ON dh.shop_id = s.id WHERE dh.receipt_number = %s",
        (receipt_number,)
    )
    return {"receipt": receipt[0] if receipt else None}
