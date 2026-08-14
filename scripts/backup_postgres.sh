#!/usr/bin/env bash
#
# Создаёт резервную копию PostgreSQL из production Docker Compose
# и загружает её в Yandex Object Storage.
#
# Скрипт запускается по расписанию через cron на VM.
#
# Требуемые переменные окружения:
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   AWS_S3_ENDPOINT_URL
#   AWS_DEFAULT_REGION
#
# Требования к VM:
#   - Docker
#   - Docker Compose plugin
#   - AWS CLI v2
#
# Пример запуска через cron:
#   0 3 * * * cd /home/zdocker/zvuchno && set -a && . /etc/zvuchno-backup.env && set +a && ./scripts/backup_postgres.sh >> /home/zdocker/backups/backup.log 2>&1

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
DB_SERVICE="db"

BACKUP_BUCKET="zvuchno-backups"
BACKUP_PREFIX="postgres"
RETENTION_COUNT="${RETENTION_COUNT:-30}"

TIMESTAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
FILENAME="zvuchno_${TIMESTAMP}.dump"

TEMP_DIR="$(mktemp -d)"
LOCAL_FILE="${TEMP_DIR}/${FILENAME}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

cleanup() {
    rm -rf "${TEMP_DIR}"
}

trap cleanup EXIT

exec 9>/tmp/zvuchno-postgres-backup.lock

if ! flock -n 9; then
    log "Backup is already running."
    exit 1
fi

DATABASE="$(
    docker compose -f "${COMPOSE_FILE}" exec -T "${DB_SERVICE}" \
        printenv POSTGRES_DB
)"

DB_USER="$(
    docker compose -f "${COMPOSE_FILE}" exec -T "${DB_SERVICE}" \
        printenv POSTGRES_USER
)"

log "Creating PostgreSQL dump..."

docker compose -f "${COMPOSE_FILE}" exec -T "${DB_SERVICE}" \
    pg_dump \
        -U "${DB_USER}" \
        -d "${DATABASE}" \
        -Fc \
    > "${LOCAL_FILE}"

DUMP_SIZE="$(du -h "${LOCAL_FILE}" | cut -f1)"

log "Dump created: ${LOCAL_FILE} (${DUMP_SIZE})"

log "Checking dump integrity..."

if ! docker compose -f "${COMPOSE_FILE}" exec -T "${DB_SERVICE}" \
        pg_restore --list < "${LOCAL_FILE}" > /dev/null 2>&1; then
    log "ERROR: dump integrity check failed."
    exit 1
fi

log "Dump integrity OK."

S3_KEY="${BACKUP_PREFIX}/${FILENAME}"

log "Uploading to s3://${BACKUP_BUCKET}/${S3_KEY}..."

aws \
    --endpoint-url="${AWS_S3_ENDPOINT_URL}" \
    s3 cp \
    "${LOCAL_FILE}" \
    "s3://${BACKUP_BUCKET}/${S3_KEY}"

log "Upload completed."

log "Applying retention policy: keep ${RETENTION_COUNT} backups."

mapfile -t BACKUP_KEYS < <(
    aws \
        --endpoint-url="${AWS_S3_ENDPOINT_URL}" \
        s3api list-objects-v2 \
        --bucket "${BACKUP_BUCKET}" \
        --prefix "${BACKUP_PREFIX}/" \
        --query 'sort_by(Contents, &LastModified)[].Key' \
        --output text \
    | tr '\t' '\n'
)

TOTAL="${#BACKUP_KEYS[@]}"

if (( TOTAL > RETENTION_COUNT )); then
    TO_DELETE_COUNT=$((TOTAL - RETENTION_COUNT))

    log "Deleting ${TO_DELETE_COUNT} old backup(s)..."

    for ((i = 0; i < TO_DELETE_COUNT; i++)); do
        KEY="${BACKUP_KEYS[$i]}"

        aws \
            --endpoint-url="${AWS_S3_ENDPOINT_URL}" \
            s3 rm \
            "s3://${BACKUP_BUCKET}/${KEY}"

        log "Deleted: ${KEY}"
    done
else
    log "Nothing to delete (${TOTAL}/${RETENTION_COUNT})."
fi

log "Backup completed successfully."
