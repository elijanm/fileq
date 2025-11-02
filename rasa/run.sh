#!/bin/bash
# Script to rebuild and restart Rasa service with training

set -e

echo "🛑 Stopping containers..."
docker compose down --remove-orphans

echo "🔑 Fixing permissions..."
sudo chown -R 1001:1001 /tmps/dockas/default_service/fq/rasa

echo "📚 Training Rasa model..."
docker compose run rasa train

echo "🚀 Rebuilding and starting containers..."
docker compose up -d --build

echo "✅ Rasa service is up and running!"
