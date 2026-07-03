import asyncio
from app.database import execute_query

async def main():
    try:
        print("SHOPKEEPERS SCHEMA:")
        res = await execute_query("DESCRIBE shopkeepers")
        for row in res: print(row)
        
        print("\nUSERS SCHEMA:")
        res = await execute_query("DESCRIBE users")
        for row in res: print(row)
        
        print("\nSAMPLE SHOPKEEPER:")
        res = await execute_query("SELECT id, owner_name, mobile FROM shopkeepers LIMIT 1")
        for row in res: print(row)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
