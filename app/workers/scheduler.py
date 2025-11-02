import os
import asyncio,logging
from datetime import datetime,timezone
import dramatiq
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dramatiq.brokers.rabbitmq import RabbitmqBroker
from core.scheduler_decorators import SCHEDULED_TASKS
from workers import discover_plugin_workers

# Setup broker
broker = RabbitmqBroker(url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/"))
dramatiq.set_broker(broker)
logging.basicConfig(level=logging.INFO)
_scheduler_started = False 

async def heartbeat():
    logging.info(f"💓 heartbeat at {datetime.utcnow()}")
async def start_scheduler():
    """Scan plugins, load scheduled tasks, and start APScheduler."""
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    global _scheduler_started
    if _scheduler_started:
        print("⚠️ Scheduler already running — skipping duplicate start.")
        return
    _scheduler_started = True
    
    discover_plugin_workers()  # ensure all plugins loaded & decorators registered
    # scheduler = BackgroundScheduler(timezone="UTC")
    scheduler = AsyncIOScheduler(timezone="UTC")
    # scheduler.add_job(heartbeat, IntervalTrigger(seconds=10), id="heartbeat",replace_existing=True)
    
    for task in SCHEDULED_TASKS:
        func = task["func"]
        trigger = task["trigger"]
        trigger_args = task["trigger_args"]

        # Dramatiq actor is the .send() method
        job_func = lambda f=func: f.send()
        func_name = getattr(func, "__name__", None) or getattr(func, "actor_name", str(func))
        
        scheduler.add_job(job_func, 
                                trigger=trigger,
                                name=func_name,
                                coalesce=True,
                                misfire_grace_time=600, 
                                max_instances=1,
                                **trigger_args)
        
        # next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "—"
        
        print(f"⏱️ Registered job: {func_name} ({trigger}, {trigger_args})")

    scheduler.start()
    print("✅ APScheduler started and running scheduled Dramatiq jobs.")
    for job in scheduler.get_jobs():
        next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "—"
        print(
            f"➡️ {job.name} → next run at {next_run} | current time {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
    
    # try:
    #     loop.call_soon(scheduler.start)
    #     loop.run_forever()
    # except (KeyboardInterrupt, SystemExit):
    #     logging.info("🛑 Scheduler shutting down.")
    #     scheduler.shutdown()

    try:
        # asyncio.get_event_loop().run_forever()
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("🛑 Scheduler stopped.")

if __name__ == "__main__":
   asyncio.run(start_scheduler())
