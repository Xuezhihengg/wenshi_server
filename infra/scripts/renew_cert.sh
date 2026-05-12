#!/usr/bin/env sh
set -eu

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

$COMPOSE run --rm certbot renew --webroot --webroot-path /var/www/certbot
$COMPOSE exec nginx nginx -s reload
