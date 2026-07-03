import asyncio
from app.database import execute_commit

async def main():
    try:
        await execute_commit("ALTER TABLE notifications ADD COLUMN target_role VARCHAR(20) DEFAULT NULL")
        print("Column added successfully")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
