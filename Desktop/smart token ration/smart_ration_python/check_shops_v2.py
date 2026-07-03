import asyncio
import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from app.database import init_db, execute_query, pool
from app.config import settings

async def main():
    logger.info(f"Connecting to DB: {settings.DB_HOST}:{settings.DB_PORT} as {settings.DB_USER}")
    logger.info(f"DB Name: {settings.DB_NAME}")
    
    try:
        await init_db()
        logger.info("Database connection initialized successfully")
        
        # Check if table exists
        tables = await execute_query("SHOW TABLES LIKE 'shops'")
        if not tables:
            logger.error("Table 'shops' DOES NOT EXIST!")
            return

        shops = await execute_query("SELECT * FROM shops")
        logger.info(f"SHOPS_COUNT: {len(shops)}")
        for shop in shops:
            print(f"SHOP: {shop}")
            
    except Exception as e:
        logger.error(f"DATABASE ERROR: {e}")
    finally:
        if pool:
            pool.close()
            await pool.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
