from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'wenshi-server'
    environment: str = 'development'
    api_host: str = '0.0.0.0'
    api_port: int = 8000
    database_url: str = 'postgresql+asyncpg://wenshi:wenshi@localhost:5432/wenshi'
    redis_url: str = 'redis://localhost:6379/0'
    log_dir: str = 'data/logs'
    log_file: str = 'api.log'
    log_level: str = 'INFO'
    log_max_bytes: int = 20 * 1024 * 1024
    log_backup_count: int = 10
    jwt_secret: str = 'dev-secret'
    jwt_issuer: str = 'wenshi-server'
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    admin_username: str = 'admin@wenshi.local'
    admin_password: str = 'admin123456'
    cors_origins: str = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174'
    phone_verification_provider: str = 'mock'
    email_verification_provider: str = 'mock'
    phone_verification_code_ttl_seconds: int = 600
    email_verification_code_ttl_seconds: int = 600
    verification_code_cooldown_seconds: int = 60
    verification_code_max_attempts: int = 5
    aliyun_sms_access_key_id: str | None = None
    aliyun_sms_access_key_secret: str | None = None
    aliyun_sms_endpoint: str = 'dysmsapi.aliyuncs.com'
    aliyun_sms_sign_name: str | None = None
    aliyun_sms_template_code: str | None = None
    aliyun_phone_auth_endpoint: str = 'dypnsapi.aliyuncs.com'
    aliyun_dm_access_key_id: str | None = None
    aliyun_dm_access_key_secret: str | None = None
    aliyun_dm_endpoint: str = 'dm.aliyuncs.com'
    aliyun_dm_account_name: str | None = None
    aliyun_dm_from_alias: str = '问事'
    aliyun_dm_reply_to_address: str = 'false'
    aliyun_dm_subject: str = '问事登录验证码'
    public_base_url: str = 'http://127.0.0.1:8000'
    upload_dir: str = 'data/uploads'
    max_avatar_upload_bytes: int = 5 * 1024 * 1024
    apple_client_id: str = 'com.anonymous.wenshi-app'
    apple_issuer: str = 'https://appleid.apple.com'
    apple_jwks_url: str = 'https://appleid.apple.com/auth/keys'
    llm_provider: str = 'nvidia'
    llm_api_key: str | None = None
    llm_base_url: str = 'https://integrate.api.nvidia.com/v1'
    llm_model: str = 'meta/llama-3.1-70b-instruct'
    llm_timeout_seconds: float = 30.0
    llm_response_format_json: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(',') if item.strip()]

    @property
    def log_path(self) -> Path:
        return Path(self.log_dir) / self.log_file


@lru_cache
def get_settings() -> Settings:
    return Settings()
