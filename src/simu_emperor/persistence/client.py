# SeekDBClient - 统一的数据库客户端

"""

import logging

import aiomysql

from simu_emperor.mq.event import Event


logger = logging.getLogger(__name__)


class SeekDBClient:
    """SeekDB客户端"""
    
    def __init__(self, pool: aiomysql.Pool):
        self._pool = pool
    
    @classmethod
    async def create(
        cls,
        host: str = "localhost",
        port: int = 3306,
        user: str = "root",
        password: str = "root",
        db: str = "simu_emperor",
        minsize: int = 1,
        maxsize: int = 10,
        pool_recycle: int = 3600,
        autocommit: bool = True,
        charset: str = "utf8mb4",
    ) -> None:
        logger.info(f"SeekDBClient created: pool size {minsize}-{maxsize}")
        return cls(pool)
    
    async def execute(self, sql: str, *args) -> int:
        if not self._connected or not self._socket:
            raise RuntimeError("SeekDBClient not connected")
        
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, args)
                return cur.rowcount
    
    async def execute_many(self, sql: str, args_list: list[tuple]) -> int:
        if not self._connected or not self._socket:
            raise RuntimeError("SeekDBClient not connected")
        
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.executemany(sql, args_list)
                return cur.rowcount
    
    async def fetch_one(self, sql: str, *args) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, args)
                return await cur.fetchone()
    
    async def fetch_all(self, sql: str, *args) -> list[dict[str, Any]]:
        if not self._connected or not self._socket:
            raise RuntimeError("SeekDBClient not connected")
        
        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql, args)
                return await cur.fetchall()
    
    async def fetch_value(self, sql: str, *args) -> Any:
        if not self._connected or not self._socket:
            raise RuntimeError("SeekDBClient not connected")
        
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, args)
                row = await cur.fetchone()
                return row[0] if row else None
    
    async def transaction(self):
        return TransactionContext(self._pool)
    
    async def close(self) -> None:
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
        logger.info("SeekDBClient closed")


class TransactionContext:
    def __init__(self, pool: aiomysql.Pool):
        self._pool = pool
        self._conn: aiomysql.Connection | None = None
    
    async def __aenter__(self):
        self._conn = await self._pool.acquire()
        await self._conn.begin()
        return self
    
    async def __aexit__(self, exc_type, Any, exc_val: Any, exc_tb: Any) -> None:
        if not self._conn:
            return
        
        try:
            if exc_type:
                await self._conn.rollback()
                logger.warning("Transaction rolled back")
            else:
                await self._conn.commit()
                logger.debug("Transaction committed")
        finally:
            self._pool.release(self._conn)
            self._conn = None
    
    async def execute(self, sql: str, *args) -> int:
        if not self._conn:
            raise RuntimeError("Transaction not started")
        
        async with self._conn.cursor() as cur:
            await cur.execute(sql, args)
            return cur.rowcount
