import json
from dataclasses import dataclass

from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.security import hash_password, verify_password


@dataclass(frozen=True)
class StoredVerificationCode:
    destination: str
    channel: str
    purpose: str
    code_hash: str | None = None
    provider_managed: bool = False


def _normalize_destination(destination: str) -> str:
    return destination.strip().lower()


def _key_part(value: str) -> str:
    return value.replace(':', '_')


def _code_key(destination: str, channel: str, purpose: str) -> str:
    return f'verification:code:{_key_part(purpose)}:{_key_part(channel)}:{_key_part(_normalize_destination(destination))}'


def _cooldown_key(destination: str, channel: str, purpose: str) -> str:
    return f'verification:cooldown:{_key_part(purpose)}:{_key_part(channel)}:{_key_part(_normalize_destination(destination))}'


def _attempts_key(destination: str, channel: str, purpose: str) -> str:
    return f'verification:attempts:{_key_part(purpose)}:{_key_part(channel)}:{_key_part(_normalize_destination(destination))}'


async def ensure_can_send_code(redis_client: Redis, destination: str, channel: str, purpose: str) -> None:
    settings = get_settings()
    created = await redis_client.set(
        _cooldown_key(destination, channel, purpose),
        '1',
        ex=settings.verification_code_cooldown_seconds,
        nx=True,
    )
    if not created:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Please wait before requesting another code')


async def store_verification_code(redis_client: Redis, destination: str, channel: str, purpose: str, raw_code: str, ttl_seconds: int) -> None:
    normalized_destination = _normalize_destination(destination)
    code_key = _code_key(normalized_destination, channel, purpose)
    attempts_key = _attempts_key(normalized_destination, channel, purpose)
    payload = {
        'destination': normalized_destination,
        'channel': channel,
        'purpose': purpose,
        'code_hash': hash_password(raw_code),
    }
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.set(code_key, json.dumps(payload, separators=(',', ':')), ex=ttl_seconds)
        pipe.delete(attempts_key)
        await pipe.execute()


async def store_provider_managed_verification(redis_client: Redis, destination: str, channel: str, purpose: str, ttl_seconds: int) -> None:
    normalized_destination = _normalize_destination(destination)
    code_key = _code_key(normalized_destination, channel, purpose)
    attempts_key = _attempts_key(normalized_destination, channel, purpose)
    payload = {
        'destination': normalized_destination,
        'channel': channel,
        'purpose': purpose,
        'provider_managed': True,
    }
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.set(code_key, json.dumps(payload, separators=(',', ':')), ex=ttl_seconds)
        pipe.delete(attempts_key)
        await pipe.execute()


async def consume_verification_code(redis_client: Redis, destination: str, channel: str, purpose: str, raw_code: str, provider_valid: bool | None = None) -> bool:
    settings = get_settings()
    normalized_destination = _normalize_destination(destination)
    code_key = _code_key(normalized_destination, channel, purpose)
    attempts_key = _attempts_key(normalized_destination, channel, purpose)
    raw_payload = await redis_client.get(code_key)
    if raw_payload is None:
        return False

    attempts = await redis_client.incr(attempts_key)
    ttl = await redis_client.ttl(code_key)
    if attempts == 1 and ttl > 0:
        await redis_client.expire(attempts_key, ttl)
    if attempts > settings.verification_code_max_attempts:
        await redis_client.delete(code_key, attempts_key)
        return False

    try:
        payload = json.loads(raw_payload)
        stored = StoredVerificationCode(
            destination=str(payload['destination']),
            channel=str(payload['channel']),
            purpose=str(payload['purpose']),
            code_hash=str(payload['code_hash']) if payload.get('code_hash') else None,
            provider_managed=bool(payload.get('provider_managed')),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        await redis_client.delete(code_key, attempts_key)
        return False

    if stored.destination != normalized_destination or stored.channel != channel or stored.purpose != purpose:
        return False
    if stored.provider_managed:
        valid = bool(provider_valid)
    elif stored.code_hash:
        valid = verify_password(raw_code, stored.code_hash)
    else:
        valid = False
    if not valid:
        return False

    await redis_client.delete(code_key, attempts_key)
    return True


async def clear_verification_state(redis_client: Redis, destination: str, channel: str, purpose: str) -> None:
    await redis_client.delete(
        _code_key(destination, channel, purpose),
        _cooldown_key(destination, channel, purpose),
        _attempts_key(destination, channel, purpose),
    )
