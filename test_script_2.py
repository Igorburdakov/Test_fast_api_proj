from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
import asyncpg
import os
import logging

logging.basicConfig( level=logging.INFO )
logger = logging.getLogger( __name__ )


class NumberRequest( BaseModel ):
    number: int = Field( ..., ge=0, description="Non-negative integer" )


DB_CONFIG = {
    "host": os.getenv( "DB_HOST", "localhost" ),
    "port": int( os.getenv( "DB_PORT", 5432 ) ),
    "user": os.getenv( "DB_USER", "postgres" ),
    "password": os.getenv( "DB_PASSWORD", "123456789" ),
    "database": os.getenv( "DB_NAME", "postgres" ),
    "min_size": 5,
    "max_size": 20
}


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool( **DB_CONFIG )
        logger.info( "Database connected" )

        async with self.pool.acquire() as conn:
            await conn.execute( """
                CREATE SCHEMA IF NOT EXISTS test_project;
                CREATE TABLE IF NOT EXISTS test_project.number_tb (
                    person_id varchar(20) not null,
                    good_number int8 not null,
                    UNIQUE(person_id, good_number)
                );
            """ )

    async def close(self):
        if self.pool:
            await self.pool.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.close()


app = FastAPI( lifespan=lifespan )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database()


@app.post( "/api/process" )
async def process_number(request_data: NumberRequest, request: Request):
    user_ip = request.client.host
    number = request_data.number

    logger.info( f"Processing number {number} from IP {user_ip}" )

    async with db.pool.acquire() as conn:
        # Проверка существования числа
        exists = await conn.fetchval( """
            SELECT EXISTS (
                SELECT 1 FROM test_project.number_tb 
                WHERE person_id = $1 AND good_number = $2
            )
        """, user_ip, number )

        if exists:
            raise HTTPException(
                status_code=412,
                detail={"error": "Number already exists"}
            )

        # Проверка существования number + 1
        exists_next = await conn.fetchval( """
            SELECT EXISTS (
                SELECT 1 FROM test_project.number_tb 
                WHERE person_id = $1 AND good_number = $2
            )
        """, user_ip, number + 1 )

        if exists_next:
            raise HTTPException(
                status_code=412,
                detail={"error": "Number + 1 already exists"}
            )

        # Добавление числа
        try:
            await conn.execute( """
                INSERT INTO test_project.number_tb (person_id, good_number)
                VALUES ($1, $2)
            """, user_ip, number )
        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=412,
                detail={"error": "Number already exists (concurrent request)"}
            )

    # Успешный ответ
    return {
        "user_ip": user_ip,
        "number": number,
        "result": number + 1
    }


@app.get( "/health" )
async def health_check():
    try:
        async with db.pool.acquire() as conn:
            await conn.fetchval( "SELECT 1" )
        return {"status": "healthy"}
    except Exception:
        raise HTTPException( status_code=503, detail={"error": "Database unavailable"} )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend:app",
        host="0.0.0.0",
        port=5001,
        reload=True,
        log_level="info"
    )