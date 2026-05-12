FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md ./
RUN uv pip install --system ".[dev]"
COPY apps ./apps
WORKDIR /app
