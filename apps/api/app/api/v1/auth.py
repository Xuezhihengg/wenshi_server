from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import (
    AppleLoginRequest,
    BindCodeRequest,
    BindWithCodeRequest,
    DeactivateAccountRequest,
    GoogleLoginRequest,
    LoginWithCodeRequest,
    PhoneTokenLoginRequest,
    RefreshTokenRequest,
    SendCodeRequest,
    SendCodeResponse,
    TokenPair,
    UserOut,
)
from app.services.auth import (
    bind_with_code,
    deactivate_account,
    login_with_apple,
    login_with_code,
    login_with_google,
    login_with_phone_token,
    refresh_token,
    send_bind_verification_code,
    send_verification_code,
    verification_code_ttl_seconds,
)
from app.services.profiles import refresh_user_profile_completed

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/code', response_model=SendCodeResponse)
async def send_code(payload: SendCodeRequest, db: DbSession):
    result = await send_verification_code(db, payload)
    return SendCodeResponse(
        message='Verification code sent',
        mock_code=result.mock_code,
        expires_in_seconds=verification_code_ttl_seconds(payload.channel),
    )


@router.post('/login/code', response_model=TokenPair)
async def code_login(payload: LoginWithCodeRequest, db: DbSession):
    return await login_with_code(db, payload)


@router.post('/bind/code', response_model=SendCodeResponse)
async def send_bind_code(payload: BindCodeRequest, user: CurrentUser, db: DbSession):
    result = await send_bind_verification_code(db, user, payload)
    return SendCodeResponse(
        message='Verification code sent',
        mock_code=result.mock_code,
        expires_in_seconds=verification_code_ttl_seconds(payload.channel),
    )


@router.post('/bind', response_model=UserOut)
async def bind_account(payload: BindWithCodeRequest, user: CurrentUser, db: DbSession):
    return await bind_with_code(db, user, payload)


@router.post('/login/apple', response_model=TokenPair)
async def apple_login(payload: AppleLoginRequest, db: DbSession):
    return await login_with_apple(db, payload)


@router.post('/login/google', response_model=TokenPair)
async def google_login(payload: GoogleLoginRequest, db: DbSession):
    return await login_with_google(db, payload)


@router.post('/login/phone-token', response_model=TokenPair)
async def phone_token_login(payload: PhoneTokenLoginRequest, db: DbSession):
    return await login_with_phone_token(db, payload)


@router.post('/refresh', response_model=TokenPair)
async def refresh(payload: RefreshTokenRequest, db: DbSession):
    return await refresh_token(db, payload.refresh_token)


@router.post('/logout')
async def logout(_: CurrentUser):
    return {'message': 'Logged out'}


@router.post('/deactivate')
async def deactivate(payload: DeactivateAccountRequest, user: CurrentUser, db: DbSession):
    await deactivate_account(db, user, payload)
    return {'message': 'Account deactivated'}


@router.get('/me', response_model=UserOut)
async def me(user: CurrentUser, db: DbSession):
    await refresh_user_profile_completed(db, user)
    return user
