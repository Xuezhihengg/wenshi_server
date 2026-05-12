# Wenshi Server

FastAPI + PostgreSQL + Redis + React/Vite admin backend for Wenshi.

## Local development

```bash
uv sync --extra dev
cp .env.example .env
uv run alembic -c apps/api/alembic.ini upgrade head
uv run uvicorn app.main:app --app-dir apps/api --reload
```

Admin web:

```bash
cd admin-web
npm install
npm run dev
```

Portal web:

```bash
cd ../wenshi-portal
npm install
npm run dev
```

Docker Compose:

```bash
docker compose up --build
```

## Production deployment

```bash
cp .env.example .env
# Edit .env: set strong POSTGRES_PASSWORD, JWT_SECRET, LLM_API_KEY,
# Aliyun keys, APPLE_CLIENT_ID, PUBLIC_BASE_URL=https://your.domain, CORS_ORIGINS=https://your.domain

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The production compose:

- only the nginx container is exposed to the host (port 80, optionally 443)
- postgres / redis / api / worker have no host ports
- admin-web and portal-web run as static nginx servers
- containers `restart: unless-stopped`

### TLS

First point `wenshi.xin` and `www.wenshi.xin` to the ECS public IP, then start
the stack on HTTP:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Issue Let's Encrypt certificates:

```bash
CERTBOT_EMAIL=you@example.com DOMAIN=wenshi.xin ./infra/scripts/issue_cert.sh
```

The script stores certificates under `infra/nginx/certs`, switches nginx to
`infra/nginx/nginx.https.conf`, and restarts nginx.

Renew certificates manually:

```bash
./infra/scripts/renew_cert.sh
```

Schedule renewal on the ECS host:

```cron
15 4 * * * cd /opt/wenshi/wenshi-server && ./infra/scripts/renew_cert.sh >> /var/log/wenshi-certbot.log 2>&1
```

Aliyun ECS security group must allow inbound TCP `80` and `443`.

### Database backup

One-shot dump:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup
```

Schedule daily on the host:

```cron
0 3 * * * cd /opt/wenshi-server && docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup
```

Backups land in the `backup_data` volume and are pruned after 14 days.

Default mock admin account:

- username: `admin@wenshi.local`
- password: `admin123456`

## Verification providers

Phone and email verification can be configured independently.

```env
# Phone: mock | aliyun_sms | dypnsapi_sms
PHONE_VERIFICATION_PROVIDER=dypnsapi_sms
PHONE_VERIFICATION_CODE_TTL_SECONDS=600
VERIFICATION_CODE_COOLDOWN_SECONDS=60
VERIFICATION_CODE_MAX_ATTEMPTS=5

# Email: mock | aliyun_dm
EMAIL_VERIFICATION_PROVIDER=aliyun_dm
EMAIL_VERIFICATION_CODE_TTL_SECONDS=600
ALIYUN_DM_ACCESS_KEY_ID=your-access-key-id
ALIYUN_DM_ACCESS_KEY_SECRET=your-access-key-secret
ALIYUN_DM_ACCOUNT_NAME=noreply@example.com
ALIYUN_DM_FROM_ALIAS=问事
ALIYUN_DM_SUBJECT=问事登录验证码
```

`ALIYUN_DM_ACCOUNT_NAME` must be a sender address already created and verified in Aliyun DirectMail.
Verification codes are stored in Redis with TTL and are deleted after successful verification.

## Logging

API logs are structured JSON and are written to stdout and rotating files.

```env
LOG_DIR=data/logs
LOG_FILE=api.log
LOG_LEVEL=INFO
LOG_MAX_BYTES=20971520
LOG_BACKUP_COUNT=10
```

Admin users can query recent logs from the admin web or `GET /api/v1/admin/logs`.

## Apple Sign In

The API verifies Apple `identity_token` against Apple's JWKS before logging in. `APPLE_CLIENT_ID` must match the iOS Bundle ID configured for the app.

```env
APPLE_CLIENT_ID=com.anonymous.wenshi-app
APPLE_ISSUER=https://appleid.apple.com
APPLE_JWKS_URL=https://appleid.apple.com/auth/keys
```

## AI readings

AI readings use a generic OpenAI-compatible LLM adapter. The default provider is NVIDIA API Catalog / NIM.

```env
LLM_PROVIDER=nvidia
LLM_API_KEY=your-nvidia-api-key
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=meta/llama-3.1-70b-instruct
LLM_TIMEOUT_SECONDS=30
LLM_RESPONSE_FORMAT_JSON=true
```

For another OpenAI-compatible provider later, set `LLM_PROVIDER=openai_compatible`, change `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`.

## Uploads

Avatar uploads are stored under `UPLOAD_DIR` and served from `/uploads`.

```env
PUBLIC_BASE_URL=http://127.0.0.1:8000
UPLOAD_DIR=data/uploads
MAX_AVATAR_UPLOAD_BYTES=5242880
```

When testing on iPhone over LAN, set `PUBLIC_BASE_URL` to your Mac LAN URL, for example `http://172.20.10.12:8000`, so uploaded avatar URLs are reachable from the device.

## Checks

Tests use PostgreSQL only. Create the local test database once before running pytest:

```bash
createdb -O wenshi wenshi_test
uv run pytest
uv run ruff check
```
