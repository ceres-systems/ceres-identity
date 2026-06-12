from collections.abc import Awaitable
from contextlib import asynccontextmanager
from typing import cast

import uvicorn
from fastapi import FastAPI
from redis.asyncio import Redis

from app.config import settings
from app.db import engine, init_db_schema
from app.routers.auth import router as auth_router
from app.routers.internal import router as internal_router
from app.routers.well_known import router as well_known_router


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    redis: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    fastapi_app.state.redis = redis
    await cast(Awaitable[bool], redis.ping())
    try:
        if settings.db_create_tables:
            await init_db_schema()
        yield
    finally:
        await redis.aclose()
        await engine.dispose()


app = FastAPI(
    title="Ceres Identity",
    description="Console IAM: users, grants, and JWT issuance",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(internal_router)
app.include_router(well_known_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
