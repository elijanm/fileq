from fastapi import APIRouter, Request, BackgroundTasks,FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime
from core.database import get_database
from starlette.routing import Mount

router = APIRouter()
plugin_dir = Path(__file__).parent
static_dir = plugin_dir / "static"
templates = Jinja2Templates(directory=str(plugin_dir / "templates"))

# Mount static assets
router.routes.append(
    Mount(
        "/heatmap/static",
        app=StaticFiles(directory=str(static_dir)),
        name="plugin_heatmap_static"
    )
)

@router.post("/api/analytics/heatmap")
async def collect_heatmap_data(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    events = payload.get("events", [])
    if not events:
        return {"status": "empty"}

    async def save_batch(events):
        db_gen = get_database()
        db = await anext(db_gen)
        await db["heatmap_events"].insert_many(
            [{**e, "received_at": datetime.utcnow()} for e in events]
        )
        await db_gen.aclose()

    background_tasks.add_task(save_batch, events)
    return {"status": "queued", "count": len(events)}

@router.post("/log")
async def log_event(request: Request):
    db = request.app.state.adb  # ✅ persistent DB
    data = await request.json()
    data["timestamp"] = datetime.utcnow().isoformat()
    await db["heatmap_events"].insert_one(data)
    return {"status": "ok"}

@router.get("/", response_class=HTMLResponse)
async def view_heatmap(request: Request):
    db = request.app.state.adb
    events = await db["heatmap_events"].find({"type": "click"}).to_list(1000)
    return templates.TemplateResponse("dashboard.html", {"request": request, "events": events})

def init_plugin(app: FastAPI | None = None):
    from loguru import logger
    

    # if static_dir.exists():
    #     app.mount(
    #         "/heatmap/static",
    #         StaticFiles(directory=str(static_dir)),
    #         name="plugin_heatmap_static",
    #     )
    #     logger.info(f"✅ Mounted static at /heatmap/static -> {static_dir}")
    # else:
    #     logger.warning(f"⚠️ Missing static dir: {static_dir.resolve()}")
    return {"router": router}
