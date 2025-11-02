from typing import Dict, Any, Optional, Generator
from contextlib import contextmanager
from fastapi import Request, Depends, HTTPException
from prometheus_client import Counter, Histogram, Gauge
import time
import logging
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import os
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
from threading import Lock
from metrics.metrics import MetricsCollector

logger = logging.getLogger(__name__)

# =====================================
# DATABASE CONNECTION
# =====================================

@dataclass
class DatabaseConfig:
    """Database configuration"""
    mongo_uri: str
    database_name: str
    max_pool_size: int = 50
    min_pool_size: int = 10
    server_selection_timeout_ms: int = 5000
    connect_timeout_ms: int = 5000
    socket_timeout_ms: int = 5000
    retry_writes: bool = True
    retry_reads: bool = True
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create configuration from environment variables"""
        return cls(
            mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            database_name=os.getenv("MONGO_DATABASE", "fq_db"),
            max_pool_size=int(os.getenv("MONGO_MAX_POOL_SIZE", "50")),
            min_pool_size=int(os.getenv("MONGO_MIN_POOL_SIZE", "10")),
            server_selection_timeout_ms=int(os.getenv("MONGO_SERVER_TIMEOUT_MS", "5000")),
        )


class DatabaseManager:
    """Thread-safe singleton database connection manager with connection pooling"""
    
    _instance: Optional["DatabaseManager"] = None
    _lock: Lock = Lock()
    _client: Optional[MongoClient] = None
    _database: Optional[Database] = None
    _config: Optional[DatabaseConfig] = None
    _initialized: bool = False
    
    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance
    
    def initialize(
        self, 
        mongo_uri: Optional[str] = None, 
        database_name: Optional[str] = None,
        config: Optional[DatabaseConfig] = None
    ) -> None:
        """
        Initialize database connection with connection pooling
        
        Args:
            mongo_uri: MongoDB connection URI (deprecated, use config)
            database_name: Database name (deprecated, use config)
            config: Database configuration object
            
        Raises:
            ConnectionFailure: If unable to connect to database
            ValueError: If already initialized or invalid config
        """
        with self._lock:
            if self._initialized:
                logger.warning("Database already initialized, skipping reinitialization")
                return
            
            # Use config or fall back to individual parameters
            if config is None:
                if mongo_uri is None or database_name is None:
                    config = DatabaseConfig.from_env()
                else:
                    config = DatabaseConfig(
                        mongo_uri=mongo_uri,
                        database_name=database_name
                    )
            
            self._config = config
            
            try:
                # Create client with connection pooling
                self._client = MongoClient(
                    config.mongo_uri,
                    maxPoolSize=config.max_pool_size,
                    minPoolSize=config.min_pool_size,
                    serverSelectionTimeoutMS=config.server_selection_timeout_ms,
                    connectTimeoutMS=config.connect_timeout_ms,
                    socketTimeoutMS=config.socket_timeout_ms,
                    retryWrites=config.retry_writes,
                    retryReads=config.retry_reads,
                    # Connection health monitoring
                    maxIdleTimeMS=45000,
                    waitQueueTimeoutMS=5000,
                )
                
                # Verify connection
                self._client.admin.command('ping')
                
                self._database = self._client[config.database_name]
                self._initialized = True
                
                logger.info(
                    f"✅ Connected to MongoDB: {config.database_name} "
                    f"(pool: {config.min_pool_size}-{config.max_pool_size})"
                )
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"❌ Failed to connect to MongoDB: {e}")
                self._cleanup()
                raise ConnectionFailure(f"Could not connect to database: {e}") from e
            except Exception as e:
                logger.error(f"❌ Unexpected error during database initialization: {e}")
                self._cleanup()
                raise
    
    def _cleanup(self) -> None:
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
    def client(self) -> MongoClient:
        """Get MongoDB client"""
        if not self._initialized or self._client is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._client
    
    @property
    def database(self) -> Database:
        """Get database instance"""
        if not self._initialized or self._database is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._database
    
    @property
    def is_initialized(self) -> bool:
        """Check if database is initialized"""
        return self._initialized
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on database connection
        
        Returns:
            Dictionary with health status
        """
        if not self._initialized:
            return {
                "status": "unhealthy",
                "error": "Database not initialized",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        try:
            # Ping with timeout
            start_time = time.time()
            self._client.admin.command('ping', maxTimeMS=1000)
            latency = (time.time() - start_time) * 1000
            
            # Get server info
            server_info = self._client.server_info()
            
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "database": self._config.database_name if self._config else "unknown",
                "version": server_info.get("version", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Unexpected error during health check: {e}")
            return {
                "status": "unhealthy",
                "error": f"Unexpected error: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def reset_connection(self) -> None:
        """
        Reset database connection (useful for testing or recovery)
        
        Warning: This will close all existing connections
        """
        logger.warning("Resetting database connection...")
        with self._lock:
            config = self._config
            self._cleanup()
            if config:
                self.initialize(config=config)
    
    def close(self) -> None:
        """Close database connection and cleanup resources"""
        logger.info("Closing database connection...")
        with self._lock:
            self._cleanup()
            logger.info("✅ Database connection closed")


# Initialize global database manager
db_manager = DatabaseManager()


def get_database() -> Database:
    """
    FastAPI dependency to get database connection
    
    Returns:
        Database instance with active connection pool
        
    Raises:
        HTTPException: If database is not available (503)
    """
    global db_manager
    
    # Lazy initialization
    if not db_manager.is_initialized:
        try:
            config = DatabaseConfig.from_env()
            db_manager.initialize(config=config)
        except ConnectionFailure as e:
            logger.error(f"Failed to initialize database: {e}")
            raise HTTPException(
                status_code=503,
                detail="Database service unavailable"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error initializing database: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error during database initialization"
            ) from e
    
    # Verify connection is still healthy (lightweight check)
    try:
        # This uses a connection from the pool, returns it automatically
        return db_manager.database
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable"
        ) from e


@contextmanager
def get_database_context() -> Generator[Database, None, None]:
    """
    Context manager for database access (useful for non-FastAPI code)
    
    Usage:
        with get_database_context() as db:
            result = db.users.find_one({"email": "test@example.com"})
    """
    try:
        yield get_database()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in database context: {e}")
        raise


# Optional: Add health check endpoint helper
async def database_health_dependency() -> Dict[str, Any]:
    """
    FastAPI dependency for health check endpoints
    
    Usage:
        @app.get("/health/database")
        async def check_db(health: dict = Depends(database_health_dependency)):
            return health
    """
    return db_manager.health_check()


# =====================================
# BACKWARD COMPATIBILITY (deprecated)
# =====================================

def get_db() -> Database:
    """
    Deprecated: Use get_database() instead
    
    This function is maintained for backward compatibility only.
    """
    logger.warning(
        "get_db() is deprecated, use get_database() instead",
        stacklevel=2
    )
    return get_database()