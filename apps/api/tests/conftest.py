import os

os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://wenshi:wenshi@localhost:5432/wenshi_test')
os.environ.setdefault('ENVIRONMENT', 'test')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/15')
os.environ.setdefault('JWT_SECRET', 'test-secret-with-more-than-thirty-two-bytes')
os.environ.setdefault('ADMIN_USERNAME', 'admin@wenshi.local')
os.environ.setdefault('ADMIN_PASSWORD', 'test-admin-password')
os.environ['PHONE_VERIFICATION_PROVIDER'] = 'mock'
os.environ['EMAIL_VERIFICATION_PROVIDER'] = 'mock'

import pytest
import redis.asyncio as redis
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine, get_db
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
async def setup_db():
    redis_client = redis.from_url(os.environ['REDIS_URL'])
    await redis_client.flushdb()
    await redis_client.aclose()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    redis_client = redis.from_url(os.environ['REDIS_URL'])
    await redis_client.flushdb()
    await redis_client.aclose()


@pytest.fixture
async def client():
    async def override_get_db():
        async with AsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client: AsyncClient):
    code_response = await client.post('/api/v1/auth/code', json={'destination': '13800000000', 'channel': 'phone', 'purpose': 'login'})
    response = await client.post('/api/v1/auth/login/code', json={'destination': '13800000000', 'channel': 'phone', 'code': code_response.json()['mock_code']})
    token = response.json()['access_token']
    return {'Authorization': f'Bearer {token}'}
