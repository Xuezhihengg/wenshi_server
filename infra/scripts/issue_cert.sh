#!/usr/bin/env sh
set -eu

DOMAIN="${DOMAIN:-wenshi.xin}"
EMAIL="${CERTBOT_EMAIL:?Set CERTBOT_EMAIL before issuing certificates}"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

$COMPOSE run --rm certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN" \
  -d "www.$DOMAIN"

cp infra/nginx/nginx.https.conf infra/nginx/nginx.conf
$COMPOSE restart nginx
