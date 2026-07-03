import asyncio
import sys
import os
sys.path.append(os.getcwd())
from app.database import execute_query

async def main():
    try:
        res = await execute_query("DESCRIBE tokens")
        for col in res:
            print(col)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
