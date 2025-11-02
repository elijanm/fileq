from motor.motor_asyncio import AsyncIOMotorClient
# from core.config import settings
import asyncio
import logging
from typing import Optional, AsyncGenerator
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from typing import Optional
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

logger = logging.getLogger("DatabaseManager")
logger.setLevel(logging.INFO)

load_dotenv()

class DatabaseManager:
    """
    Async Singleton MongoDB connection manager with connection pooling.
    Uses Motor (async driver) and built-in pooling for scalability.
    """

    _instance = None
    _client: Optional[AsyncIOMotorClient] = None
    _database: Optional[AsyncIOMotorDatabase] = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    async def initialize(
        self,
        mongo_uri: str = None,
        database_name: str = "fq_db",
        max_pool_size: int = 100,
        min_pool_size: int = 5,
        server_selection_timeout_ms: int = 5000,
    ):
        """
        Initialize async database connection with connection pool.
        Should be called once at app startup.
        """
        if self._initialized:
            return

        mongo_uri = mongo_uri or os.getenv("MONGO_URL", "mongodb://localhost:27017")
     
        database_name = os.getenv("MONGO_DATABASE", database_name)
        try:
            self._client = AsyncIOMotorClient(
                mongo_uri,
                maxPoolSize=max_pool_size,
                minPoolSize=min_pool_size,
                serverSelectionTimeoutMS=server_selection_timeout_ms,
                uuidRepresentation="standard",
                connectTimeoutMS=5000,
                socketTimeoutMS=20000,
                retryWrites=True,
            )

            # Ensure connection works
            await self._client.server_info()
            self._database = self._client[database_name]
            self._initialized = True

            logger.info(f"✅ Connected to MongoDB [{database_name}] at {mongo_uri}")

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise

    @property
    def client(self) -> AsyncIOMotorClient:
        if self._client is None:
            raise RuntimeError("DatabaseManager not initialized. Call `initialize()` first.")
        return self._client

    @property
    def database(self) -> AsyncIOMotorDatabase:
        if self._database is None:
            raise RuntimeError("DatabaseManager not initialized. Call `initialize()` first.")
        return self._database

    async def close(self):
        """Gracefully close connection pool"""
        if self._client:
            self._client.close()
            logger.info("🧹 MongoDB connection closed")
        self._client = None
        self._database = None
        self._initialized = False

    @asynccontextmanager
    async def get_collection(self, name: str):
        """
        Context manager for working with a MongoDB collection safely.
        Example:
            async with db.get_collection("users") as users:
                await users.insert_one({...})
        """
        if self._database is None:
            raise RuntimeError("DatabaseManager not initialized. Call `initialize()` first.")
        collection = self._database[name]
        try:
            yield collection
        except Exception as e:
            logger.error(f"Error in collection context '{name}': {e}")
            raise


# Example usage in an async environment (e.g., FastAPI startup)

db_manager = DatabaseManager()


async def startup_event():
    await db_manager.initialize(
        mongo_uri=os.getenv("MONGO_URL", "mongodb://localhost:27017"),
        database_name="nexidra_modular",
        max_pool_size=200,
    )


async def shutdown_event():
    await db_manager.close()


# Example usage in a plugin or route handler
async def example_usage():
    async with db_manager.get_collection("users") as users:
        await users.insert_one({"name": "Elijah", "role": "admin"})
        count = await users.count_documents({})
        logger.info(f"User count: {count}")

async def get_database() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    Dependency for FastAPI routes — yields the active database connection.
    Example:
        @router.get("/users")
        async def get_users(db: AsyncIOMotorDatabase = Depends(get_database)):
            docs = await db["users"].find().to_list(100)
    """
    if not db_manager._initialized:
        await db_manager.initialize()
    try:
        yield db_manager.database
    finally:
        # No close here; main app manages lifecycle
        pass