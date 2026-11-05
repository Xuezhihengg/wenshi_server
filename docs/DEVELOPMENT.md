# Development Guide

This guide covers local development for the Wenshi backend, admin console and the related web/mobile clients.

## Repository layout

The project is split across three repositories. Clone them into the same parent directory when running the full stack:

```text
~/code/
├── wenshi-app
├── wenshi-server
└── wenshi-portal
```

## Prerequisites

| Tool | Version |
| --- | --- |
| Python | 3.11+ |
| uv | latest |
| PostgreSQL | 16+ |
| Redis | 7+ |
| Node.js | 20.19+ |
| Docker | optional, for the container workflow |

## Backend

```bash
cd ~/code/wenshi-server
cp .env.example .env
uv sync --extra dev

createdb -O wenshi wenshi
uv run alembic -c apps/api/alembic.ini upgrade head
uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

The development environment uses the mock verification provider. The code is always `123456`.

Admin credentials come from `.env`:

```env
ADMIN_USERNAME=admin@wenshi.local
ADMIN_PASSWORD=dev-only-change-me
```

Change both values before deploying to production.

## Admin console

```bash
cd ~/code/wenshi-server/admin-web
npm install
npm run dev
```

Open http://127.0.0.1:5173/admin/.

## Portal

```bash
cd ~/code/wenshi-portal
cp .env.example .env
npm install
npm run dev
```

Open http://127.0.0.1:5174.

## Mobile app

```bash
cd ~/code/wenshi-app
cp .env.example .env
npm install
npm run start
```

For native builds:

```bash
npm run ios
npm run android
```

Set the API address in `wenshi-app/.env`:

```env
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Use `http://10.0.2.2:8000` on the Android emulator, or `http://<computer-lan-ip>:8000` on a physical device. The backend must listen on `0.0.0.0` for LAN access.

Google Sign-In requires a native rebuild and valid OAuth client IDs. It does not work in Expo Go.

## Checks

Backend:

```bash
uv run ruff check .
uv run pytest -q
```

Admin and portal:

```bash
npm run typecheck
npm run build
```

Mobile app:

```bash
npm run typecheck
```

## Troubleshooting

### API returns 502 through nginx

Check that the API container is running and migrations completed:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 api
```

### The app cannot reach the backend

Confirm the backend is bound to `0.0.0.0`, the phone and computer are on the same network, and the local firewall allows port `8000`.

### Google Sign-In reports a missing native module

Rebuild the native app:

```bash
cd ~/code/wenshi-app
npm run ios
# or
npm run android
```

### A local account is disabled

Inspect the user record:

```bash
psql -h localhost -p 5432 -U wenshi -d wenshi
```

```sql
select id, phone, email, google_id, register_provider, disabled, created_at
from users
order by created_at desc;
```
