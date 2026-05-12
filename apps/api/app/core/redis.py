import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.config import get_settings


def get_redis() -> Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)
