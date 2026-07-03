import asyncio
from app.database import execute_commit

async def main():
    try:
        # First find the constraint name
        # The error said it was notifications_ibfk_1
        await execute_commit("ALTER TABLE notifications DROP FOREIGN KEY notifications_ibfk_1")
        print("Foreign key constraint removed successfully")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
