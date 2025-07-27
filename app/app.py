from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import hashlib
import os
import time
import aiomysql
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "app"),
    "password": os.getenv("DB_PASSWORD", "app"),
    "database": os.getenv("DB_NAME", "o11y"),
}

pool = None  # глобальный пул подключений

class HashRequest(BaseModel):
    input: str
    algorithm: str = "sha256"

@app.on_event("startup")
async def startup_event():
    global pool
    pool = await aiomysql.create_pool(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        db=DB_CONFIG["database"],
        autocommit=True,
        maxsize=10,  # размер пула (настройте под нагрузку)
    )
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS hash_requests (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    input_text TEXT,
                    algorithm VARCHAR(50),
                    hash_result TEXT,
                    duration_ms FLOAT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

@app.on_event("shutdown")
async def shutdown_event():
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()

@app.post("/hash")
async def hash_string(req: HashRequest):
    if req.algorithm not in hashlib.algorithms_available:
        raise HTTPException(status_code=400, detail="Unsupported algorithm")

    start = time.time()
    h = hashlib.new(req.algorithm)
    h.update(req.input.encode("utf-8"))
    result = h.hexdigest()
    duration = (time.time() - start) * 1000

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO hash_requests (input_text, algorithm, hash_result, duration_ms) VALUES (%s, %s, %s, %s)",
                    (req.input, req.algorithm, result, duration)
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return {"hash": result, "duration_ms": round(duration, 2)}

@app.get("/docs")
def docs_redirect():
    return {"info": "POST /hash с input и algorithm. Метрики — /metrics"}
