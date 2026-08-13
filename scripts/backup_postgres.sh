#!/usr/bin/env bash

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"

DB_SERVICE="db"
BACKEND_SERVICE="backend"

DATABASE="$(
    docker compose -f "${COMPOSE_FILE}" exec -T "${DB_SERVICE}" \
        printenv POSTGRES_DB
)"
DB_USER="$(
    docker compose -f "${COMPOSE_FILE}" exec -T "${DB_SERVICE}" \
        printenv POSTGRES_USER
)"

BACKUP_BUCKET="zvuchno-backups"
BACKUP_PREFIX="postgres"

TIMESTAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
FILENAME="zvuchno_${TIMESTAMP}.sql.gz"

TEMP_DIR="$(mktemp -d)"
LOCAL_FILE="${TEMP_DIR}/${FILENAME}"
CONTAINER_FILE="/tmp/${FILENAME}"

cleanup() {
    rm -rf "${TEMP_DIR}"
    docker compose -f "${COMPOSE_FILE}" exec -T "${BACKEND_SERVICE}" \
        rm -f "${CONTAINER_FILE}" >/dev/null 2>&1 || true
}

trap cleanup EXIT

echo "[$(date)] Creating PostgreSQL dump..."

docker compose -f "${COMPOSE_FILE}" exec -T "${DB_SERVICE}" \
    pg_dump -U "${DB_USER}" -d "${DATABASE}" \
    | gzip > "${LOCAL_FILE}"

echo "[$(date)] Dump created: ${LOCAL_FILE}"

gzip -t "${LOCAL_FILE}"

echo "[$(date)] Copying dump to backend container..."

docker cp \
    "${LOCAL_FILE}" \
    "$(docker compose -f "${COMPOSE_FILE}" ps -q "${BACKEND_SERVICE}"):${CONTAINER_FILE}"

S3_KEY="${BACKUP_PREFIX}/${FILENAME}"

echo "[$(date)] Uploading to Object Storage..."

docker compose -f "${COMPOSE_FILE}" exec -T "${BACKEND_SERVICE}" \
    python - "${CONTAINER_FILE}" "${BACKUP_BUCKET}" "${S3_KEY}" <<'PY'
import os
import sys

import boto3

file_path = sys.argv[1]
bucket = sys.argv[2]
key = sys.argv[3]

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["AWS_S3_ENDPOINT_URL"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ["AWS_S3_REGION_NAME"],
)

s3.upload_file(file_path, bucket, key)

print(f"Uploaded: s3://{bucket}/{key}")
PY

echo "[$(date)] Removing old backups..."

docker compose -f "${COMPOSE_FILE}" exec -T "${BACKEND_SERVICE}" \
    python - "${BACKUP_BUCKET}" "${BACKUP_PREFIX}/" <<'PY'
import os
import sys

import boto3

bucket = sys.argv[1]
prefix = sys.argv[2]

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["AWS_S3_ENDPOINT_URL"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    region_name=os.environ["AWS_S3_REGION_NAME"],
)

objects = []

paginator = s3.get_paginator("list_objects_v2")

for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
    objects.extend(page.get("Contents", []))

objects.sort(
    key=lambda obj: obj["LastModified"],
    reverse=True,
)

old_objects = objects[30:]

if old_objects:
    s3.delete_objects(
        Bucket=bucket,
        Delete={
            "Objects": [
                {"Key": obj["Key"]}
                for obj in old_objects
            ],
        },
    )

print(f"Backups retained: {min(len(objects), 30)}")
print(f"Backups deleted: {len(old_objects)}")
PY

echo "[$(date)] Backup completed successfully."
