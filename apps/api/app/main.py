from pathlib import Path
from time import perf_counter
from uuid import uuid4

import jwt
import redis.asyncio as redis
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import metrics_middleware, metrics_response
from app.db.session import engine
from app.schemas.common import HealthResponse, ReadyResponse

configure_logging()
settings = get_settings()
logger = structlog.get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get('x-request-id', str(uuid4()))
        user_id = _user_id_from_request(request)
        start = perf_counter()
        structlog.contextvars.bind_contextvars(request_id=request_id, user_id=user_id)
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((perf_counter() - start) * 1000, 2)
            logger.exception(
                'http.request_failed',
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
                client_ip=_client_ip(request),
                user_agent=request.headers.get('user-agent'),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            structlog.contextvars.clear_contextvars()
            raise
        duration_ms = round((perf_counter() - start) * 1000, 2)
        response.headers['x-request-id'] = request_id
        logger.info(
            'http.request',
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=_client_ip(request),
            user_agent=request.headers.get('user-agent'),
        )
        structlog.contextvars.clear_contextvars()
        return response


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get('x-forwarded-for')
    if forwarded_for:
        return forwarded_for.split(',', 1)[0].strip()
    return request.client.host if request.client else None


def _user_id_from_request(request: Request) -> str | None:
    authorization = request.headers.get('authorization', '')
    if not authorization.lower().startswith('bearer '):
        return None
    token = authorization.split(' ', 1)[1].strip()
    try:
        payload = jwt.decode(token, options={'verify_signature': False})
    except jwt.PyJWTError:
        return None
    subject = payload.get('sub')
    return str(subject) if subject else None


app = FastAPI(title='Wenshi Server API', version='0.1.0')
app.add_middleware(RequestIdMiddleware)
app.middleware('http')(metrics_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(api_router)
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=settings.upload_dir), name='uploads')


@app.get('/', tags=['system'])
async def root():
    return {'service': settings.app_name, 'status': 'ok', 'docs': '/docs'}


@app.get('/health', response_model=HealthResponse, tags=['system'])
async def health():
    return HealthResponse(status='ok', service=settings.app_name, environment=settings.environment)


@app.get('/ready', response_model=ReadyResponse, tags=['system'])
async def ready():
    postgres_ok = False
    redis_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        postgres_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.warning('postgres_not_ready', error=str(exc))
    try:
        client = redis.from_url(settings.redis_url)
        redis_ok = bool(await client.ping())
        await client.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.warning('redis_not_ready', error=str(exc))
    return ReadyResponse(status='ready' if postgres_ok and redis_ok else 'degraded', postgres=postgres_ok, redis=redis_ok)


@app.get('/metrics', tags=['system'])
async def metrics():
    return metrics_response()
