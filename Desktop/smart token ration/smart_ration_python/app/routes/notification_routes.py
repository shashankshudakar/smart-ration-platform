from fastapi import APIRouter, Depends, HTTPException, Request
from ..database import execute_query, execute_commit
from ..middleware.auth import get_current_user, role_check

router = APIRouter()

@router.get("/")
async def get_notifications(user: dict = Depends(get_current_user)):
    user_id = user['id']
    role = user['role']
    
    # Show:
    # 1. Notifications explicitly for this user_id
    # 2. Notifications for this user's role (admin, shopkeeper, user)
    # 3. Public notifications (target_role is NULL AND user_id is NULL)
    notifications = await execute_query(
        """SELECT * FROM notifications 
           WHERE user_id = %s 
           OR target_role = %s 
           OR (user_id IS NULL AND target_role IS NULL) 
           ORDER BY created_at DESC LIMIT 50""",
        (user_id, role)
    )
    unread = await execute_query(
        """SELECT COUNT(*) as count FROM notifications 
           WHERE (user_id = %s OR target_role = %s OR (user_id IS NULL AND target_role IS NULL)) 
           AND status = 'unread'""",
        (user_id, role)
    )
    return {"notifications": notifications, "unreadCount": unread[0]['count']}

@router.put("/{id}/read")
async def mark_read(id: int, user: dict = Depends(get_current_user)):
    await execute_commit("UPDATE notifications SET status = 'read' WHERE id = %s AND (user_id = %s OR target_role = %s)", (id, user['id'], user['role']))
    return {"message": "Notification marked as read"}

@router.put("/read-all")
async def read_all(user: dict = Depends(get_current_user)):
    await execute_commit("UPDATE notifications SET status = 'read' WHERE user_id = %s OR target_role = %s", (user['id'], user['role']))
    return {"message": "All notifications marked as read"}

@router.delete("/clear-all")
async def clear_all(user: dict = Depends(get_current_user)):
    # Delete notifications explicitly for this user OR for their role
    # Note: We probably shouldn't delete NULL/NULL public ones for everyone, 
    # but the user asked to "remove all".
    # Let's delete only those targeted to them specifically or their role.
    await execute_commit(
        "DELETE FROM notifications WHERE user_id = %s OR target_role = %s", 
        (user['id'], user['role'])
    )
    return {"message": "All notifications cleared"}

@router.post("/shopkeeper-alert")
async def shopkeeper_alert(data: dict, request: Request, user: dict = Depends(get_current_user)):
    if user['role'] != 'shopkeeper':
        raise HTTPException(status_code=403, detail="Only shopkeepers can send alerts")
    
    message = data.get('message')
    target = data.get('target', 'admin') # 'admin', 'users', or 'both'
    
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    socket = request.app.state.socket
    notification_msg = f"SHOPKEEPER ALERT ({user['name']}): {message}"
    
    if target == 'both':
        # Public notification
        await execute_commit(
            'INSERT INTO notifications (user_id, message, type, target_role, sender_id) VALUES (NULL, %s, %s, NULL, %s)',
            (notification_msg, 'warning', user['id'])
        )
        if socket:
            await socket.emit('new_notification', {"message": notification_msg, "type": "warning"})
    elif target == 'admin':
        # Admin-only notification
        await execute_commit(
            'INSERT INTO notifications (user_id, message, type, target_role, sender_id) VALUES (NULL, %s, %s, "admin", %s)',
            (notification_msg, 'warning', user['id'])
        )
        if socket:
            await socket.emit('new_notification', {"message": notification_msg, "type": "warning", "target": "admin"})
    elif target == 'users':
        # User-only (beneficiaries) notification
        await execute_commit(
            'INSERT INTO notifications (user_id, message, type, target_role, sender_id) VALUES (NULL, %s, %s, "user", %s)',
            (notification_msg, 'warning', user['id'])
        )
        if socket:
            await socket.emit('new_notification', {"message": notification_msg, "type": "warning", "target": "user"})

    return {"message": "Alert sent successfully"}

@router.post("/reply")
async def reply_notification(data: dict, request: Request, user: dict = Depends(role_check(['admin', 'shopkeeper']))):
    try:
        recipient_id = data.get('recipient_id')
        message = data.get('message')
        if not message:
            raise HTTPException(status_code=400, detail="Message required")

        notification_msg = f"{'ADMIN' if user['role'] == 'admin' else 'SHOPKEEPER'} REPLY: {message}"
        
        # If shopkeeper is replying, we need to know WHICH admin to reply to.
        # But usually we just target all admins or the specific sender_id.
        target_role = 'admin' if user['role'] == 'shopkeeper' else 'shopkeeper'
        
        # If recipient_id is provided, use it. Otherwise, if shopkeeper is replying, we might target role='admin'.
        # Actually, let's just use recipient_id which will be the sender_id from the original notif.
        
        await execute_commit(
            'INSERT INTO notifications (user_id, message, type, sender_id, target_role) VALUES (%s, %s, %s, %s, %s)',
            (recipient_id, notification_msg, 'info', user['id'], target_role)
        )
        
        socket = request.app.state.socket
        if socket:
            if recipient_id:
                await socket.send_notification(recipient_id, {"message": notification_msg, "type": "info"})
            else:
                await socket.emit('new_notification', {"message": notification_msg, "type": "info", "target": target_role})
        
        return {"message": "Reply sent successfully"}
    except Exception as e:
        print(f"Reply error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
