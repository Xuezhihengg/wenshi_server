from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from structlog import get_logger

from app.core.config import get_settings

logger = get_logger(__name__)


@dataclass(frozen=True)
class PhoneAuthResult:
    mobile: str
    request_id: str | None = None


class PhoneAuthProvider:
    async def get_mobile(self, access_token: str) -> PhoneAuthResult:
        raise NotImplementedError


class AliyunPhoneAuthProvider(PhoneAuthProvider):
    async def get_mobile(self, access_token: str) -> PhoneAuthResult:
        try:
            response = await self._get_mobile(access_token)
        except Exception as exc:
            logger.warning('aliyun_phone_auth_failed', error=str(exc))
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Phone auth provider unavailable') from exc

        body = getattr(response, 'body', None)
        response_code = getattr(body, 'code', None)
        request_id = getattr(body, 'request_id', None)
        result = getattr(body, 'get_mobile_result_dto', None)
        mobile = getattr(result, 'mobile', None)
        if response_code != 'OK' or not mobile:
            message = getattr(body, 'message', None) or 'Phone auth provider rejected request'
            logger.warning('aliyun_phone_auth_rejected', code=response_code, message=message, request_id=request_id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)

        return PhoneAuthResult(mobile=mobile, request_id=request_id)

    async def _get_mobile(self, access_token: str) -> Any:
        from alibabacloud_credentials.client import Client as CredentialClient
        from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
        from alibabacloud_dypnsapi20170525.client import Client as DypnsapiClient
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tea_util import models as util_models

        settings = get_settings()
        config = open_api_models.Config(credential=CredentialClient())
        config.endpoint = settings.aliyun_phone_auth_endpoint
        client = DypnsapiClient(config)
        request = dypnsapi_models.GetMobileRequest(access_token=access_token)
        return client.get_mobile_with_options(request, util_models.RuntimeOptions())


def get_phone_auth_provider() -> PhoneAuthProvider:
    return AliyunPhoneAuthProvider()
