import logging
import anyio
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("tenant")


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract tenant context safely from subdomain.
    Handles EndOfStream / No response errors gracefully.
    """

    def __init__(self, app: FastAPI):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "")
        try:
            if "." in host and not host.startswith("localhost"):
                subdomain = host.split(".")[0]
                if subdomain not in ["www", "api", "admin"]:
                    tenant_service = getattr(request.app.state, "tenant_service", None)
                    if tenant_service:
                        tenant = await tenant_service.get_tenant_by_subdomain(subdomain)
                        if tenant and tenant.status in ["ACTIVE", "TRIAL"]:
                            request.state.tenant_id = tenant.id
                            request.state.tenant = tenant
                    else:
                        logger.warning("Tenant service not initialized in app.state")
        except Exception as e:
            logger.warning(f"⚠️ Tenant resolution failed for host '{host}': {e}")

        # ✅ Always ensure downstream response is handled
        try:
            response = await call_next(request)
            if not response:
                logger.error(f"❌ call_next returned None for {request.url.path}")
                return JSONResponse(
                    {"error": "No response returned"}, status_code=500
                )
            return response

        # --- Handle closed client connection (EndOfStream) gracefully
        except anyio.EndOfStream:
            logger.warning(f"⚠️ Client disconnected early: {request.url.path}")
            return JSONResponse(
                {"warning": "Client disconnected before response was sent"},
                status_code=499,  # 499 = client closed request (Nginx convention)
            )

        # --- Handle downstream "No response returned."
        except RuntimeError as e:
            if "No response returned" in str(e):
                logger.error(f"⚠️ Downstream returned no response: {request.url.path}")
                return JSONResponse(
                    {"error": "Downstream returned no response"},
                    status_code=500,
                )
            raise

        # --- Catch-all fallback
        except Exception as e:
            logger.exception(f"Unhandled error in TenantContextMiddleware: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)
