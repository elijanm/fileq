#!/bin/bash
set -e

echo "⏳ Waiting for MinIO to be ready..."
until mc alias set myminio http://minio:9000 minioadmin minioadmin 2>/dev/null; do
  sleep 2
done

echo "✅ MinIO is ready. Creating buckets..."

# Create buckets
mc mb --ignore-existing myminio/public
mc mb --ignore-existing myminio/private

# Create pseudo-folders
# for folder in processing approved quarantined; do
#   mc cp /dev/null myminio/public/$folder/.keep
#   mc cp /dev/null myminio/private/$folder/.keep
# done

echo "✅ Buckets and pseudo-folders created."

# Add event notification (only works if webhook was set via env)
mc event add myminio/public arn:minio:sqs::minio_worker_hook --event put,delete,get || true

echo "✅ Webhook configured on 'public' bucket."
mc admin config get myminio notify_webhook

# Start FastAPI
exec uvicorn main:app --host 0.0.0.0 --port 8000
