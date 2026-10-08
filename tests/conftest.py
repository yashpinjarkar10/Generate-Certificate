"""
Pytest configuration and shared fixtures.
"""
from unittest.mock import AsyncMock
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db import connect_prisma, disconnect_prisma


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Ensure database connects once on session loop and disconnects on session exit."""
    await connect_prisma()
    yield
    await disconnect_prisma()


@pytest_asyncio.fixture
async def client():
    """Async test client with mocked Redis queue."""
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(return_value=True)
    app.state.redis_pool = mock_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
