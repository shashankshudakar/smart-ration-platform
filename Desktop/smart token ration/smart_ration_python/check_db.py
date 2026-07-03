import asyncio
import sys
import os

# Add the current directory to sys.path to import app
sys.path.append(os.getcwd())

from app.database import execute_query

async def main():
    try:
        print("--- SHOPS TABLE ---")
        shops = await execute_query("DESCRIBE shops")
        for col in shops:
            print(col)
            
        print("\n--- USERS TABLE ---")
        users = await execute_query("DESCRIBE users")
        for col in users:
            print(col)
            
        print("\n--- RATION STOCK TABLE ---")
        stock = await execute_query("DESCRIBE ration_stock")
        for col in stock:
            print(col)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
