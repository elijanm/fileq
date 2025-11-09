
import asyncio
import dramatiq
from bson import ObjectId
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from plugins.pms.utils.advanced_rent_analytics import AdvancedRentAnalytics
from workers.tasks import MONGO_URI
from core.scheduler_decorators import run_every_day,run_every_hour,run_every_minute

@run_every_hour
@dramatiq.actor
def test_hourly():
    #Code will run every hour
    print(f"Called at {datetime.now(timezone.utc)}")
