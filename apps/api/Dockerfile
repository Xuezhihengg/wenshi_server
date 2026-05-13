FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_TRUSTED_HOST=mirrors.aliyun.com
ENV PIP_INDEX_URL=$PIP_INDEX_URL \
    PIP_TRUSTED_HOST=$PIP_TRUSTED_HOST \
    UV_INDEX_URL=$PIP_INDEX_URL \
    UV_NATIVE_TLS=true
RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md ./
RUN uv pip install --system ".[dev]"
COPY apps ./apps
WORKDIR /app
