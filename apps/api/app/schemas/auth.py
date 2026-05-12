from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SendCodeRequest(BaseModel):
    destination: str = Field(min_length=3, max_length=255)
    channel: str = Field(pattern='^(phone|email)$')
    purpose: str = Field(default='login', pattern='^(login|bind)$')


class SendCodeResponse(BaseModel):
    message: str
    mock_code: str | None = None
    expires_in_seconds: int


class LoginWithCodeRequest(BaseModel):
    destination: str
    channel: str = Field(pattern='^(phone|email)$')
    code: str = Field(min_length=4, max_length=12)


class BindCodeRequest(BaseModel):
    destination: str = Field(min_length=3, max_length=255)
    channel: str = Field(pattern='^(phone|email)$')


class BindWithCodeRequest(BaseModel):
    destination: str = Field(min_length=3, max_length=255)
    channel: str = Field(pattern='^(phone|email)$')
    code: str = Field(min_length=4, max_length=12)


class PhoneTokenLoginRequest(BaseModel):
    access_token: str = Field(min_length=8, max_length=4096)


class AppleLoginRequest(BaseModel):
    apple_id: str | None = Field(default=None, min_length=1, max_length=255)
    identity_token: str = Field(min_length=20, max_length=4096)
    email: EmailStr | None = None
    display_name: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class DeactivateAccountRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    expires_in_seconds: int
    is_new_user: bool = False
    profile_completed: bool = False


class UserOut(BaseModel):
    id: str
    phone: str | None
    email: str | None
    apple_id: str | None
    wechat_id: str | None
    display_name: str
    avatar_url: str | None
    register_provider: str
    membership_plan: str
    membership_status: str
    profile_completed: bool
    created_at: datetime
    last_login_at: datetime | None
    is_admin: bool
