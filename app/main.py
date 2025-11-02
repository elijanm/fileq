from fastapi import FastAPI, HTTPException,Request
from fastapi.responses import JSONResponse,FileResponse
from contextlib import asynccontextmanager
import os
import structlog
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from jose import jwt
from minio import Minio
from routes import auth,uploads
from utils.db import get_database as get_db
from metrics.metrics import get_metrics
from middlewares.geoip import (
    GeoIPMiddleware
)
from core.database import AsyncDatabaseConfig,db_manager
from services.lago_billing import LagoBillingService
from services.tenant_service import TenantService
from services.user_service import UserService
from utils.redis_client import get_redis_client
from utils.user import SecurityUtils,AuditLogger
from services.kratos_services import KratosService
from services.audit import AuditService
from services.email_services import EmailService
from services.tenant_service import TenantStatus
from services.system_config import SystemConfigService
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from babel.support import Translations
from fastapi_versioning import VersionedFastAPI, version
from core.plugin_loader import discover_and_register_plugins
from routes.auth2 import (
    create_standalone_auth_router
)
from utils.auth.kratos import (
    AuthConfig,
    SessionInfo,
    AuthUtilities,
    initialize_authentication,
    get_current_user,
    get_authenticator,
    get_current_user_api_key,
    auth_health_check,
    limiter,
    logger,
    container
)
from middlewares.latency_middleware import LatencyMiddleware,_register_route
# Import Dramatiq actors
load_dotenv()
from workers.tasks import validate_file, transcribe_audio, hello_task
logger = structlog.get_logger()

config = AuthConfig()

# preload translations once
translations = {
    "en": Translations.load("locales", ["en"]),
    "fr": Translations.load("locales", ["fr"]),
}
DEFAULT_LOCALE = "en"

def get_locale(request: Request) -> str:
    # Pick from header, fallback to en
    lang = request.headers.get("Accept-Language", DEFAULT_LOCALE).split(",")[0]
    return lang if lang in translations else DEFAULT_LOCALE

from babel.support import Translations
class Translator:
    def __init__(self, default_locale="en", locales_path="locales"):
        self.default_locale = default_locale
        self.locales_path = locales_path
        self.translations = {}

        # Preload known languages (optional)
        for lang in ["en", "fr"]:
            try:
                self.translations[lang] = Translations.load(locales_path, [lang])
            except Exception:
                self.translations[lang] = Translations()  # fallback: identity

    def t(self, msg: str, locale: str = None) -> str:
        """Translate a message into the given locale (fallback to default)."""
        lang = locale or self.default_locale

        if lang not in self.translations:
            try:
                self.translations[lang] = Translations.load(self.locales_path, [lang])
            except Exception:
                self.translations[lang] = Translations()  # fallback

        return self.translations[lang].gettext(msg)
tr = Translator(default_locale="en", locales_path="locales") 
    


# Enhanced lifespan with tenant service
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events with tenant service"""
    # Startup
    logger.info("Starting Multi-tenant Authentication API...")
    
    # Initialize database connections
    db = get_db()
    redis_client = get_redis_client()
    metrics = get_metrics()
    
    
    
    
    # Initialize services
    security_utils = SecurityUtils()
    kratos_service = KratosService(db=db,metrics_collector=metrics)
    lago_service = LagoBillingService(db=db,metrics_collector=metrics)
    email_service = EmailService(db=db,metrics_collector=metrics)
    auth_utils: AuthUtilities =  AuthUtilities(db)
    AuditService.configure(db, metrics)
    SystemConfigService.setup(db)
    # Initialize authentication system
    initialize_authentication(auth_utils)
    logger.info("authentication_initialized")
    
    
    
    
    
    audit_service = AuditService()
    
    # Initialize tenant service
    tenant_service = TenantService(
        tenants_collection=db.tenants,
        tenant_users_collection=db.tenant_users,
        tenant_invitations_collection=db.tenant_invitations,
        users_collection=db.users,
        audit_service=audit_service,
        email_service=email_service
    )
    
    # Initialize enhanced user service with tenant support
    user_service = UserService(
        db=db,
        redis_client=redis_client,
        kratos_service=kratos_service,
        lago_service=lago_service,
        email_service=email_service,
        audit_service=audit_service,
        security_utils=security_utils,
        metrics=metrics,
        tenant_service=tenant_service  # Add tenant service dependency
    )
    
    db_config = AsyncDatabaseConfig.from_env()
    await db_manager.initialize(config=db_config)
    adb = db_manager.database
    
    # Store in app state
    app.state.db=db #ToDo make it aasync with get_database from core
    app.state.adb=adb
    app.state.translator =tr 
    app.state.email_service = email_service
    app.state.audit_service = audit_service
    app.state.translations = translations
    app.state.lago_service = lago_service
    app.state.kratos_service = kratos_service
    app.state.redis_client = redis_client
    app.state.user_service = user_service
    app.state.tenant_service = tenant_service
    app.state.security_utils = security_utils
    app.state.metrics = metrics
    await discover_and_register_plugins(app)
    for r in app.routes:
        if "heatmap" in r.path:
           print(f"→ {r.name} :: {r.path}")
    # Perform health check
    # health_status = await auth_health_check()
    # logger.info("startup_health_check", status=health_status)
    # print(health_status)
    # if health_status["overall_status"] == "unhealthy":
    #     logger.warning("startup_health_issues", checks=health_status["checks"])
    health=await db_manager.health_check()  
    if health["status"] != "healthy":
        raise RuntimeError(f"Database unhealthy: {health}")
    print(health)
    logger.info("✅ Multi-tenant Authentication API started successfully")

    
    yield
    await db_manager._cleanup()
    # await db.aclose()
    # Shutdown
    logger.info("🛑 Shutting down Multi-tenant Authentication API...")
    redis_client.close()

# Update app initialization
from core.MongoORJSONResponse import MongoORJSONResponse
app = FastAPI(
    title="Multi-tenant Authentication API",
    description="Enterprise-grade multi-tenant authentication service",
    version="2.0.0",
    lifespan=lifespan,
    default_response_class=MongoORJSONResponse
)

from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

from middlewares.pyinstrument_mdlware import PyInstrumentMiddleware

app.add_middleware(PyInstrumentMiddleware)
app0 = FastAPI(default_response_class=MongoORJSONResponse)

# from pyinstrument import Profiler

# async def get_current_user(...):
#     profiler = Profiler(interval=0.001)
#     profiler.start()

#     # do logic
#     user = await find_or_create_anon_user()

#     profiler.stop()
#     profiler.open_in_browser()
#     return user


@app0.get("/")
def home():
    return {"status": "ok"}
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to specific domains e.g. ["https://your-frontend.com"]
    allow_credentials=True,
    allow_methods=["*"],   # or ["GET", "POST", "PUT", "DELETE"]
    allow_headers=["*"],   # or restrict to ["Authorization", "Content-Type"]
)

app.add_middleware(GeoIPMiddleware)
# Middleware to extract tenant context
from middlewares.tenant_context import TenantContextMiddleware
app.add_middleware(TenantContextMiddleware)

class I18nMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.locale = get_locale(request)
        response = await call_next(request)
        response.headers["Content-Language"] = request.state.locale
        return response

app.add_middleware(I18nMiddleware)
app.add_middleware(LatencyMiddleware)

_register_route(app0)
app.mount("/internal", app0)



# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging"""
    logger.warning(
        "http_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(
        "unexpected_exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )



auth_router = create_standalone_auth_router(
        get_authenticator_func=get_authenticator,
        get_current_user_func=get_current_user,
        auth_health_check_func=auth_health_check,
        config=config
    )
        
# app.include_router(auth_router, prefix="/api/v1")
app.include_router(auth.router,prefix="/api/v1")
app.include_router(uploads.router)
# app.include_router(billing.router)

# Root endpoint with tenant awareness
@app.get("/")
async def root(request: Request):
    """Root endpoint with tenant information"""
    base_info = {
        "service": "Multi-tenant Authentication API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs"
    }
    
    # Add tenant context if available
    if hasattr(request.state, 'tenant'):
        tenant = request.state.tenant
        base_info["tenant"] = {
            "name": tenant.name,
            "subdomain": tenant.subdomain,
            "status": tenant.status.value
        }
    
    return base_info

@app.get("/heatmap/static/sw.js")
async def service_worker():
    headers = {"Service-Worker-Allowed": "/"}
    return FileResponse("plugins/heatmap/static/sw.js", headers=headers)




# @app.get("/")
# async def root():
#     return {"msg": "Hello World from FileQ FastAPI demo"}

# @app.get("/mongo")
# async def mongo_test():
#     await db.test.insert_one({"ping": "pong"})
#     doc = await db.test.find_one({}, sort=[("_id", -1)])

#     if doc and "_id" in doc:
#         doc["_id"] = str(doc["_id"])   # serialize ObjectId to string

#     return {"last_doc": doc}

# @app.get("/redis")
# async def redis_test():
#     count = await redis_client.incr("visits")
#     return {"visits": count}
# @app.get("/redis/dump")
# async def redis_dump():
#     keys = await redis_client.keys("*")
#     data = {}
#     for key in keys:
#         data[key] = await redis_client.get(key)
#     return {"dump": data}
# @app.get("/dramatiq")
# async def dramatiq_test():
#     hello_task.send("FileQ user")
#     return {"msg": "Task queued"}

# @app.get("/minio")
# async def minio_test():
#     if not minio_client.bucket_exists("fileq-demo"):
#         minio_client.make_bucket("fileq-demo")
#     buckets = [b.name for b in minio_client.list_buckets()]
#     return {"buckets": buckets}

# @app.get("/secure")
# async def secure_route(token: str):
#     claims = verify_token(token)
#     return {"claims": claims}

# # ---------------------------------------------------
# # Trigger background jobs
# # ---------------------------------------------------
# @app.post("/process/{file_id}")
# async def process_file(file_id: str, job: str = "validate"):
#     """
#     Trigger a Dramatiq job for a given file.
#     job = "validate" | "transcribe"
#     """
#     bucket = "fileq-demo"
#     object_name = f"{file_id}.bin"
    
#     if not minio_client.bucket_exists(bucket):
#         minio_client.make_bucket(bucket)
#     import tempfile
#     with tempfile.NamedTemporaryFile(delete=False) as tmp:
#         tmp.write(b"hello world")
#         tmp.flush()
#         minio_client.fput_object(bucket, object_name, tmp.name)
#         os.remove(tmp.name)

#     if job == "validate":
#         validate_file.send(bucket, object_name, file_id)
#         return {"msg": f"Validation job queued for {file_id}"}
#     elif job == "transcribe":
#         transcribe_audio.send(bucket, object_name, file_id)
#         return {"msg": f"Transcription job queued for {file_id}"}
#     else:
#         raise HTTPException(status_code=400, detail="Unknown job type")
