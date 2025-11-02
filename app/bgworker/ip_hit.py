from pymongo import UpdateOne
from datetime import datetime
import asyncio,statistics,time

def flush_hits_to_mongo(redis_client, mongo_db):
    cursor = 0
    ops = []
    current_minute = int(time.time() // 60)

    while True:
        cursor, keys = redis_client.scan(cursor=cursor, match="hits:*")
        for key in keys:
            key_str = key.decode() if isinstance(key, bytes) else key
            _, ip, minute_key = key_str.split(":")
            count = int(redis_client.get(key) or 0)

            # Skip current minute (still updating)
            if int(minute_key) >= current_minute:
                continue

            ops.append(
                UpdateOne(
                    {"ip": ip, "minute": minute_key},
                    {
                        "$setOnInsert": {"created_at": datetime.utcnow()},
                        "$set": {"updated_at": datetime.utcnow()},
                        "$inc": {"count": count}
                    },
                    upsert=True
                )
            )

            # Delete after persisting
            redis_client.delete(key)

        if cursor == 0:
            break

    if ops:
        result = mongo_db.ip_hits.bulk_write(ops, ordered=False)
        print(f"✅ Flushed {len(ops)} keys → Mongo. "
              f"{result.modified_count} updated, {len(result.upserted_ids)} inserted")
        
        
async def anomaly_worker(redis_client, mongo_db, sigma=3, sleep_time=60):
    while True:
        # 1. Flush Redis → Mongo in bulk
        flush_hits_to_mongo(redis_client, mongo_db)

        # 2. Run anomaly detection on last N docs per IP
        ips = mongo_db.ip_hits.distinct("ip")
        for ip in ips:
            docs = list(
                mongo_db.ip_hits.find({"ip": ip}).sort("created_at", -1).limit(60)
            )
            if len(docs) < 5:
                continue

            latest = docs[0]["count"]
            values = [d["count"] for d in docs[1:]]
            mean = statistics.mean(values)
            stdev = statistics.pstdev(values) or 1

            if latest > mean + sigma * stdev:
                mongo_db.ip_anomalies.insert_one({
                    "ip": ip,
                    "minute": docs[0]["minute"],
                    "count": latest,
                    "detected_at": datetime.utcnow(),
                    "reason": f"Count {latest} exceeds {sigma}σ threshold (mean={mean:.2f}, std={stdev:.2f})"
                })
                print(f"🚨 Anomaly detected for {ip} at {docs[0]['minute']} (count={latest})")

        await asyncio.sleep(sleep_time)
