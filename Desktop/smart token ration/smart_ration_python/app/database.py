import aiomysql
from .config import settings

pool = None

async def init_db():
    global pool
    pool = await aiomysql.create_pool(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        db=settings.DB_NAME,
        autocommit=True,
        minsize=5,
        maxsize=20
    )
    print("MySQL Database connected successfully")

async def get_db():
    if pool is None:
        await init_db()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            yield cur

async def execute_query(query, params=None):
    if pool is None:
        await init_db()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, params or ())
            return await cur.fetchall()

async def execute_commit(query, params=None):
    if pool is None:
        await init_db()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, params or ())
            return cur.lastrowid
