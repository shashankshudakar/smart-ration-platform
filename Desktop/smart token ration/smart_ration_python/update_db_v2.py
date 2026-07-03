import asyncio
from app.database import execute_commit

async def main():
    try:
        await execute_commit("ALTER TABLE notifications ADD COLUMN sender_id INT DEFAULT NULL")
        print("Column sender_id added successfully")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
