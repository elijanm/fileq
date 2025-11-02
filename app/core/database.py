# database_async.py - Improved Async MongoDB connection manager

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import (
    ConnectionFailure,
    ServerSelectionTimeoutError,
    OperationFailure,
    ConfigurationError
)
from typing import Optional, AsyncGenerator, Dict, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# =====================================
# CONFIGURATION
# =====================================

@dataclass
class AsyncDatabaseConfig:
    """Async MongoDB configuration"""
    mongo_uri: str
    database_name: str
    max_pool_size: int = 100
    min_pool_size: int = 10
    server_selection_timeout_ms: int = 5000
    connect_timeout_ms: int = 5000
    socket_timeout_ms: int = 20000
    retry_writes: bool = True
    retry_reads: bool = True
    max_idle_time_ms: int = 45000
    wait_queue_timeout_ms: int = 5000
    uuid_representation: str = "standard"
    
    @classmethod
    def from_env(cls) -> "AsyncDatabaseConfig":
        """Create configuration from environment variables"""
        return cls(
            mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            database_name=os.getenv("MONGO_DATABASE", "fq_db"),
            max_pool_size=int(os.getenv("MONGO_MAX_POOL_SIZE", "100")),
            min_pool_size=int(os.getenv("MONGO_MIN_POOL_SIZE", "10")),
            server_selection_timeout_ms=int(os.getenv("MONGO_SERVER_TIMEOUT_MS", "5000")),
            connect_timeout_ms=int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "5000")),
            socket_timeout_ms=int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "20000")),
        )
    
    def validate(self) -> None:
        """Validate configuration"""
        if not self.mongo_uri:
            raise ValueError("MongoDB URI cannot be empty")
        if not self.database_name:
            raise ValueError("Database name cannot be empty")
        if self.max_pool_size < self.min_pool_size:
            raise ValueError("max_pool_size must be >= min_pool_size")
        if self.max_pool_size < 1:
            raise ValueError("max_pool_size must be at least 1")


# =====================================
# ASYNC DATABASE MANAGER
# =====================================

class AsyncDatabaseManager:
    """
    Thread-safe async singleton MongoDB connection manager with connection pooling.
    Uses Motor (async driver) for high-performance async operations.
    """
    
    _instance: Optional["AsyncDatabaseManager"] = None
    _lock: asyncio.Lock = None
    _client: Optional[AsyncIOMotorClient] = None
    _database: Optional[AsyncIOMotorDatabase] = None
    _config: Optional[AsyncDatabaseConfig] = None
    _initialized: bool = False
    
    def __new__(cls) -> "AsyncDatabaseManager":
        """Singleton pattern implementation"""
        if cls._instance is None:
            cls._instance = super(AsyncDatabaseManager, cls).__new__(cls)
            cls._lock = asyncio.Lock()
        return cls._instance
    
    async def initialize(
        self,
        config: Optional[AsyncDatabaseConfig] = None,
        mongo_uri: Optional[str] = None,
        database_name: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Initialize async database connection with connection pool.
        Should be called once at app startup.
        
        Args:
            config: AsyncDatabaseConfig object (preferred)
            mongo_uri: MongoDB URI (deprecated, use config)
            database_name: Database name (deprecated, use config)
            **kwargs: Additional config parameters
            
        Raises:
            ConnectionFailure: If unable to connect to database
            ValueError: If invalid configuration
        """
        # Use lock to ensure thread-safe initialization
        async with self._lock:
            if self._initialized:
                logger.warning("AsyncDatabaseManager already initialized, skipping")
                return
            
            # Create config from parameters or environment
            if config is None:
                if mongo_uri or database_name or kwargs:
                    config = AsyncDatabaseConfig(
                        mongo_uri=mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017"),
                        database_name=database_name or os.getenv("MONGO_DATABASE", "fq_db"),
                        **kwargs
                    )
                else:
                    config = AsyncDatabaseConfig.from_env()
            
            # Validate configuration
            config.validate()
            self._config = config
            
            try:
                # Create async client with connection pooling
                self._client = AsyncIOMotorClient(
                    config.mongo_uri,
                    maxPoolSize=config.max_pool_size,
                    minPoolSize=config.min_pool_size,
                    serverSelectionTimeoutMS=config.server_selection_timeout_ms,
                    connectTimeoutMS=config.connect_timeout_ms,
                    socketTimeoutMS=config.socket_timeout_ms,
                    retryWrites=config.retry_writes,
                    retryReads=config.retry_reads,
                    maxIdleTimeMS=config.max_idle_time_ms,
                    waitQueueTimeoutMS=config.wait_queue_timeout_ms,
                    uuidRepresentation=config.uuid_representation,
                )
                
                # Verify connection by pinging server
                await asyncio.wait_for(
                    self._client.server_info(),
                    timeout=config.server_selection_timeout_ms / 1000
                )
                
                self._database = self._client[config.database_name]
                self._initialized = True
                
                logger.info(
                    f"✅ Connected to MongoDB: {config.database_name} "
                    f"(pool: {config.min_pool_size}-{config.max_pool_size})"
                )
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"❌ Failed to connect to MongoDB: {e}")
                await self._cleanup()
                raise ConnectionFailure(f"Could not connect to MongoDB: {e}") from e
            except asyncio.TimeoutError as e:
                logger.error(f"❌ MongoDB connection timeout")
                await self._cleanup()
                raise ConnectionFailure("MongoDB connection timeout") from e
            except Exception as e:
                logger.error(f"❌ Unexpected error during MongoDB initialization: {e}")
                await self._cleanup()
                raise
    
    async def _cleanup(self) -> None:
        """Internal cleanup method"""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.error(f"Error closing MongoDB client: {e}")
        self._client = None
        self._database = None
        self._config = None
        self._initialized = False
    
    @property
    def client(self) -> AsyncIOMotorClient:
        """
        Get MongoDB async client
        
        Returns:
            AsyncIOMotorClient instance
            
        Raises:
            RuntimeError: If not initialized
        """
        if not self._initialized or self._client is None:
            raise RuntimeError(
                "AsyncDatabaseManager not initialized. Call `await initialize()` first."
            )
        return self._client
    
    @property
    def database(self) -> AsyncIOMotorDatabase:
        """
        Get database instance
        
        Returns:
            AsyncIOMotorDatabase instance
            
        Raises:
            RuntimeError: If not initialized
        """
        if not self._initialized or self._database is None:
            raise RuntimeError(
                "AsyncDatabaseManager not initialized. Call `await initialize()` first."
            )
        return self._database
    
    @property
    def is_initialized(self) -> bool:
        """Check if database is initialized"""
        return self._initialized
    
    def get_collection(self, name: str) -> AsyncIOMotorCollection:
        """
        Get a collection by name
        
        Args:
            name: Collection name
            
        Returns:
            AsyncIOMotorCollection instance
            
        Raises:
            RuntimeError: If not initialized
            
        Usage:
            collection = db_manager.get_collection("users")
            await collection.insert_one({"name": "John"})
        """
        if not self._initialized or self._database is None:
            raise RuntimeError(
                "AsyncDatabaseManager not initialized. Call `await initialize()` first."
            )
        return self._database[name]
    
    @asynccontextmanager
    async def collection_context(self, name: str) -> AsyncGenerator[AsyncIOMotorCollection, None]:
        """
        Context manager for working with a MongoDB collection safely.
        
        Args:
            name: Collection name
            
        Yields:
            AsyncIOMotorCollection instance
            
        Usage:
            async with db_manager.collection_context("users") as users:
                await users.insert_one({"name": "John"})
                count = await users.count_documents({})
        """
        if not self._initialized or self._database is None:
            raise RuntimeError(
                "AsyncDatabaseManager not initialized. Call `await initialize()` first."
            )
        
        collection = self._database[name]
        try:
            yield collection
        except Exception as e:
            logger.error(f"Error in collection context '{name}': {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check on database connection
        
        Returns:
            Dictionary with health status and metrics
        """
        if not self._initialized:
            return {
                "status": "unhealthy",
                "error": "Database not initialized",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        try:
            # Measure latency with ping command
            start_time = datetime.now()
            await asyncio.wait_for(
                self._client.admin.command('ping'),
                timeout=5.0
            )
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            # Get server info
            server_info = await self._client.server_info()
            
            # Get database stats
            try:
                db_stats = await self._database.command('dbStats')
            except Exception:
                db_stats = {}
            
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "database": self._config.database_name if self._config else "unknown",
                "version": server_info.get("version", "unknown"),
                "collections": db_stats.get("collections", 0),
                "data_size": db_stats.get("dataSize", 0),
                "indexes": db_stats.get("indexes", 0),
                "pool_size": f"{self._config.min_pool_size}-{self._config.max_pool_size}" if self._config else "unknown",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except asyncio.TimeoutError:
            logger.error("Database health check timeout")
            return {
                "status": "unhealthy",
                "error": "Health check timeout",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": f"Connection error: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Unexpected error during health check: {e}")
            return {
                "status": "unhealthy",
                "error": f"Unexpected error: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def reset_connection(self) -> None:
        """
        Reset database connection (useful for recovery from connection failures)
        
        Warning: This will close all existing connections in the pool
        """
        logger.warning("Resetting database connection...")
        async with self._lock:
            config = self._config
            await self._cleanup()
            if config:
                await self.initialize(config=config)
    
    async def close(self) -> None:
        """
        Gracefully close database connection and cleanup resources
        
        Should be called during application shutdown
        """
        logger.info("Closing database connection...")
        async with self._lock:
            await self._cleanup()
            logger.info("✅ Database connection closed")
    
    async def create_indexes(self, indexes_config: Dict[str, list]) -> None:
        """
        Create indexes for collections
        
        Args:
            indexes_config: Dictionary mapping collection names to index definitions
            
        Example:
            await db_manager.create_indexes({
                "users": [
                    {"keys": [("email", 1)], "unique": True},
                    {"keys": [("created_at", -1)]}
                ],
                "sessions": [
                    {"keys": [("session_id", 1)], "unique": True},
                    {"keys": [("expires_at", 1)], "expireAfterSeconds": 0}
                ]
            })
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized")
        
        for collection_name, indexes in indexes_config.items():
            collection = self._database[collection_name]
            for index_def in indexes:
                try:
                    keys = index_def.pop("keys")
                    await collection.create_index(keys, **index_def)
                    logger.info(f"✅ Created index on {collection_name}: {keys}")
                except Exception as e:
                    logger.error(f"❌ Failed to create index on {collection_name}: {e}")
    
    async def list_collections(self) -> list:
        """
        List all collections in the database
        
        Returns:
            List of collection names
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized")
        
        try:
            return await self._database.list_collection_names()
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []
    
    async def drop_collection(self, name: str) -> bool:
        """
        Drop a collection
        
        Args:
            name: Collection name
            
        Returns:
            True if successful
            
        Warning: Use with extreme caution in production!
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized")
        
        try:
            await self._database.drop_collection(name)
            logger.warning(f"⚠️ Dropped collection: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to drop collection {name}: {e}")
            return False


# =====================================
# GLOBAL INSTANCE
# =====================================

# Global async database manager instance
db_manager = AsyncDatabaseManager()


# =====================================
# FASTAPI DEPENDENCIES
# =====================================

async def get_database() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    FastAPI dependency for database access
    
    Yields:
        AsyncIOMotorDatabase instance
        
    Usage:
        @router.get("/users")
        async def get_users(db: AsyncIOMotorDatabase = Depends(get_database)):
            users = await db.users.find().to_list(100)
            return users
    """
    # Lazy initialization
    if not db_manager.is_initialized:
        try:
            await db_manager.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    try:
        yield db_manager.database
    finally:
        # Connection pool manages lifecycle, nothing to close per-request
        pass


async def get_collection(collection_name: str) -> AsyncGenerator[AsyncIOMotorCollection, None]:
    """
    FastAPI dependency for collection access
    
    Args:
        collection_name: Name of the collection
        
    Yields:
        AsyncIOMotorCollection instance
        
    Usage:
        def get_users_collection():
            return get_collection("users")
        
        @router.get("/users")
        async def list_users(
            users: AsyncIOMotorCollection = Depends(get_users_collection)
        ):
            return await users.find().to_list(100)
    """
    if not db_manager.is_initialized:
        try:
            await db_manager.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    try:
        yield db_manager.get_collection(collection_name)
    finally:
        pass


async def get_database_health() -> Dict[str, Any]:
    """
    FastAPI dependency for health check endpoints
    
    Usage:
        @app.get("/health/database")
        async def check_database(health: dict = Depends(get_database_health)):
            return health
    """
    return await db_manager.health_check()


# =====================================
# STARTUP/SHUTDOWN HELPERS
# =====================================

async def startup_event(config: Optional[AsyncDatabaseConfig] = None) -> None:
    """
    Startup event handler for FastAPI
    
    Args:
        config: Optional database configuration
        
    Usage:
        @app.on_event("startup")
        async def on_startup():
            await startup_event()
    """
    try:
        await db_manager.initialize(config=config)
        
        # Verify health
        health = await db_manager.health_check()
        if health["status"] != "healthy":
            logger.warning(f"Database health check after startup: {health}")
        
    except Exception as e:
        logger.error(f"Failed to initialize database during startup: {e}")
        raise


async def shutdown_event() -> None:
    """
    Shutdown event handler for FastAPI
    
    Usage:
        @app.on_event("shutdown")
        async def on_shutdown():
            await shutdown_event()
    """
    try:
        await db_manager.close()
    except Exception as e:
        logger.error(f"Error during database shutdown: {e}")


# =====================================
# UTILITY FUNCTIONS
# =====================================

async def ensure_indexes(indexes_config: Dict[str, list]) -> None:
    """
    Ensure indexes exist (create if they don't)
    
    Args:
        indexes_config: Index configuration dictionary
        
    Usage:
        await ensure_indexes({
            "users": [
                {"keys": [("email", 1)], "unique": True}
            ]
        })
    """
    await db_manager.create_indexes(indexes_config)


@asynccontextmanager
async def transaction_context():
    """
    Context manager for MongoDB transactions
    
    Usage:
        async with transaction_context() as session:
            await db.users.insert_one({"name": "John"}, session=session)
            await db.logs.insert_one({"action": "user_created"}, session=session)
            # Transaction commits automatically if no exception
            # Rolls back if exception occurs
    """
    if not db_manager.is_initialized:
        raise RuntimeError("Database not initialized")
    
    async with await db_manager.client.start_session() as session:
        async with session.start_transaction():
            try:
                yield session
            except Exception as e:
                logger.error(f"Transaction failed, rolling back: {e}")
                raise


# =====================================
# BACKWARD COMPATIBILITY
# =====================================

# Alias for backward compatibility
get_db = get_database


# =====================================
# USAGE EXAMPLES
# =====================================

async def example_usage():
    """Example usage patterns"""
    
    # Example 1: Initialize database
    config = AsyncDatabaseConfig.from_env()
    await db_manager.initialize(config=config)
    
    # Example 2: Direct collection access
    users = db_manager.get_collection("users")
    await users.insert_one({"name": "John", "email": "john@example.com"})
    user = await users.find_one({"email": "john@example.com"})
    print(f"Found user: {user}")
    
    # Example 3: Using context manager
    async with db_manager.collection_context("users") as users:
        count = await users.count_documents({})
        print(f"Total users: {count}")
    
    # Example 4: Health check
    health = await db_manager.health_check()
    print(f"Database health: {health}")
    
    # Example 5: Create indexes
    await db_manager.create_indexes({
        "users": [
            {"keys": [("email", 1)], "unique": True},
            {"keys": [("created_at", -1)]}
        ]
    })
    
    # Example 6: Using transactions
    async with transaction_context() as session:
        await db_manager.database.users.insert_one(
            {"name": "Jane"},
            session=session
        )
        await db_manager.database.logs.insert_one(
            {"action": "user_created"},
            session=session
        )
    
    # Cleanup
    await db_manager.close()


# =====================================
# FASTAPI LIFESPAN INTEGRATION
# =====================================

async def lifespan_example(app):
    """
    Example lifespan integration for FastAPI
    
    Usage:
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            config = AsyncDatabaseConfig.from_env()
            await db_manager.initialize(config=config)
            
            # Verify health
            health = await db_manager.health_check()
            if health["status"] != "healthy":
                raise RuntimeError(f"Database unhealthy: {health}")
            
            yield
            
            # Shutdown
            await db_manager.close()
    """
    pass


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())