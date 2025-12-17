import asyncpg
from contextlib import asynccontextmanager
import os
from typing import Optional


class AsyncDatabase:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Инициализация пула соединений"""
        self.pool = await asyncpg.create_pool(
            host=os.getenv( 'DB_HOST', 'localhost' ),
            port=int( os.getenv( 'DB_PORT', 5432 ) ),
            user=os.getenv( 'DB_USER', 'postgres' ),
            password=os.getenv( 'DB_PASSWORD', '123456789' ),
            database=os.getenv( 'DB_NAME', 'postgres' ),
            min_size=5,
            max_size=20
        )

        # Создание таблиц
        async with self.pool.acquire() as conn:
            await conn.execute( """
                CREATE TABLE IF NOT EXISTS test_project.number_tb (
                    id SERIAL PRIMARY KEY,
                    person_id VARCHAR(45) NOT NULL,
                    good_number INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(person_id, good_number)
                );
            """ )

    async def close(self):
        """Закрытие пула соединений"""
        if self.pool:
            await self.pool.close()

    @asynccontextmanager
    async def get_connection(self):
        """Контекстный менеджер для получения соединения"""
        if not self.pool:
            raise RuntimeError( "Database not initialized" )

        async with self.pool.acquire() as conn:
            yield conn
