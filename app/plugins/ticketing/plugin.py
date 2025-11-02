from fastapi import APIRouter,FastAPI
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from routes.auth import get_current_user,checker,Depends,SessionInfo
from plugins.ticketing.router import router


def init_plugin(app:FastAPI):
    
    return {"router": router}
