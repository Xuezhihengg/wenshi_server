import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter('wenshi_http_requests_total', 'Total HTTP requests', ['method', 'path', 'status'])
REQUEST_LATENCY = Histogram('wenshi_http_request_duration_seconds', 'HTTP request latency', ['method', 'path'])


async def metrics_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    path = request.scope.get('route').path if request.scope.get('route') else request.url.path
    REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
    return response


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
