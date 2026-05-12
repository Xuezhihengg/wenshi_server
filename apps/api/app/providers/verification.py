import json
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from structlog import get_logger

from app.core.config import get_settings

MOCK_CODE = '123456'
logger = get_logger(__name__)


@dataclass(frozen=True)
class VerificationDeliveryResult:
    destination: str
    channel: str
    provider: str
    mock_code: str | None = None
    request_id: str | None = None


class VerificationProvider:
    async def send_code(self, destination: str, channel: str, code: str) -> VerificationDeliveryResult:
        raise NotImplementedError

    async def check_code(self, destination: str, channel: str, code: str) -> bool:
        raise NotImplementedError


class MockVerificationProvider(VerificationProvider):
    async def send_code(self, destination: str, channel: str, code: str) -> VerificationDeliveryResult:
        return VerificationDeliveryResult(destination=destination, channel=channel, provider='mock', mock_code=code)

    async def check_code(self, destination: str, channel: str, code: str) -> bool:
        return code == MOCK_CODE


class AliyunSmsVerificationProvider(VerificationProvider):
    def __init__(self) -> None:
        settings = get_settings()
        missing = [
            name
            for name, value in {
                'ALIYUN_SMS_ACCESS_KEY_ID': settings.aliyun_sms_access_key_id,
                'ALIYUN_SMS_ACCESS_KEY_SECRET': settings.aliyun_sms_access_key_secret,
                'ALIYUN_SMS_SIGN_NAME': settings.aliyun_sms_sign_name,
                'ALIYUN_SMS_TEMPLATE_CODE': settings.aliyun_sms_template_code,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f'Missing Aliyun SMS settings: {", ".join(missing)}')

    async def send_code(self, destination: str, channel: str, code: str) -> VerificationDeliveryResult:
        if channel != 'phone':
            return await MockVerificationProvider().send_code(destination, channel, code)

        try:
            response = await self._send_sms(destination, code)
        except Exception as exc:
            logger.warning('aliyun_sms_send_failed', destination=destination, error=str(exc))
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='SMS provider unavailable') from exc

        body = getattr(response, 'body', None)
        response_code = getattr(body, 'code', None)
        request_id = getattr(body, 'request_id', None)
        if response_code != 'OK':
            message = getattr(body, 'message', None) or 'SMS provider rejected request'
            logger.warning('aliyun_sms_rejected', destination=destination, code=response_code, message=message, request_id=request_id)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message)

        return VerificationDeliveryResult(destination=destination, channel=channel, provider='aliyun_sms', request_id=request_id)

    async def _send_sms(self, phone: str, code: str) -> Any:
        from alibabacloud_dysmsapi20170525 import models as dysmsapi_models
        from alibabacloud_dysmsapi20170525.client import Client as DysmsapiClient
        from alibabacloud_tea_openapi import models as open_api_models

        settings = get_settings()
        config = open_api_models.Config(
            access_key_id=settings.aliyun_sms_access_key_id,
            access_key_secret=settings.aliyun_sms_access_key_secret,
            endpoint=settings.aliyun_sms_endpoint,
        )
        client = DysmsapiClient(config)
        request = dysmsapi_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=settings.aliyun_sms_sign_name,
            template_code=settings.aliyun_sms_template_code,
            template_param=f'{{"code":"{code}"}}',
        )
        return client.send_sms(request)

    async def check_code(self, destination: str, channel: str, code: str) -> bool:
        return True


class AliyunDypnsSmsVerificationProvider(VerificationProvider):
    async def send_code(self, destination: str, channel: str, code: str) -> VerificationDeliveryResult:
        if channel != 'phone':
            return await MockVerificationProvider().send_code(destination, channel, code)

        try:
            response = await self._send_sms_verify_code(destination)
        except Exception as exc:
            logger.warning('dypns_sms_send_failed', destination=destination, error=str(exc))
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='SMS provider unavailable') from exc

        body = getattr(response, 'body', None)
        success = bool(getattr(body, 'success', False))
        request_id = getattr(body, 'request_id', None)
        if not success:
            message = getattr(body, 'message', None) or 'SMS provider rejected request'
            logger.warning('dypns_sms_rejected', destination=destination, code=getattr(body, 'code', None), message=message, request_id=request_id)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=message)

        return VerificationDeliveryResult(destination=destination, channel=channel, provider='dypns_sms', request_id=request_id)

    async def check_code(self, destination: str, channel: str, code: str) -> bool:
        if channel != 'phone':
            return await MockVerificationProvider().check_code(destination, channel, code)

        try:
            response = await self._check_sms_verify_code(destination, code)
        except Exception as exc:
            logger.warning('dypns_sms_check_failed', destination=destination, error=str(exc))
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='SMS provider unavailable') from exc

        body = getattr(response, 'body', None)
        model = getattr(body, 'model', None)
        verify_result = getattr(model, 'verify_result', None)
        success = bool(getattr(body, 'success', False))
        return success and str(verify_result).lower() in {'true', 'pass', 'success', 'ok', '1'}

    async def _send_sms_verify_code(self, phone: str) -> Any:
        from alibabacloud_credentials.client import Client as CredentialClient
        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_dypnsapi20170525.client import Client as DypnsapiClient
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tea_util import models as util_models

        settings = get_settings()
        config = open_api_models.Config(credential=CredentialClient())
        config.endpoint = settings.aliyun_phone_auth_endpoint
        client = DypnsapiClient(config)
        request = dypnsapi_models.SendSmsVerifyCodeRequest(
            phone_number=phone,
            sign_name=settings.aliyun_sms_sign_name,
            template_code=settings.aliyun_sms_template_code,
            template_param=json.dumps(
                {'code': '##code##', 'min': str(max(1, settings.phone_verification_code_ttl_seconds // 60))},
                separators=(',', ':'),
            ),
            code_length=6,
            code_type=1,
            valid_time=settings.phone_verification_code_ttl_seconds,
            interval=60,
            duplicate_policy=1,
            return_verify_code=False,
        )
        return client.send_sms_verify_code_with_options(request, util_models.RuntimeOptions())

    async def _check_sms_verify_code(self, phone: str, code: str) -> Any:
        from alibabacloud_credentials.client import Client as CredentialClient
        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_dypnsapi20170525.client import Client as DypnsapiClient
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tea_util import models as util_models

        settings = get_settings()
        config = open_api_models.Config(credential=CredentialClient())
        config.endpoint = settings.aliyun_phone_auth_endpoint
        client = DypnsapiClient(config)
        request = dypnsapi_models.CheckSmsVerifyCodeRequest(
            phone_number=phone,
            verify_code=code,
        )
        return client.check_sms_verify_code_with_options(request, util_models.RuntimeOptions())


class AliyunDmEmailVerificationProvider(VerificationProvider):
    def __init__(self) -> None:
        settings = get_settings()
        missing = [
            name
            for name, value in {
                'ALIYUN_DM_ACCESS_KEY_ID': settings.aliyun_dm_access_key_id,
                'ALIYUN_DM_ACCESS_KEY_SECRET': settings.aliyun_dm_access_key_secret,
                'ALIYUN_DM_ACCOUNT_NAME': settings.aliyun_dm_account_name,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f'Missing Aliyun DM settings: {", ".join(missing)}')

    async def send_code(self, destination: str, channel: str, code: str) -> VerificationDeliveryResult:
        if channel != 'email':
            return await MockVerificationProvider().send_code(destination, channel, code)

        try:
            response = await self._send_mail(destination, code)
        except Exception as exc:
            logger.warning('aliyun_dm_send_failed', destination=destination, error=str(exc))
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Email provider unavailable') from exc

        body = getattr(response, 'body', None)
        request_id = getattr(body, 'request_id', None)
        env_id = getattr(body, 'env_id', None)
        if not request_id and not env_id:
            logger.warning('aliyun_dm_empty_response', destination=destination, response=str(response))

        return VerificationDeliveryResult(destination=destination, channel=channel, provider='aliyun_dm', request_id=request_id or env_id)

    async def _send_mail(self, email: str, code: str) -> Any:
        from alibabacloud_dm20151123 import models as dm_models
        from alibabacloud_dm20151123.client import Client as DmClient
        from alibabacloud_tea_openapi import models as open_api_models

        settings = get_settings()
        minutes = max(1, settings.email_verification_code_ttl_seconds // 60)
        html_body = (
            '<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;line-height:1.7;color:#1f2933;">'
            '<h2 style="margin:0 0 12px;">问事登录验证码</h2>'
            f'<p>你的验证码是：</p><p style="font-size:28px;font-weight:800;letter-spacing:4px;margin:8px 0;">{code}</p>'
            f'<p>验证码 {minutes} 分钟内有效。如非本人操作，请忽略此邮件。</p>'
            '</div>'
        )
        text_body = f'你的问事登录验证码是：{code}。验证码 {minutes} 分钟内有效。如非本人操作，请忽略此邮件。'
        config = open_api_models.Config(
            access_key_id=settings.aliyun_dm_access_key_id,
            access_key_secret=settings.aliyun_dm_access_key_secret,
            endpoint=settings.aliyun_dm_endpoint,
        )
        client = DmClient(config)
        request = dm_models.SingleSendMailRequest(
            account_name=settings.aliyun_dm_account_name,
            address_type=1,
            reply_to_address=settings.aliyun_dm_reply_to_address,
            to_address=email,
            subject=settings.aliyun_dm_subject,
            html_body=html_body,
            text_body=text_body,
            from_alias=settings.aliyun_dm_from_alias,
        )
        return client.single_send_mail(request)

    async def check_code(self, destination: str, channel: str, code: str) -> bool:
        return True


class ChannelVerificationProvider(VerificationProvider):
    def __init__(self, phone_provider: VerificationProvider, email_provider: VerificationProvider) -> None:
        self.phone_provider = phone_provider
        self.email_provider = email_provider

    async def send_code(self, destination: str, channel: str, code: str) -> VerificationDeliveryResult:
        if channel == 'email':
            return await self.email_provider.send_code(destination, channel, code)
        return await self.phone_provider.send_code(destination, channel, code)

    async def check_code(self, destination: str, channel: str, code: str) -> bool:
        if channel == 'email':
            return await self.email_provider.check_code(destination, channel, code)
        return await self.phone_provider.check_code(destination, channel, code)


def get_phone_verification_provider() -> VerificationProvider:
    settings = get_settings()
    if settings.phone_verification_provider == 'dypnsapi_sms':
        return AliyunDypnsSmsVerificationProvider()
    if settings.phone_verification_provider == 'aliyun_sms':
        return AliyunSmsVerificationProvider()
    return MockVerificationProvider()


def get_email_verification_provider() -> VerificationProvider:
    settings = get_settings()
    if settings.email_verification_provider == 'aliyun_dm':
        return AliyunDmEmailVerificationProvider()
    return MockVerificationProvider()


def get_verification_provider() -> VerificationProvider:
    return ChannelVerificationProvider(get_phone_verification_provider(), get_email_verification_provider())
