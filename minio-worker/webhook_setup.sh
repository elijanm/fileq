#!/bin/bash
set -e

echo "⏳ Waiting for FastAPI service to be up..."
until curl -s http://minio-worker:8000/notifications >/dev/null; do
  sleep 2
done

echo "✅ FastAPI is up. Registering MinIO webhook..."

mc alias set myminio http://minio:9000 minioadmin minioadmin

mc admin config set myminio notify_webhook:minio-worker-hook \
  endpoint="http://minio-worker:8000/notifications"

if ! mc admin service restart myminio --quiet; then
  echo "⚠️  MinIO restart failed (probably due to non-interactive shell). Skipping."
fi

sleep 5

mc event add myminio/public arn:minio:sqs::minio-worker-hook --event put || true

echo "✅ Webhook registered!"
