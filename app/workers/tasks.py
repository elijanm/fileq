import dramatiq
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from motor.motor_asyncio import AsyncIOMotorClient
import redis
from minio import Minio
import os
import tempfile
import asyncio

# ---------------------------------------------------
# Setup connections (in real use, config via ENV)
# ---------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017/fileq")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

# MongoDB client (sync here, workers usually avoid async overhead)
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client.get_database()

# Redis client
redis_client = redis.Redis.from_url(REDIS_URL)

# MinIO client

try:
    minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=secure,
)
except Exception as e:
    print(f"Exception {e}={MINIO_ENDPOINT} ")


# RabbitMQ broker
broker = RabbitmqBroker(url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/"))
dramatiq.set_broker(broker)

# ---------------------------------------------------
# Example Dramatiq tasks
# ---------------------------------------------------


def run_redis(func_name: str, *args, **kwargs):
    """
    Safely run any redis.asyncio function from sync Dramatiq workers.
    """
    func = getattr(redis_client, func_name)

    async def runner():
        return await func(*args, **kwargs)

    return asyncio.run(runner())

@dramatiq.actor(max_retries=3)
def hello_task(name: str):
    """Simple hello world task."""
    
    redis_client.incr("hello")
    print(f"👋 Hello {name}, from Dramatiq worker! {redis_client.get('hello')}")


@dramatiq.actor(max_retries=2)
def validate_file(bucket: str, object_name: str, file_id: str):
    """
    Downloads a file from MinIO, validates size & mime, updates MongoDB.
    """
    print(f"🔍 Validating file: {bucket}/{object_name}")
    # run_redis("incr","validated_files")
    redis_client.incr("validated_files")
    tmp_path=None

    try:
        # Download file temporarily
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            minio_client.fget_object(bucket, object_name, tmp.name)
            tmp_path = tmp.name

        file_size = os.path.getsize(tmp_path)
        print(f"📦 File size = {file_size} bytes")

        # Example validation rule: reject > 10MB
        if file_size > 10:
            async def do_update():
                await db.files.update_one(
                {"_id": file_id},
                {"$set": {"status": "failed", "rejected_reason": "File too large"}}
               )
            asyncio.run(do_update())
            redis_client.set("val_err",f"too large {file_size}")
            
            # run_redis("incr","validated_files_rejected")
            redis_client.incr("validated_files_rejected")
            print("❌ File rejected (too large)")
        else:
            
            async def do_update():
                db.files.update_one(
                {"_id": file_id},
                {"$set": {"status": "valid"}}
            )
            asyncio.run(do_update())
            
            
            # redis_client.incr("")
            redis_client.incr("validated_files_accepted")
            print("✅ File validated successfully")

       

    except Exception as e:
        print(f"⚠️ Validation failed: {e}")
        # run_redis("set","validated_files_error",str(e))
        redis_client.set("validated_files_error",str(e))
        async def do_update():
               db.files.update_one(
                    {"_id": file_id},
                    {"$set": {"status": "failed", "rejected_reason": str(e)}}
                )
            
        asyncio.run(do_update())
        
        raise
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@dramatiq.actor(max_retries=2)
def transcribe_audio(bucket: str, object_name: str, file_id: str):
    """
    Stub for audio transcription – in real use, call Whisper.
    """
    print(f"🎙️ Transcribing audio: {object_name}")
    # Simulate transcript
    transcript = f"Transcript of {object_name} (demo)"
    db.transcripts.insert_one({"file_id": file_id, "text": transcript, "language": "en"})
    
    redis_client.incr("transcribed_files")
    print("✅ Transcript stored in MongoDB")
