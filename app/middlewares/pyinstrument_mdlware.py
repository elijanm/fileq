from pyinstrument import Profiler
from fastapi import Request
from starlette.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware

class PyInstrumentMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "profile" not in request.query_params:
            return await call_next(request)

        profiler = Profiler()
        profiler.start()

        response = await call_next(request)

        profiler.stop()
        html_output = profiler.output_html()

    
        return HTMLResponse(html_output)
