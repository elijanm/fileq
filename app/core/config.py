import os
from dotenv import load_dotenv
load_dotenv()

class Settings:
    APP_NAME = "Nexidra Modular Core"
    MONGO_URL = os.getenv("MONGO_URI", "mongodb://localhost:27017/nexidra")
    REGISTRY_URL = os.getenv("REGISTRY_URL", "http://127.0.0.1:8001")
    REGISTRY_API_KEY=os.getenv("REGISTRY_API_KEY",None)
    VERIFY_KEY_PATH = os.getenv("VERIFY_KEY_PATH", "./keys/public.pem")

settings = Settings()
