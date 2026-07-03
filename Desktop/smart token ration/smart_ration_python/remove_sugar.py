import asyncio, os, sys
sys.path.append(os.getcwd())
from app.database import init_db, execute_query, execute_commit, pool

async def main():
    try:
        await init_db()
        # Delete sugar from ration_stock using parameterized LIKE
        await execute_commit("DELETE FROM ration_stock WHERE LOWER(category_name) LIKE %s", ('%sugar%',))
        print("Removed sugar from ration_stock")
        # Delete sugar from monthly_quota
        await execute_commit("DELETE FROM monthly_quota WHERE LOWER(category_name) LIKE %s", ('%sugar%',))
        print("Removed sugar from monthly_quota")
        # Verify
        remaining = await execute_query("SELECT DISTINCT category_name FROM ration_stock")
        print(f"Remaining categories: {[r['category_name'] for r in remaining]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if pool:
            pool.close()
            await pool.wait_closed()

asyncio.run(main())
