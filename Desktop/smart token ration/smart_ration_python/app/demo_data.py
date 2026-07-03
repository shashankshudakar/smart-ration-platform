from .database import execute_commit, execute_query
from .middleware.auth import hash_password


DEMO_PASSWORD = "demo123"
DEMO_ADMIN = {"username": "demo_admin", "name": "Demo Admin", "email": "demo.admin@smartration.local"}
DEMO_USER = {
    "name": "Demo Beneficiary",
    "mobile": "9000000001",
    "aadhaar_number": "100000000001",
    "ration_card_number": "DEMO-RC-001",
    "address": "Demo Street, Smart Ration City",
}
DEMO_SHOPKEEPER = {
    "owner_name": "Demo Shopkeeper",
    "mobile": "9000000002",
    "shop_name": "Demo Fair Price Shop",
    "address": "Demo Market, Smart Ration City",
}


async def _table_exists(table_name: str) -> bool:
    rows = await execute_query("SHOW TABLES LIKE %s", (table_name,))
    return bool(rows)


async def _columns_for(table_name: str) -> set[str]:
    rows = await execute_query(f"DESCRIBE {table_name}")
    return {row["Field"] for row in rows}


async def _insert_if_columns_exist(table_name: str, values: dict):
    columns = await _columns_for(table_name)
    filtered = {key: value for key, value in values.items() if key in columns}
    if not filtered:
        return None

    names = ", ".join(filtered.keys())
    placeholders = ", ".join(["%s"] * len(filtered))
    return await execute_commit(
        f"INSERT INTO {table_name} ({names}) VALUES ({placeholders})",
        tuple(filtered.values()),
    )


async def ensure_demo_accounts():
    hashed_password = hash_password(DEMO_PASSWORD)

    if await _table_exists("admins"):
        admins = await execute_query("SELECT id FROM admins WHERE username = %s", (DEMO_ADMIN["username"],))
        if not admins:
            await _insert_if_columns_exist(
                "admins",
                {**DEMO_ADMIN, "password": hashed_password},
            )

    users = await execute_query("SELECT id FROM users WHERE mobile = %s", (DEMO_USER["mobile"],))
    if not users:
        await execute_commit(
            """
            INSERT INTO users
                (name, mobile, aadhaar_number, ration_card_number, address, password, role, status)
            VALUES
                (%s, %s, %s, %s, %s, %s, 'user', 'approved')
            """,
            (
                DEMO_USER["name"],
                DEMO_USER["mobile"],
                DEMO_USER["aadhaar_number"],
                DEMO_USER["ration_card_number"],
                DEMO_USER["address"],
                hashed_password,
            ),
        )

    shops = await execute_query("SELECT id FROM shops WHERE shop_name = %s", (DEMO_SHOPKEEPER["shop_name"],))
    if shops:
        shop_id = shops[0]["id"]
    else:
        shop_id = await execute_commit(
            "INSERT INTO shops (shop_name, owner_name, address, shop_type, is_active) VALUES (%s, %s, %s, 'city', 1)",
            (
                DEMO_SHOPKEEPER["shop_name"],
                DEMO_SHOPKEEPER["owner_name"],
                DEMO_SHOPKEEPER["address"],
            ),
        )

    shopkeepers = []
    if await _table_exists("shopkeepers"):
        shopkeepers = await execute_query(
            "SELECT id FROM shopkeepers WHERE mobile = %s",
            (DEMO_SHOPKEEPER["mobile"],),
        )
    if not shopkeepers and await _table_exists("shopkeepers"):
        await _insert_if_columns_exist(
            "shopkeepers",
            {
                "owner_name": DEMO_SHOPKEEPER["owner_name"],
                "mobile": DEMO_SHOPKEEPER["mobile"],
                "shop_id": shop_id,
                "shop_name": DEMO_SHOPKEEPER["shop_name"],
                "address": DEMO_SHOPKEEPER["address"],
                "password": hashed_password,
                "status": "approved",
            },
        )

    shopkeeper_users = await execute_query("SELECT id FROM users WHERE mobile = %s", (DEMO_SHOPKEEPER["mobile"],))
    if not shopkeeper_users:
        await execute_commit(
            """
            INSERT INTO users
                (name, mobile, aadhaar_number, ration_card_number, address, password, role, status)
            VALUES
                (%s, %s, %s, %s, %s, %s, 'shopkeeper', 'approved')
            """,
            (
                DEMO_SHOPKEEPER["owner_name"],
                DEMO_SHOPKEEPER["mobile"],
                "100000000002",
                "DEMO-RC-002",
                DEMO_SHOPKEEPER["address"],
                hashed_password,
            ),
        )
