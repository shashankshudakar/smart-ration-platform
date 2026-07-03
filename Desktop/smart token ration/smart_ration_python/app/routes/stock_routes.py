from fastapi import APIRouter, Depends, HTTPException, Request
from ..database import execute_query, execute_commit
from ..middleware.auth import get_current_user, role_check
from datetime import datetime

router = APIRouter()

QUOTA_CONFIG = {
    "village": {"Rice": 10000, "Wheat": 10000},
    "city": {"Rice": 10000, "Wheat": 10000}
}

@router.get("/shops/list")
async def list_shops():
    try:
        shops = await execute_query("SELECT id, shop_name, address, shop_type FROM shops")
        return {"shops": shops}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def ensure_monthly_quota(shop_id: int):
    month_year = datetime.now().strftime('%Y-%m')
    existing = await execute_query('SELECT id FROM monthly_quota WHERE shop_id = %s AND month_year = %s LIMIT 1', (shop_id, month_year))
    if existing: return

    shops = await execute_query('SELECT shop_type FROM shops WHERE id = %s', (shop_id,))
    if not shops: return
    
    shop_type = shops[0].get('shop_type', 'village')
    quotas = QUOTA_CONFIG.get(shop_type, QUOTA_CONFIG['village'])

    for category, qty in quotas.items():
        await execute_commit(
            "INSERT IGNORE INTO monthly_quota (shop_id, month_year, category_name, allocated_qty, sold_qty) VALUES (%s, %s, %s, %s, 0)",
            (shop_id, month_year, category, qty)
        )
        
        # Sync ration_stock
        stock_exists = await execute_query('SELECT id FROM ration_stock WHERE shop_id = %s AND category_name = %s', (shop_id, category))
        if stock_exists:
            await execute_commit('UPDATE ration_stock SET quantity = %s WHERE id = %s', (qty, stock_exists[0]['id']))
        else:
            await execute_commit(
                'INSERT INTO ration_stock (shop_id, category_name, quantity, unit, min_threshold, price_per_unit) VALUES (%s, %s, %s, %s, %s, %s)',
                (shop_id, category, qty, 'kg', 10, 3.00 if category == 'Rice' else 2.00)
            )

@router.get("/{shop_id}")
async def get_shop_stock(shop_id: int):
    await ensure_monthly_quota(shop_id)
    month_year = datetime.now().strftime('%Y-%m')
    stock = await execute_query(
        """SELECT rs.*, s.shop_name, s.shop_type, mq.allocated_qty, mq.sold_qty, (mq.allocated_qty - mq.sold_qty) as remaining_qty 
           FROM ration_stock rs LEFT JOIN shops s ON rs.shop_id = s.id 
           LEFT JOIN monthly_quota mq ON rs.shop_id = mq.shop_id AND rs.category_name = mq.category_name AND mq.month_year = %s 
           WHERE rs.shop_id = %s ORDER BY rs.category_name""",
        (month_year, shop_id)
    )
    return {"stock": stock}

@router.get("/")
async def get_all_stock(user: dict = Depends(role_check(['admin']))):
    month_year = datetime.now().strftime('%Y-%m')
    stock = await execute_query(
        """SELECT rs.*, s.shop_name, s.shop_type, mq.allocated_qty, mq.sold_qty, (mq.allocated_qty - mq.sold_qty) as remaining_qty 
           FROM ration_stock rs LEFT JOIN shops s ON rs.shop_id = s.id 
           LEFT JOIN monthly_quota mq ON rs.shop_id = mq.shop_id AND rs.category_name = mq.category_name AND mq.month_year = %s 
           ORDER BY s.shop_name, rs.category_name""",
        (month_year,)
    )
    return {"stock": stock}

@router.get("/alerts/low")
async def get_low_stock_alerts(user: dict = Depends(role_check(['admin', 'shopkeeper']))):
    alerts = await execute_query(
        "SELECT rs.*, s.shop_name FROM ration_stock rs JOIN shops s ON rs.shop_id = s.id WHERE rs.quantity <= rs.min_threshold"
    )
    return {"alerts": alerts}

@router.post("/add")
async def add_stock(data: dict, user: dict = Depends(role_check(['admin']))):
    await execute_commit(
        "INSERT INTO ration_stock (shop_id, category_name, quantity, unit, min_threshold, price_per_unit) VALUES (%s, %s, %s, %s, %s, %s)",
        (data['shop_id'], data['category_name'], data['quantity'], data['unit'], data.get('min_threshold', 10), data.get('price_per_unit', 0))
    )
    return {"message": "Stock added successfully"}

@router.put("/update")
async def update_stock(data: dict, user: dict = Depends(role_check(['admin', 'shopkeeper']))):
    await execute_commit(
        "UPDATE ration_stock SET quantity = %s, min_threshold = %s, price_per_unit = %s WHERE shop_id = %s AND category_name = %s",
        (data['quantity'], data.get('min_threshold', 10), data.get('price_per_unit', 0), data['shop_id'], data['category_name'])
    )
    return {"message": "Stock updated successfully"}
