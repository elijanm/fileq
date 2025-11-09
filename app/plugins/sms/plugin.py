from fastapi import APIRouter,Request,HTTPException
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from plugins.sms.models.models import Provider,ValidStatus
from plugins.sms.services.providers.provider_selector import get_provider
import logging
from routes.auth import get_current_user,checker,Depends,SessionInfo

logger = logging.getLogger("sms")
logging.basicConfig(level=logging.INFO)

def init_plugin(app):
    router = APIRouter()
    templates = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(templates))

    @router.get("/")
    @checker.require_role("admin")
    async def dashboard(user:SessionInfo=Depends(get_current_user)):
        tmpl = env.get_template("dashboard.html")
        return tmpl.render(title="Tasks Plugin")
    
    @router.post("/inbound/{service_provider}/{status}")
    async def inbound_handler(
        service_provider: Provider,
        status: ValidStatus,
        request: Request,
        user:SessionInfo=Depends(get_current_user)
    ):
        """
        Generic inbound webhook for multiple communication service providers.
        Example:
            POST /communication/inbound/telenyx/Success
            POST /communication/inbound/twilio/Failed
        """
        try:
            data = await request.json()
        except Exception:
            data = await request.body()
            logger.warning("Non-JSON payload received")

        # Log incoming webhook
        logger.info(f"[{service_provider}] inbound {status}: {data}")

        # --- ROUTING LOGIC ---
        if status == "success":
            # Handle message delivery success
            # e.g., mark message as delivered in DB
            pass
        elif status == "queue":
            # Handle queued message
            pass
        elif status == "failed":
            # Handle delivery failure
            pass
        else:
            raise HTTPException(status_code=400, detail="Invalid status")

        return {"provider": service_provider, "status": status, "received": True}

    @router.post("/create")
    async def create_item(item: dict,user:SessionInfo=Depends(get_current_user)):
        return {"status": "created", "plugin": "tasks", "item": item}
    
    
    @router.post("/send/{provider_name}")
    async def send_message(provider_name: Provider, payload: dict):
        provider = get_provider(provider_name, api_key="")
        response = await provider.send(payload)
        return {"status": "ok", "provider": provider_name, "response": response}
    @router.post("/balance/{provider_name}")
    async def balance(provider_name: Provider):
        provider = get_provider(provider_name, api_key="")
        response = await provider.balance()
        return {"status": "ok", "provider": provider_name, "response": response}


    return {"router": router}

   