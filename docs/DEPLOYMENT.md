# Deployment Guide

This guide describes a production deployment on a single Linux server using Docker Compose, nginx and Let's Encrypt.

The examples use the official domain `wenshi.xin`. Replace the domain, server address and certificates with your own values for a fork.

## Topology

```text
Internet
   │
   ▼
nginx :80/:443
   ├── /            → portal-web
   ├── /admin/      → admin-web
   ├── /api/v1/     → api
   └── /uploads/    → api static files
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
          PostgreSQL            Redis
```

Only nginx publishes host ports. PostgreSQL, Redis and the API remain on the internal Docker network.

## Prerequisites

- A Linux server with Docker Engine and the Docker Compose plugin
- A domain whose `A` records point to the server
- Inbound TCP `22`, `80` and `443` allowed by the cloud security group
- Optional: ICP filing when serving from mainland China

## Server bootstrap

The following example targets Alibaba Cloud Linux 8. Adapt the package manager for other distributions.

```bash
sudo dnf makecache
sudo dnf install -y ca-certificates curl git tar

sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Log out and back in so the Docker group membership takes effect, then verify:

```bash
docker --version
docker compose version
```

## DNS and firewall

Create the following DNS records:

| Host | Type | Value |
| --- | --- | --- |
| `@` | A | server public IP |
| `www` | A | server public IP |

Verify resolution:

```bash
dig +short wenshi.xin
dig +short www.wenshi.xin
```

If the host firewall is enabled:

```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

Do not expose PostgreSQL `5432`, Redis `6379` or the API `8000` to the public network.

## Code layout

```text
/opt/wenshi/wenshi-server
/opt/wenshi/wenshi-portal
```

```bash
sudo mkdir -p /opt/wenshi
sudo chown -R "$USER":"$USER" /opt/wenshi
cd /opt/wenshi
git clone https://github.com/Xuezhihengg/wenshi-server.git
git clone https://github.com/Xuezhihengg/wenshi-portal.git
```

The production Compose file in `wenshi-server` builds the portal from the sibling directory `../wenshi-portal`.

## Environment

```bash
cd /opt/wenshi/wenshi-server
cp .env.example .env
```

Set at least the following values:

```env
ENVIRONMENT=production
POSTGRES_PASSWORD=<strong-password>
JWT_SECRET=<openssl-rand-hex-32>
ADMIN_USERNAME=<admin-email>
ADMIN_PASSWORD=<strong-admin-password>
CORS_ORIGINS=https://wenshi.xin,https://www.wenshi.xin
PUBLIC_BASE_URL=https://wenshi.xin
ADMIN_VITE_API_BASE_URL=/
PORTAL_VITE_API_BASE_URL=/

PHONE_VERIFICATION_PROVIDER=dypnsapi_sms
EMAIL_VERIFICATION_PROVIDER=aliyun_dm
```

Production startup is rejected when the API still uses development secrets, the default admin password, `mock` verification providers or a wildcard CORS origin.

Complete the provider credentials for Aliyun SMS, DirectMail, Apple Sign-In, Google Sign-In and the LLM service before starting the stack.

## First deployment

Start the stack over HTTP:

```bash
cd /opt/wenshi/wenshi-server
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Check the services:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl http://wenshi.xin/health
curl http://wenshi.xin/api/v1/memberships/plans
```

The API container runs Alembic migrations on startup.

## HTTPS

Confirm that both the apex domain and `www` resolve to the server and port `80` is reachable, then issue certificates:

```bash
cd /opt/wenshi/wenshi-server
CERTBOT_EMAIL=you@example.com DOMAIN=wenshi.xin ./infra/scripts/issue_cert.sh
```

The script obtains a certificate, switches nginx to the HTTPS configuration and restarts the container.

Verify:

```bash
curl -I https://wenshi.xin
curl https://wenshi.xin/health
```

Schedule renewal:

```cron
15 4 * * * cd /opt/wenshi/wenshi-server && ./infra/scripts/renew_cert.sh >> /var/log/wenshi-certbot.log 2>&1
```

## Updates

```bash
cd /opt/wenshi/wenshi-server
git pull

cd /opt/wenshi/wenshi-portal
git pull

cd /opt/wenshi/wenshi-server
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

To rebuild only one service:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api worker nginx
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build portal-web nginx
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build admin-web nginx
```

## Backups

Run a one-off database dump:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup
```

Schedule a daily backup:

```cron
0 3 * * * cd /opt/wenshi/wenshi-server && docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup >> /var/log/wenshi-backup.log 2>&1
```

Backups are written to the `backup_data` volume and pruned by the backup script.

## Operations

```bash
cd /opt/wenshi/wenshi-server

docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f nginx

docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
  alembic -c apps/api/alembic.ini current

docker compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres \
  psql -U wenshi -d wenshi
```

## Troubleshooting

### 502 Bad Gateway

Inspect the API logs and container state:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 api
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 nginx
```

Common causes are a failed migration, invalid environment variables or a missing portal build context.

### Admin login fails

```bash
curl http://wenshi.xin/health
curl -i http://wenshi.xin/api/v1/admin/login
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 api
```

Confirm that `ADMIN_USERNAME` and `ADMIN_PASSWORD` match the values in `.env`.

### Verification codes are not delivered

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=300 api \
  | grep -Ei 'sms|dypns|dm|email|verification|aliyun'

grep -E 'VERIFICATION|ALIYUN|DM|SMS|DYPNS' .env
```

Production must not use `mock` providers.

### Images or uploads are missing

Confirm the `uploads_data` volume is mounted and `PUBLIC_BASE_URL` matches the public origin. nginx serves the API under `/uploads/`.

## Security checklist

- Use a random `JWT_SECRET` of at least 32 characters.
- Use a unique, strong admin password.
- Keep `.env`, database dumps and TLS private keys outside version control.
- Restrict SSH access and disable password login.
- Enable cloud firewall rules and operating system updates.
- Rotate provider credentials after any suspected exposure.
