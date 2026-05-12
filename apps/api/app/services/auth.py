import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.security import create_token, decode_token
from app.models import (
    AuthProvider,
    NotificationSetting,
    Profile,
    User,
    VerificationPurpose,
)
from app.providers.phone_auth import get_phone_auth_provider
from app.providers.verification import MOCK_CODE, get_verification_provider
from app.schemas.auth import (
    AppleLoginRequest,
    BindCodeRequest,
    BindWithCodeRequest,
    DeactivateAccountRequest,
    LoginWithCodeRequest,
    PhoneTokenLoginRequest,
    SendCodeRequest,
    TokenPair,
)
from app.services.audit import write_audit_log
from app.services.profiles import refresh_user_profile_completed
from app.services.verification_codes import (
    clear_verification_state,
    consume_verification_code,
    ensure_can_send_code,
    store_provider_managed_verification,
    store_verification_code,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _token_pair(user: User, is_new_user: bool = False) -> TokenPair:
    settings = get_settings()
    access = create_token(user.id, 'access', timedelta(minutes=settings.access_token_expire_minutes), {'is_admin': user.is_admin})
    refresh = create_token(user.id, 'refresh', timedelta(days=settings.refresh_token_expire_days))
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in_seconds=settings.access_token_expire_minutes * 60,
        is_new_user=is_new_user,
        profile_completed=user.profile_completed,
    )


async def ensure_default_profile(db: AsyncSession, user: User) -> None:
    existing = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if existing:
        return
    db.add(Profile(user_id=user.id, name='本人', relation='本人', gender='未填写', birthday='未填写', is_selected=True))
    db.add(NotificationSetting(user_id=user.id))


async def send_verification_code(db: AsyncSession, payload: SendCodeRequest):
    destination = payload.destination.strip()
    channel = AuthProvider(payload.channel)
    purpose = VerificationPurpose(payload.purpose)
    if purpose == VerificationPurpose.login:
        await ensure_login_destination_enabled(db, destination, AuthProvider(payload.channel))
    redis_client = get_redis()
    provider_managed = is_provider_managed_verification_channel(payload.channel)
    raw_code = MOCK_CODE if is_mock_verification_channel(payload.channel) else generate_verification_code()
    try:
        await ensure_can_send_code(redis_client, destination, channel.value, purpose.value)
        result = await get_verification_provider().send_code(destination, payload.channel, raw_code)
        if provider_managed:
            await store_provider_managed_verification(redis_client, destination, channel.value, purpose.value, verification_code_ttl_seconds(payload.channel))
        else:
            await store_verification_code(redis_client, destination, channel.value, purpose.value, raw_code, verification_code_ttl_seconds(payload.channel))
        return result
    except Exception:
        await clear_verification_state(redis_client, destination, channel.value, purpose.value)
        raise
    finally:
        await redis_client.aclose()


async def send_bind_verification_code(db: AsyncSession, user: User, payload: BindCodeRequest):
    destination = payload.destination.strip()
    channel = AuthProvider(payload.channel)
    await ensure_destination_bindable(db, user, destination, channel)
    bind_payload = SendCodeRequest(destination=destination, channel=payload.channel, purpose=VerificationPurpose.bind.value)
    return await send_verification_code(db, bind_payload)


async def login_with_code(db: AsyncSession, payload: LoginWithCodeRequest) -> TokenPair:
    destination = payload.destination.strip()
    redis_client = get_redis()
    try:
        provider_valid = await check_provider_managed_code(destination, payload.channel, payload.code)
        valid = await consume_verification_code(redis_client, destination, payload.channel, VerificationPurpose.login.value, payload.code, provider_valid)
    finally:
        await redis_client.aclose()
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid verification code')
    field = User.phone if payload.channel == 'phone' else User.email
    user = await db.scalar(select(User).where(field == destination))
    if user and user.disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Account is disabled')
    is_new_user = user is None
    if not user:
        kwargs = {'register_provider': AuthProvider(payload.channel)}
        if payload.channel == 'phone':
            kwargs['phone'] = destination
        else:
            kwargs['email'] = destination
        user = User(**kwargs)
        db.add(user)
        await db.flush()
        await ensure_default_profile(db, user)
    user.last_login_at = utc_now()
    await write_audit_log(db, user.id, 'auth.login', 'user', user.id, {'channel': payload.channel})
    await db.commit()
    await refresh_user_profile_completed(db, user)
    return _token_pair(user, is_new_user)


async def bind_with_code(db: AsyncSession, user: User, payload: BindWithCodeRequest) -> User:
    destination = payload.destination.strip()
    channel = AuthProvider(payload.channel)
    await ensure_destination_bindable(db, user, destination, channel)
    redis_client = get_redis()
    try:
        provider_valid = await check_provider_managed_code(destination, channel.value, payload.code)
        valid = await consume_verification_code(redis_client, destination, channel.value, VerificationPurpose.bind.value, payload.code, provider_valid)
    finally:
        await redis_client.aclose()
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid verification code')
    if channel == AuthProvider.phone:
        user.phone = destination
        action = 'auth.bind_phone'
    else:
        user.email = destination
        action = 'auth.bind_email'
    await write_audit_log(db, user.id, action, 'user', user.id, {'destination': destination})
    await db.commit()
    await db.refresh(user)
    return user


def generate_verification_code() -> str:
    return f'{secrets.randbelow(1_000_000):06d}'


def is_mock_verification_channel(channel: str) -> bool:
    settings = get_settings()
    if channel == 'email':
        return settings.email_verification_provider == 'mock'
    return settings.phone_verification_provider == 'mock'


def is_provider_managed_verification_channel(channel: str) -> bool:
    settings = get_settings()
    return channel == 'phone' and settings.phone_verification_provider == 'dypnsapi_sms'


async def check_provider_managed_code(destination: str, channel: str, code: str) -> bool | None:
    if not is_provider_managed_verification_channel(channel):
        return None
    return await get_verification_provider().check_code(destination, channel, code)


def verification_code_ttl_seconds(channel: str) -> int:
    settings = get_settings()
    if channel == 'email':
        return settings.email_verification_code_ttl_seconds
    return settings.phone_verification_code_ttl_seconds


async def ensure_login_destination_enabled(db: AsyncSession, destination: str, channel: AuthProvider) -> None:
    field = User.phone if channel == AuthProvider.phone else User.email
    user = await db.scalar(select(User).where(field == destination))
    if user and user.disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Account is disabled')


async def ensure_destination_bindable(db: AsyncSession, user: User, destination: str, channel: AuthProvider) -> None:
    field = User.phone if channel == AuthProvider.phone else User.email
    existing = await db.scalar(select(User).where(field == destination))
    if existing and existing.id != user.id:
        detail = '手机号已经被注册过了' if channel == AuthProvider.phone else '邮箱已经被注册过了'
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def login_with_apple(db: AsyncSession, payload: AppleLoginRequest) -> TokenPair:
    apple_claims = verify_apple_identity_token(payload.identity_token)
    apple_id = str(apple_claims.get('sub') or '')
    if not apple_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid Apple identity token')
    if payload.apple_id and payload.apple_id != apple_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Apple user does not match identity token')

    token_email = apple_claims.get('email')
    email = str(payload.email or token_email) if payload.email or token_email else None
    user = await db.scalar(select(User).where(User.apple_id == apple_id))
    if not user and email:
        user = await db.scalar(select(User).where(User.email == email))
        if user and not user.apple_id:
            user.apple_id = apple_id
    if user and user.disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Account is disabled')
    is_new_user = user is None
    if not user:
        user = User(apple_id=apple_id, email=email, display_name=payload.display_name or 'Apple 用户', register_provider=AuthProvider.apple)
        db.add(user)
        await db.flush()
        await ensure_default_profile(db, user)
    elif email and not user.email:
        user.email = email
    if payload.display_name and user.display_name == '问事用户':
        user.display_name = payload.display_name
    user.last_login_at = utc_now()
    await write_audit_log(db, user.id, 'auth.apple_login', 'user', user.id)
    await db.commit()
    await refresh_user_profile_completed(db, user)
    return _token_pair(user, is_new_user)


def verify_apple_identity_token(identity_token: str) -> dict:
    settings = get_settings()
    try:
        signing_key = jwt.PyJWKClient(settings.apple_jwks_url).get_signing_key_from_jwt(identity_token)
        return jwt.decode(
            identity_token,
            signing_key.key,
            algorithms=['RS256'],
            audience=settings.apple_client_id,
            issuer=settings.apple_issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid Apple identity token') from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unable to verify Apple identity token') from exc


async def login_with_phone_token(db: AsyncSession, payload: PhoneTokenLoginRequest) -> TokenPair:
    result = await get_phone_auth_provider().get_mobile(payload.access_token)
    user = await db.scalar(select(User).where(User.phone == result.mobile))
    if user and user.disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Account is disabled')
    if not user:
        user = User(phone=result.mobile, register_provider=AuthProvider.phone)
        db.add(user)
        await db.flush()
        await ensure_default_profile(db, user)
    user.last_login_at = utc_now()
    await write_audit_log(db, user.id, 'auth.phone_token_login', 'user', user.id, {'request_id': result.request_id})
    await db.commit()
    await refresh_user_profile_completed(db, user)
    return _token_pair(user)


async def refresh_token(db: AsyncSession, refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token, 'refresh')
    user = await db.get(User, payload['sub'])
    if not user or user.disabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid user')
    await refresh_user_profile_completed(db, user)
    return _token_pair(user)


async def deactivate_account(db: AsyncSession, user: User, payload: DeactivateAccountRequest) -> None:
    user.disabled = True
    await write_audit_log(
        db,
        user.id,
        'auth.deactivate_account',
        'user',
        user.id,
        {'reason': payload.reason.strip() if payload.reason else None},
    )
    await db.commit()


async def ensure_admin_user(db: AsyncSession) -> User:
    settings = get_settings()
    user = await db.scalar(select(User).where(User.email == settings.admin_username))
    if user:
        if not user.is_admin:
            user.is_admin = True
            await db.commit()
        return user
    user = User(email=settings.admin_username, display_name='Wenshi Admin', register_provider=AuthProvider.email, is_admin=True)
    db.add(user)
    await db.flush()
    await ensure_default_profile(db, user)
    await db.commit()
    return user


async def admin_login(db: AsyncSession, username: str, password: str) -> TokenPair:
    settings = get_settings()
    if username != settings.admin_username or password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid admin credentials')
    user = await ensure_admin_user(db)
    return _token_pair(user)
