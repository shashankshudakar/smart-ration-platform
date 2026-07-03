import asyncio
import sys
import os
sys.path.append(os.getcwd())
from app.database import execute_query

async def main():
    try:
        tables = await execute_query("SHOW TABLES")
        print("Tables in DB:", tables)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
