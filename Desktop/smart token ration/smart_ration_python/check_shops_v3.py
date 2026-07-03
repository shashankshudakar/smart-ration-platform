import asyncio
import os
import sys

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from app.database import init_db, execute_query, pool

async def main():
    try:
        await init_db()
        # Use a query that doesn't return much if empty
        shops = await execute_query("SELECT id, shop_name FROM shops")
        print(f"RESULT_SHOPS_COUNT: {len(shops)}")
        for s in shops:
            print(f"RESULT_SHOP: {s['id']} | {s['shop_name']}")
    except Exception as e:
        print(f"RESULT_ERROR: {str(e)}")
    finally:
        if pool:
            pool.close()
            await pool.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
