#!/bin/bash

set -e

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
MONGO_CONTAINER="auth_mongodb_1"

echo "🗄️ Creating backup for $DATE..."

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup MongoDB
echo "Backing up MongoDB..."
docker exec $MONGO_CONTAINER mongodump --authenticationDatabase admin \
    -u $MONGO_ROOT_USERNAME -p $MONGO_ROOT_PASSWORD \
    --db auth_db --out /tmp/backup_$DATE

docker cp $MONGO_CONTAINER:/tmp/backup_$DATE $BACKUP_DIR/mongodb_$DATE

# Backup Redis (if needed)
echo "Backing up Redis..."
docker exec auth_redis_1 redis-cli --rdb /tmp/dump_$DATE.rdb
docker cp auth_redis_1:/tmp/dump_$DATE.rdb $BACKUP_DIR/redis_$DATE.rdb

# Compress backups
echo "Compressing backups..."
tar -czf $BACKUP_DIR/auth_backup_$DATE.tar.gz -C $BACKUP_DIR mongodb_$DATE redis_$DATE.rdb

# Clean up individual files
rm -rf $BACKUP_DIR/mongodb_$DATE $BACKUP_DIR/redis_$DATE.rdb

# Clean up old backups (keep only last 7 days)
find $BACKUP_DIR -name "auth_backup_*.tar.gz" -mtime +7 -delete

echo "✅ Backup completed: auth_backup_$DATE.tar.gz"