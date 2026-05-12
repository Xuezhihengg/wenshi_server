#!/bin/sh
# pg_backup.sh — dump PostgreSQL into /backups with timestamped filename
# Run inside the "backup" service:
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup
# Or schedule via host cron (recommended):
#   0 3 * * * cd /opt/wenshi-server && docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup
set -eu

BACKUP_DIR=${BACKUP_DIR:-/backups}
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-14}
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUT="${BACKUP_DIR}/${PGDATABASE}-${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"
echo "[backup] dumping ${PGDATABASE}@${PGHOST} -> ${OUT}"
pg_dump --no-owner --no-privileges "$PGDATABASE" | gzip -9 > "$OUT"

echo "[backup] pruning files older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -name '*.sql.gz' -type f -mtime +${RETENTION_DAYS} -print -delete

ls -lh "$BACKUP_DIR"
