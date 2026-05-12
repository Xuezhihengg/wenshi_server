from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from fastapi import HTTPException, status
from structlog import get_logger

from app.core.config import get_settings

logger = get_logger(__name__)


class LLMProvider(Protocol):
    async def create_json(self, messages: list[dict[str, str]], *, temperature: float = 0.2, max_tokens: int = 1200) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    response_format_json: bool


class OpenAICompatibleLLMProvider:
    def __init__(self, config: OpenAICompatibleConfig) -> None:
        self.config = config

    async def create_json(self, messages: list[dict[str, str]], *, temperature: float = 0.2, max_tokens: int = 1200) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'model': self.config.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        if self.config.response_format_json:
            payload['response_format'] = {'type': 'json_object'}
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.post(
                    self._chat_completions_url(),
                    headers={
                        'Authorization': f'Bearer {self.config.api_key}',
                        'Content-Type': 'application/json',
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                'llm_http_error',
                provider=self.config.provider,
                status_code=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='LLM request failed') from exc
        except httpx.HTTPError as exc:
            logger.warning('llm_unavailable', provider=self.config.provider, error=str(exc))
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='LLM provider unavailable') from exc

        content = data.get('choices', [{}])[0].get('message', {}).get('content')
        if not isinstance(content, str) or not content.strip():
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='LLM returned empty content')
        return _parse_json_content(content, self.config.provider)

    def _chat_completions_url(self) -> str:
        base_url = self.config.base_url.rstrip('/')
        if base_url.endswith('/chat/completions'):
            return base_url
        return f'{base_url}/chat/completions'


def _parse_json_content(content: str, provider: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, flags=re.DOTALL)
        candidate = fenced.group(1) if fenced else _extract_json_object(content)
        try:
            parsed = json.loads(candidate)
        except (TypeError, json.JSONDecodeError) as exc:
            logger.warning('llm_invalid_json', provider=provider, content=content[:500])
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='LLM returned invalid JSON') from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='LLM returned invalid JSON object')
    return parsed


def _extract_json_object(content: str) -> str | None:
    start = content.find('{')
    end = content.rfind('}')
    if start < 0 or end <= start:
        return None
    return content[start:end + 1]


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()
    if provider not in {'nvidia', 'openai_compatible', 'deepseek'}:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f'Unsupported LLM provider: {settings.llm_provider}')
    if not settings.llm_api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='LLM API key is not configured')
    if not settings.llm_model:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='LLM model is not configured')
    return OpenAICompatibleLLMProvider(
        OpenAICompatibleConfig(
            provider=provider,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            response_format_json=settings.llm_response_format_json,
        )
    )
