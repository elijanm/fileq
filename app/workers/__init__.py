# app/workers/__init__.py
import os
import sys
import json
import importlib
import hashlib
import redis
import time
from datetime import datetime
from pymongo import MongoClient
from minio import Minio
import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from dramatiq.middleware import Retries
from dotenv import load_dotenv
load_dotenv()
# ---------------------------------------------------
# Setup connections (in real use, config via ENV)
# ---------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/fileq")


REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

# MongoDB client (sync style to avoid async overhead in worker)
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.get_database()

MAX_RETRIES = 5
BACKOFF_SECONDS = 2

def connect_to_redis():
    """Attempt to connect to Redis with retry and exponential backoff."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
           
            client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=True,
                )

            # test connection
            client.ping()
            print(f"✅ Connected to Redis {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB} (attempt {attempt})")
            return client

        except redis.ConnectionError as e:
            wait = BACKOFF_SECONDS * attempt
            print(f"⚠️ Redis not ready (attempt {attempt}/{MAX_RETRIES}): {e}")
            print(f"   Retrying in {wait}s...")
            time.sleep(wait)

    raise redis.ConnectionError("❌ Failed to connect to Redis after multiple attempts")

# global redis client
redis_client = connect_to_redis()

# MinIO client
try:
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=secure,
    )
    print(f"✅ Connected to MinIO at {MINIO_ENDPOINT}")
except Exception as e:
    print(f"⚠️ MinIO connection failed: {e} ({MINIO_ENDPOINT})")

# RabbitMQ broker (preferred over Redis for Dramatiq in production)
broker = RabbitmqBroker(url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/"))
broker.add_middleware(Retries(max_retries=3))
dramatiq.set_broker(broker)


# ---------------------------------------------------
# Cached Plugin Worker Discovery
# ---------------------------------------------------
CACHE_KEY = "pms:worker_discovery"


def calculate_plugins_hash(base_path="app/plugins") -> str:
    """Create hash fingerprint of all _tasks.py for change detection."""
    file_paths = []
    for root, _, files in os.walk(base_path):
        for f in files:
            if f.endswith("_tasks.py"):
                full_path = os.path.join(root, f)
                file_paths.append(full_path)
    file_paths.sort()
    hasher = hashlib.sha256()
    for path in file_paths:
        hasher.update(path.encode())
        hasher.update(str(os.path.getmtime(path)).encode())  # track mod time
    return hasher.hexdigest()


def discover_plugin_workers(use_cache=True):
    """
    Auto-discover and import worker modules under app/plugins/**/tasks/_tasks.py
    Caches discovery results in Redis for faster startup.
    """
    sys.path.insert(0, os.getcwd())  # ensure root importable
    base_path = os.path.dirname(os.path.realpath(__file__))
    PLUGINS_DIR = os.path.join(base_path, "..", "plugins")
    base_path = os.path.realpath(PLUGINS_DIR)

    new_hash = calculate_plugins_hash(base_path)
    
    cached_data = None
    if use_cache:
        try:
            raw = redis_client.get(CACHE_KEY)
            if raw:
                cached_data = json.loads(raw)
        except Exception as e:
            print(f"⚠️ Cache read error: {e}")
    
    if cached_data and cached_data.get("hash") == new_hash:
        modules = cached_data.get("modules", [])
        print(f"⚡ Using cached worker discovery ({len(modules)} modules)")
    else:
        print(f"🔍 Scanning for plugin worker modules... {base_path}")
        modules = []
        for root, _, files in os.walk(base_path):
            
            for f in files:
                if f.endswith("_tasks.py"):
                    rel_path = os.path.relpath(os.path.join(root, f)).replace(os.sep, ".")
                    module = rel_path.replace(".py", "")
                    modules.append(module)
        try:
            redis_client.set(CACHE_KEY, json.dumps({"hash": new_hash, "modules": modules}))
            print(f"💾 Cached {len(modules)} modules to Redis.")
        except Exception as e:
            print(f"⚠️ Cache write failed: {e}")

    for m in modules:
        try:
            importlib.import_module(m)
            print(f"✅ Loaded worker module: {m}")
        except Exception as e:
            print(f"⚠️ Failed to import {m}: {e}")

    return modules


# ---------------------------------------------------
# Execute auto-discovery on import
# ---------------------------------------------------
discover_plugin_workers()


# ---------------------------------------------------
# Expose resources for plugins to reuse
# ---------------------------------------------------
__all__ = [
    "broker",
    "db",
    "mongo_client",
    "redis_client",
    "minio_client",
    "discover_plugin_workers",
]
