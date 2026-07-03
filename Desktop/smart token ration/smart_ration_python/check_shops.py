import asyncio
import os
import sys

# Add the current directory to sys.path to import app
sys.path.append(os.getcwd())

from app.database import execute_query

async def main():
    try:
        shops = await execute_query("SELECT * FROM shops")
        print(f"SHOPS_FOUND: {len(shops)}")
        for shop in shops:
            print(shop)
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
