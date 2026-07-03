import socketio
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .config import settings
from .database import init_db
from .demo_data import ensure_demo_accounts
from .routes import auth_routes, token_routes, stock_routes, admin_routes, shopkeeper_routes, notification_routes, chatbot_routes

# Initialize FastAPI app
app = FastAPI(title="Smart Ration Platform API")

# Initialize Socket.IO
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, app)

# Static files and Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event
@app.on_event("startup")
async def startup():
    await init_db()
    await ensure_demo_accounts()

# Socket.IO Handlers
connected_users = {}

@sio.event
async def connect(sid, environ):
    print(f"🔌 Client connected: {sid}")

@sio.event
async def join(sid, user_id):
    await sio.enter_room(sid, f"user_{user_id}")
    connected_users[sid] = user_id
    print(f"👤 User {user_id} joined room")

@sio.event
async def join_shop(sid, shop_id):
    await sio.enter_room(sid, f"shop_{shop_id}")
    print(f"🏪 Socket {sid} joined shop_{shop_id}")

@sio.event
async def join_admin(sid):
    await sio.enter_room(sid, "admin_room")
    print(f"👑 Admin joined admin room")

@sio.event
async def disconnect(sid):
    user_id = connected_users.pop(sid, "unknown")
    print(f"❌ Client disconnected: {sid} (User: {user_id})")

# Helper functions for Socket.IO (will be attached to app state)
class SocketHandlers:
    @staticmethod
    async def notify_user(user_id, event, data):
        await sio.emit(event, data, room=f"user_{user_id}")

    @staticmethod
    async def notify_shop(shop_id, event, data):
        await sio.emit(event, data, room=f"shop_{shop_id}")

    @staticmethod
    async def notify_admin(event, data):
        await sio.emit(event, data, room="admin_room")

    @staticmethod
    async def broadcast_queue_update(shop_id, data):
        await sio.emit('queue_update', data, room=f"shop_{shop_id}")

    @staticmethod
    async def broadcast_stock_update(shop_id, data):
        await sio.emit('stock_update', data, room=f"shop_{shop_id}")
        await sio.emit('stock_update', {"shopId": shop_id, **data}, room="admin_room")

    @staticmethod
    async def send_notification(user_id, notification):
        await sio.emit('new_notification', notification, room=f"user_{user_id}")

    @staticmethod
    async def emit(event, data, room=None):
        await sio.emit(event, data, room=room)

app.state.socket = SocketHandlers

# Include Routes
app.include_router(auth_routes.router, prefix="/api/auth", tags=["Auth"])
app.include_router(token_routes.router, prefix="/api/tokens", tags=["Tokens"])
app.include_router(stock_routes.router, prefix="/api/stock", tags=["Stock"])
app.include_router(admin_routes.router, prefix="/api/admin", tags=["Admin"])
app.include_router(shopkeeper_routes.router, prefix="/api/shopkeeper", tags=["Shopkeeper"])
app.include_router(notification_routes.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(chatbot_routes.router, prefix="/api/chatbot", tags=["Chatbot"])

# UI Routes (Plain HTML)
@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/dashboard")
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/tokens")
async def tokens_page(request: Request):
    return templates.TemplateResponse("tokens.html", {"request": request})

@app.get("/book")
async def book_page(request: Request):
    return templates.TemplateResponse("book.html", {"request": request})

@app.get("/notifications")
async def notifications_page(request: Request):
    return templates.TemplateResponse("notifications.html", {"request": request})

@app.get("/admin")
async def admin_hub_page(request: Request):
    return templates.TemplateResponse("admin_hub.html", {"request": request})

@app.get("/admin/users")
async def admin_users_page(request: Request):
    return templates.TemplateResponse("admin_users.html", {"request": request})

@app.get("/admin/alerts")
async def admin_alerts_page(request: Request):
    return templates.TemplateResponse("admin_alerts.html", {"request": request})

@app.get("/admin/shops")
async def admin_shops_page(request: Request):
    return templates.TemplateResponse("admin_shops.html", {"request": request})

@app.get("/stock")
async def stock_page(request: Request):
    return templates.TemplateResponse("stock.html", {"request": request})

@app.get("/reports")
async def reports_page(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request})

@app.get("/shopkeeper")
async def shopkeeper_page(request: Request):
    return templates.TemplateResponse("shopkeeper.html", {"request": request})

@app.get("/shopkeeper/history")
async def shopkeeper_history_page(request: Request):
    return templates.TemplateResponse("distribution_history.html", {"request": request})

@app.get("/shopkeeper/stock")
async def shopkeeper_stock_page(request: Request):
    return templates.TemplateResponse("shopkeeper_stock.html", {"request": request})

@app.get("/shopkeeper/broadcast")
async def shopkeeper_broadcast_page(request: Request):
    return templates.TemplateResponse("shopkeeper_alerts.html", {"request": request})

# Health Check
@app.get("/api/health")
async def health():
    return {
        "status": "OK", 
        "project": "Smart Token Ration Platform",
        "connected_clients": len(connected_users)
    }
