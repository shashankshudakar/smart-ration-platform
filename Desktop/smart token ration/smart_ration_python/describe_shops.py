import asyncio, os, sys
sys.path.append(os.getcwd())
from app.database import init_db, execute_query, pool

async def main():
    try:
        await init_db()
        cols = await execute_query("DESCRIBE shops")
        for c in cols:
            print(f"COL: {c['Field']} | {c['Type']}")
    except Exception as e:
        print(f"ERR: {e}")
    finally:
        if pool:
            pool.close()
            await pool.wait_closed()

asyncio.run(main())
