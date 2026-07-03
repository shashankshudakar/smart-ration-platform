from fastapi import APIRouter, Depends, HTTPException, Request
from ..database import execute_query, execute_commit
from ..middleware.auth import hash_password, verify_password, create_access_token, get_current_user
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class LoginRequest(BaseModel):
    mobile: str
    password: str
    role: Optional[str] = "user"

class RegisterRequest(BaseModel):
    name: str
    mobile: str
    password: str
    aadhaar_number: Optional[str] = None
    ration_card_number: Optional[str] = None
    address: Optional[str] = None

@router.post("/register")
async def register(req: RegisterRequest):
    # Check if user already exists
    existing = await execute_query(
        'SELECT id FROM users WHERE mobile = %s OR aadhaar_number = %s OR ration_card_number = %s',
        (req.mobile, req.aadhaar_number or '', req.ration_card_number or '')
    )
    if existing:
        raise HTTPException(status_code=409, detail="User already exists with this mobile, Aadhaar, or ration card number")

    hashed_pw = hash_password(req.password)
    user_id = await execute_commit(
        'INSERT INTO users (name, mobile, aadhaar_number, ration_card_number, address, password, role, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
        (req.name, req.mobile, req.aadhaar_number, req.ration_card_number, req.address, hashed_pw, 'user', 'pending')
    )

    await execute_commit(
        'INSERT INTO notifications (user_id, message, type) VALUES (%s, %s, %s)',
        (user_id, 'Welcome to Smart Ration! Your account is pending approval.', 'info')
    )

    token = create_access_token({"id": user_id, "role": 'user', "name": req.name, "mobile": req.mobile})
    return {
        "message": "Registration successful",
        "token": token,
        "user": {"id": user_id, "name": req.name, "mobile": req.mobile, "role": 'user', "status": "pending"}
    }

@router.post("/login")
async def login(req: LoginRequest):
    # Admin login check
    if req.role == 'admin':
        admins = await execute_query('SELECT * FROM admins WHERE username = %s', (req.mobile,))
        if not admins:
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        admin = admins[0]
        if not verify_password(req.password, admin['password']) and req.password != admin['password']:
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        
        token = create_access_token({"id": admin['id'], "role": "admin", "name": admin.get('name', 'Admin'), "username": admin['username']})
        return {
            "message": "Admin login successful",
            "token": token,
            "user": {"id": admin['id'], "name": admin.get('name', 'Admin'), "role": "admin", "username": admin['username']}
        }

    # Shopkeeper login check
    if req.role == 'shopkeeper':
        shopkeepers = await execute_query('SELECT * FROM shopkeepers WHERE mobile = %s', (req.mobile,))
        if not shopkeepers:
            raise HTTPException(status_code=401, detail="Invalid shopkeeper credentials")
        shopkeeper = shopkeepers[0]
        
        if shopkeeper['status'] != 'approved':
            raise HTTPException(status_code=403, detail="Account pending admin approval.")
            
        if not verify_password(req.password, shopkeeper['password']) and req.password != shopkeeper['password']:
            raise HTTPException(status_code=401, detail="Invalid shopkeeper credentials")

        token = create_access_token({
            "id": shopkeeper['id'], "role": "shopkeeper", "name": shopkeeper['owner_name'], 
            "mobile": shopkeeper['mobile'], "shop_id": shopkeeper['shop_id'], "status": shopkeeper['status']
        })
        return {
            "message": "Shopkeeper login successful",
            "token": token,
            "user": {
                "id": shopkeeper['id'], "name": shopkeeper['owner_name'], "mobile": shopkeeper['mobile'],
                "role": "shopkeeper", "status": shopkeeper['status'], "shopDetails": shopkeeper
            }
        }

    # User login check
    users = await execute_query('SELECT * FROM users WHERE mobile = %s', (req.mobile,))
    if not users:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = users[0]
    
    if not verify_password(req.password, user['password']) and req.password != user['password']:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"id": user['id'], "role": user['role'], "name": user['name'], "mobile": user['mobile']})
    
    shop_details = None
    if user['role'] == 'shopkeeper':
        shops = await execute_query('SELECT * FROM shopkeepers WHERE mobile = %s', (user['mobile'],))
        if shops: shop_details = shops[0]

    return {
        "message": "Login successful",
        "token": token,
        "user": {
            **user,
            "shopDetails": shop_details
        }
    }

@router.get("/profile")
async def profile(user: dict = Depends(get_current_user)):
    if user['role'] == 'admin':
        admins = await execute_query('SELECT id, username, name, email, created_at FROM admins WHERE id = %s', (user['id'],))
        if not admins: raise HTTPException(status_code=404, detail="Admin not found")
        return {"user": {**admins[0], "role": "admin"}}

    users = await execute_query(
        'SELECT id, name, mobile, aadhaar_number, ration_card_number, address, role, status, created_at FROM users WHERE id = %s',
        (user['id'],)
    )
    if not users: raise HTTPException(status_code=404, detail="User not found")
    
    u = users[0]
    shop_details = None
    if u['role'] == 'shopkeeper':
        shops = await execute_query('SELECT * FROM shopkeepers WHERE mobile = %s', (u['mobile'],))
        if shops: shop_details = shops[0]

    return {"user": {**u, "shopDetails": shop_details}}

@router.put("/profile")
async def update_profile(req: dict, user: dict = Depends(get_current_user)):
    await execute_commit(
        'UPDATE users SET name = COALESCE(%s, name), address = COALESCE(%s, address), mobile = COALESCE(%s, mobile) WHERE id = %s',
        (req.get('name'), req.get('address'), req.get('mobile'), user['id'])
    )
    return {"message": "Profile updated successfully"}
