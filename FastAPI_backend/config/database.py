import os
import asyncpg
from contextlib import asynccontextmanager
from typing import AsyncGenerator

DB_URL = os.getenv("DB_URL", "postgresql://postgres:yesyes123@localhost:5432/Wihwin")

pool: asyncpg.Pool = None


async def init_pool():
    global pool
    pool = await asyncpg.create_pool(
        DB_URL, min_size=2, max_size=20
    )


async def close_pool():
    global pool
    if pool:
        await pool.close()


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator:
    async with pool.acquire() as conn:
        yield conn


async def test_connection() -> bool:
    try:
        async with get_db_connection() as conn:
            await conn.fetchval("SELECT 1")
            return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
