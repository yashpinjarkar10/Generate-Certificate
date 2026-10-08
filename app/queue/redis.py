# Redis/ARQ connection module
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

load_dotenv()


def get_redis_settings() -> RedisSettings:
    """Build Redis settings supporting REDIS_URL or individual host/port configs.

    Supported env vars:
        REDIS_URL         e.g. rediss://default:token@fun-heron-209055.upstash.io:6379
        REDIS_HOST        Fallback host (default: localhost)
        REDIS_PORT        Fallback port (default: 6379)
        REDIS_PASSWORD    Fallback password
        REDIS_USE_SSL     Force TLS (true/false)
    """
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return RedisSettings.from_dsn(redis_url)

    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    database = int(os.getenv("REDIS_DATABASE", "0"))
    username = os.getenv("REDIS_USERNAME", "default")
    password = os.getenv("REDIS_PASSWORD")

    # Smart SSL detection
    ssl_env = os.getenv("REDIS_USE_SSL")
    if ssl_env is not None:
        use_ssl = ssl_env.lower() in ("true", "1", "yes")
    else:
        use_ssl = "upstash.io" in host

    return RedisSettings(
        host=host,
        port=port,
        database=database,
        username=username if password else None,
        password=password if password else None,
        ssl=use_ssl,
    )


@asynccontextmanager
async def create_redis_pool(app: FastAPI):
    """Create and manage ARQ Redis pool during application lifespan."""
    settings = get_redis_settings()
    pool = await create_pool(settings)
    app.state.redis_pool = pool
    yield
    await pool.close()


def get_redis_pool(request: Request) -> ArqRedis:
    """Dependency injection helper to retrieve Redis pool from app state."""
    return request.app.state.redis_pool