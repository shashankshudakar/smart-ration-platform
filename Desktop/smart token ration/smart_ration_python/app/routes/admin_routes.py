from fastapi import APIRouter, Depends, HTTPException, Request
from ..database import execute_query, execute_commit
from ..middleware.auth import get_current_user, role_check

router = APIRouter()

@router.get("/dashboard")
async def admin_dashboard(user: dict = Depends(role_check(['admin']))):
    try:
        user_count = await execute_query('SELECT COUNT(*) as count FROM users')
        pending_count = await execute_query("SELECT COUNT(*) as count FROM users WHERE status = 'pending'")
        token_count = await execute_query('SELECT COUNT(*) as count FROM tokens')
        dist_count = await execute_query('SELECT COUNT(*) as count FROM distribution_history')
        shop_count = await execute_query('SELECT COUNT(*) as count FROM shops')
        low_stock = await execute_query('SELECT COUNT(*) as count FROM ration_stock WHERE quantity <= min_threshold')
        
        recent_tokens = await execute_query(
            'SELECT t.*, u.name FROM tokens t LEFT JOIN users u ON t.user_id = u.id ORDER BY t.created_at DESC LIMIT 10'
        )

        return {
            "stats": {
                "totalUsers": user_count[0]['count'] if user_count else 0,
                "pendingApprovals": pending_count[0]['count'] if pending_count else 0,
                "totalTokens": token_count[0]['count'] if token_count else 0,
                "totalDistributions": dist_count[0]['count'] if dist_count else 0,
                "totalShops": shop_count[0]['count'] if shop_count else 0,
                "lowStockAlerts": low_stock[0]['count'] if low_stock else 0
            },
            "recentTokens": recent_tokens
        }
    except Exception as e:
        print(f"❌ Error in admin_dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users")
async def get_users(status: str = None, role: str = None, search: str = None, user: dict = Depends(role_check(['admin']))):
    query = 'SELECT id, name, mobile, aadhaar_number, ration_card_number, address, role, status, created_at FROM users WHERE 1=1'
    params = []
    if status:
        query += ' AND status = %s'
        params.append(status)
    if role:
        query += ' AND role = %s'
        params.append(role)
    if search:
        query += ' AND (name LIKE %s OR mobile LIKE %s)'
        params.append(f'%{search}%')
        params.append(f'%{search}%')
        
    query += ' ORDER BY created_at DESC'
    users = await execute_query(query, tuple(params))
    return {"users": users}

@router.put("/users/{id}/approve")
async def approve_user(id: int, request: Request, user: dict = Depends(role_check(['admin']))):
    await execute_commit("UPDATE users SET status = 'approved' WHERE id = %s", (id,))
    await execute_commit(
        'INSERT INTO notifications (user_id, message, type) VALUES (%s, %s, %s)',
        (id, 'Your account has been approved! You can now book tokens.', 'success')
    )
    
    socket = request.app.state.socket
    await socket.send_notification(id, {"message": "Account approved!", "type": "success"})
    return {"message": "User approved"}

@router.put("/users/{id}/reject")
async def reject_user(id: int, req: dict, user: dict = Depends(role_check(['admin']))):
    reason = req.get('reason', 'Not specified')
    await execute_commit("UPDATE users SET status = 'rejected' WHERE id = %s", (id,))
    await execute_commit(
        'INSERT INTO notifications (user_id, message, type) VALUES (%s, %s, %s)',
        (id, f'Your account has been rejected. Reason: {reason}', 'alert')
    )
    return {"message": "User rejected"}

@router.delete("/users/{id}")
async def delete_user(id: int, user: dict = Depends(role_check(['admin']))):
    await execute_commit("DELETE FROM users WHERE id = %s", (id,))
    return {"message": "User deleted"}

@router.get("/reports")
async def get_reports(shop_id: int = None, month: str = None, user: dict = Depends(role_check(['admin']))):
    from datetime import datetime
    if not month:
        month = datetime.now().strftime('%Y-%m')

    query = """SELECT dh.*, u.name as user_name, s.shop_name 
           FROM distribution_history dh 
           LEFT JOIN users u ON dh.user_id = u.id 
           LEFT JOIN shops s ON dh.shop_id = s.id 
           WHERE DATE_FORMAT(dh.distribution_date, '%Y-%m') = %s"""
    params = [month]

    if shop_id:
        query += " AND dh.shop_id = %s"
        params.append(shop_id)

    query += " ORDER BY dh.distribution_date DESC LIMIT 100"
    distributions = await execute_query(query, tuple(params))

    sum_query = """SELECT distributed_items, SUM(quantity) as total_qty, COUNT(*) as count 
           FROM distribution_history 
           WHERE DATE_FORMAT(distribution_date, '%Y-%m') = %s"""
    sum_params = [month]
    if shop_id:
        sum_query += " AND shop_id = %s"
        sum_params.append(shop_id)
    sum_query += " GROUP BY distributed_items"
    summary = await execute_query(sum_query, tuple(sum_params))

    return {"distributions": distributions, "summary": summary}

@router.get("/fraud-check")
async def get_fraud_alerts(user: dict = Depends(role_check(['admin']))):
    # Same logic as JS: check for multiple bookings with same ration card in short time
    alerts = await execute_query(
        """SELECT u.name, u.ration_card_number, COUNT(*) as booking_count 
           FROM tokens t JOIN users u ON t.user_id = u.id 
           WHERE t.status != 'cancelled' AND t.created_at >= DATE_SUB(NOW(), INTERVAL 1 DAY)
           GROUP BY u.ration_card_number HAVING booking_count > 1"""
    )
    return {"alerts": alerts}

@router.post("/alerts")
async def send_system_alert(data: dict, request: Request, admin: dict = Depends(role_check(['admin']))):
    target = data.get('target', 'all')
    message = data.get('message')
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    socket = request.app.state.socket
    notification_msg = f"ADMIN ALERT: {message}"
    
    if target == 'all':
        # Send to everyone (NULL target_role)
        # But we want to exclude the admin from seeing it in their own list if they sent it
        # Actually, let's just use target_role = 'user' and target_role = 'shopkeeper'
        # to avoid it showing for admins.
        await execute_commit(
            'INSERT INTO notifications (user_id, message, type, target_role) VALUES (NULL, %s, %s, "user")',
            (notification_msg, 'warning')
        )
        await execute_commit(
            'INSERT INTO notifications (user_id, message, type, target_role) VALUES (NULL, %s, %s, "shopkeeper")',
            (notification_msg, 'warning')
        )
        if socket:
            await socket.emit('new_notification', {"message": notification_msg, "type": "warning"})
    elif target == 'shopkeeper':
        await execute_commit(
            'INSERT INTO notifications (user_id, message, type, target_role) VALUES (NULL, %s, %s, "shopkeeper")',
            (notification_msg, 'warning')
        )
        if socket:
            await socket.emit('new_notification', {"message": notification_msg, "type": "warning", "target": "shopkeeper"})
    else:
        # Target specific role or 'user'
        await execute_commit(
            'INSERT INTO notifications (user_id, message, type, target_role) VALUES (NULL, %s, %s, "user")',
            (notification_msg, 'warning')
        )
        if socket:
            await socket.emit('new_notification', {"message": notification_msg, "type": "warning", "target": "user"})

    return {"message": "Alert broadcasted successfully"}

@router.get("/shopkeepers")
async def get_shopkeepers(user: dict = Depends(role_check(['admin']))):
    shopkeepers = await execute_query("SELECT * FROM users WHERE role = 'shopkeeper' ORDER BY created_at DESC")
    return {"shopkeepers": shopkeepers}

@router.post("/shops")
async def create_shop(data: dict, user: dict = Depends(role_check(['admin']))):
    address = data.get('address', '')
    location = data.get('location', '')
    full_address = f"{location}, {address}" if location and address else (address or location)
    
    await execute_commit(
        "INSERT INTO shops (shop_name, address, shop_type, is_active) VALUES (%s, %s, %s, 1)",
        (data['shop_name'], full_address, data.get('shop_type', 'village'))
    )
    return {"message": "Shop created successfully"}

@router.put("/shops/{id}")
async def update_shop(id: int, data: dict, user: dict = Depends(role_check(['admin']))):
    address = data.get('address', '')
    location = data.get('location', '')
    full_address = f"{location}, {address}" if location and address else (address or location)
    
    await execute_commit(
        "UPDATE shops SET shop_name = %s, address = %s, shop_type = %s WHERE id = %s",
        (data['shop_name'], full_address, data.get('shop_type', 'village'), id)
    )
    return {"message": "Shop updated successfully"}

@router.delete("/shops/{id}")
async def delete_shop(id: int, user: dict = Depends(role_check(['admin']))):
    await execute_commit("DELETE FROM shops WHERE id = %s", (id,))
    return {"message": "Shop deleted successfully"}
