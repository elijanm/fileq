# redis_client.py - Improved Redis client implementation

import redis
from redis.asyncio import Redis as AsyncRedis
from redis.asyncio import ConnectionPool as AsyncConnectionPool
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
    RedisError
)
import json
import logging
from typing import Any, Optional, Dict, List, Union, Set, AsyncGenerator
from datetime import datetime, timedelta
from dataclasses import dataclass
import os
from fastapi import Depends, HTTPException
from contextlib import asynccontextmanager, contextmanager
from threading import Lock

logger = logging.getLogger(__name__)

# =====================================
# CONFIGURATION
# =====================================

@dataclass
class RedisConfig:
    """Redis configuration"""
    host: str
    port: int
    db: int = 0
    password: Optional[str] = None
    decode_responses: bool = True
    max_connections: int = 50
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    
    @classmethod
    def from_env(cls) -> "RedisConfig":
        """Create configuration from environment variables"""
        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD"),
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
            socket_timeout=int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
        )
    
    def validate(self) -> None:
        """Validate configuration"""
        if not self.host:
            raise ValueError("Redis host cannot be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError(f"Invalid Redis port: {self.port}")
        if self.max_connections < 1:
            raise ValueError("max_connections must be at least 1")


# =====================================
# REDIS CLIENT
# =====================================

class RedisClient:
    """Redis client with connection pooling and common operations"""
    
    def __init__(self, config: RedisConfig):
        """
        Initialize Redis client
        
        Args:
            config: Redis configuration object
        """
        config.validate()
        self.config = config
        
        # Connection pool for better performance
        self.pool = redis.ConnectionPool(
            host=config.host,
            port=config.port,
            db=config.db,
            password=config.password,
            decode_responses=config.decode_responses,
            max_connections=config.max_connections,
            socket_timeout=config.socket_timeout,
            socket_connect_timeout=config.socket_connect_timeout,
            retry_on_timeout=config.retry_on_timeout,
            health_check_interval=config.health_check_interval,
        )
        
        self._client: Optional[redis.Redis] = None
        self._is_connected: bool = False
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance (lazy initialization)"""
        if self._client is None:
            self._client = redis.Redis(connection_pool=self.pool)
            self._is_connected = True
        return self._client
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._is_connected and self._client is not None
    
    def ping(self) -> bool:
        """Test Redis connection"""
        try:
            return self.client.ping()
        except (RedisConnectionError, RedisTimeoutError) as e:
            logger.error(f"Redis ping failed: {e}")
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Redis ping: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check
        
        Returns:
            Health status dictionary
        """
        try:
            start_time = datetime.now()
            ping_result = self.client.ping()
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            info = self.client.info("server")
            
            return {
                "status": "healthy" if ping_result else "unhealthy",
                "latency_ms": round(latency, 2),
                "host": self.config.host,
                "port": self.config.port,
                "db": self.config.db,
                "version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    # =====================================
    # BASIC KEY-VALUE OPERATIONS
    # =====================================
    
    def set(
        self, 
        key: str, 
        value: Any, 
        ex: Optional[int] = None, 
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
        serialize: bool = True
    ) -> bool:
        """
        Set a key-value pair with optional expiration
        
        Args:
            key: The key
            value: The value to store
            ex: Expiration time in seconds
            px: Expiration time in milliseconds
            nx: Only set if key doesn't exist
            xx: Only set if key exists
            serialize: Whether to JSON serialize complex types
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if serialize and not isinstance(value, (str, bytes, int, float)):
                value = json.dumps(value, default=str)
            
            result = self.client.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis SET failed for key '{key}': {e}")
            return False
    
    def get(self, key: str, deserialize: bool = True) -> Optional[Any]:
        """
        Get value by key
        
        Args:
            key: The key
            deserialize: Whether to JSON deserialize the value
            
        Returns:
            The value or None if not found
        """
        try:
            value = self.client.get(key)
            if value is None:
                return None
            
            if deserialize and isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            
            return value
        except Exception as e:
            logger.error(f"Redis GET failed for key '{key}': {e}")
            return None
    
    def delete(self, *keys: str) -> int:
        """Delete one or more keys"""
        try:
            return self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis DELETE failed for keys {keys}: {e}")
            return 0
    
    def exists(self, *keys: str) -> int:
        """Check if keys exist (returns count)"""
        try:
            return self.client.exists(*keys)
        except Exception as e:
            logger.error(f"Redis EXISTS failed for keys {keys}: {e}")
            return 0
    
    def expire(self, key: str, time: int) -> bool:
        """Set expiration time for a key in seconds"""
        try:
            return self.client.expire(key, time)
        except Exception as e:
            logger.error(f"Redis EXPIRE failed for key '{key}': {e}")
            return False
    
    def ttl(self, key: str) -> int:
        """
        Get time to live for a key
        
        Returns:
            Seconds until expiration, -1 if no expiration, -2 if key doesn't exist
        """
        try:
            return self.client.ttl(key)
        except Exception as e:
            logger.error(f"Redis TTL failed for key '{key}': {e}")
            return -2
    
    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment key by amount"""
        try:
            return self.client.incr(key, amount)
        except Exception as e:
            logger.error(f"Redis INCR failed for key '{key}': {e}")
            return None
    
    def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement key by amount"""
        try:
            return self.client.decr(key, amount)
        except Exception as e:
            logger.error(f"Redis DECR failed for key '{key}': {e}")
            return None
    
    # =====================================
    # HASH OPERATIONS
    # =====================================
    
    def hset(
        self, 
        name: str, 
        key: Optional[str] = None,
        value: Optional[Any] = None,
        mapping: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Set hash fields
        
        Args:
            name: Hash name
            key: Field name (for single field)
            value: Field value (for single field)
            mapping: Dictionary of field-value pairs
            
        Returns:
            Number of fields added
        """
        try:
            if mapping:
                # Serialize complex values
                serialized_mapping = {}
                for k, v in mapping.items():
                    if isinstance(v, (dict, list, tuple)):
                        serialized_mapping[k] = json.dumps(v, default=str)
                    else:
                        serialized_mapping[k] = v
                return self.client.hset(name, mapping=serialized_mapping)
            elif key is not None and value is not None:
                if isinstance(value, (dict, list, tuple)):
                    value = json.dumps(value, default=str)
                return self.client.hset(name, key, value)
            else:
                raise ValueError("Either provide key+value or mapping")
        except Exception as e:
            logger.error(f"Redis HSET failed for hash '{name}': {e}")
            return 0
    
    def hget(self, name: str, key: str, deserialize: bool = True) -> Optional[Any]:
        """Get hash field value"""
        try:
            value = self.client.hget(name, key)
            if value is None:
                return None
            
            if deserialize and isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            
            return value
        except Exception as e:
            logger.error(f"Redis HGET failed for hash '{name}', key '{key}': {e}")
            return None
    
    def hgetall(self, name: str, deserialize: bool = True) -> Dict[str, Any]:
        """Get all hash fields and values"""
        try:
            result = self.client.hgetall(name)
            if not deserialize:
                return result
            
            # Deserialize values
            deserialized = {}
            for k, v in result.items():
                if isinstance(v, str):
                    try:
                        deserialized[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        deserialized[k] = v
                else:
                    deserialized[k] = v
            
            return deserialized
        except Exception as e:
            logger.error(f"Redis HGETALL failed for hash '{name}': {e}")
            return {}
    
    def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields"""
        try:
            return self.client.hdel(name, *keys)
        except Exception as e:
            logger.error(f"Redis HDEL failed for hash '{name}': {e}")
            return 0
    
    def hexists(self, name: str, key: str) -> bool:
        """Check if hash field exists"""
        try:
            return self.client.hexists(name, key)
        except Exception as e:
            logger.error(f"Redis HEXISTS failed for hash '{name}', key '{key}': {e}")
            return False
    
    def hincrby(self, name: str, key: str, amount: int = 1) -> Optional[int]:
        """Increment hash field by amount"""
        try:
            return self.client.hincrby(name, key, amount)
        except Exception as e:
            logger.error(f"Redis HINCRBY failed for hash '{name}', key '{key}': {e}")
            return None
    
    # =====================================
    # LIST OPERATIONS
    # =====================================
    
    def lpush(self, name: str, *values: Any) -> int:
        """Push values to the left of a list"""
        try:
            serialized_values = [
                json.dumps(v, default=str) if isinstance(v, (dict, list, tuple)) else v
                for v in values
            ]
            return self.client.lpush(name, *serialized_values)
        except Exception as e:
            logger.error(f"Redis LPUSH failed for list '{name}': {e}")
            return 0
    
    def rpush(self, name: str, *values: Any) -> int:
        """Push values to the right of a list"""
        try:
            serialized_values = [
                json.dumps(v, default=str) if isinstance(v, (dict, list, tuple)) else v
                for v in values
            ]
            return self.client.rpush(name, *serialized_values)
        except Exception as e:
            logger.error(f"Redis RPUSH failed for list '{name}': {e}")
            return 0
    
    def lpop(self, name: str, count: Optional[int] = None, deserialize: bool = True) -> Optional[Any]:
        """Pop value(s) from the left of a list"""
        try:
            value = self.client.lpop(name, count)
            if value is None:
                return None
            
            if deserialize and isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            
            return value
        except Exception as e:
            logger.error(f"Redis LPOP failed for list '{name}': {e}")
            return None
    
    def rpop(self, name: str, count: Optional[int] = None, deserialize: bool = True) -> Optional[Any]:
        """Pop value(s) from the right of a list"""
        try:
            value = self.client.rpop(name, count)
            if value is None:
                return None
            
            if deserialize and isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            
            return value
        except Exception as e:
            logger.error(f"Redis RPOP failed for list '{name}': {e}")
            return None
    
    def lrange(self, name: str, start: int, end: int, deserialize: bool = True) -> List[Any]:
        """Get a range of elements from a list"""
        try:
            values = self.client.lrange(name, start, end)
            if not deserialize:
                return values
            
            return [
                json.loads(v) if isinstance(v, str) and self._is_json(v) else v
                for v in values
            ]
        except Exception as e:
            logger.error(f"Redis LRANGE failed for list '{name}': {e}")
            return []
    
    def llen(self, name: str) -> int:
        """Get the length of a list"""
        try:
            return self.client.llen(name)
        except Exception as e:
            logger.error(f"Redis LLEN failed for list '{name}': {e}")
            return 0
    
    def ltrim(self, name: str, start: int, end: int) -> bool:
        """Trim list to specified range"""
        try:
            return self.client.ltrim(name, start, end)
        except Exception as e:
            logger.error(f"Redis LTRIM failed for list '{name}': {e}")
            return False
    
    # =====================================
    # SET OPERATIONS
    # =====================================
    
    def sadd(self, name: str, *values: Any) -> int:
        """Add values to a set"""
        try:
            serialized_values = [
                json.dumps(v, default=str) if isinstance(v, (dict, list, tuple)) else v
                for v in values
            ]
            return self.client.sadd(name, *serialized_values)
        except Exception as e:
            logger.error(f"Redis SADD failed for set '{name}': {e}")
            return 0
    
    def srem(self, name: str, *values: Any) -> int:
        """Remove values from a set"""
        try:
            serialized_values = [
                json.dumps(v, default=str) if isinstance(v, (dict, list, tuple)) else v
                for v in values
            ]
            return self.client.srem(name, *serialized_values)
        except Exception as e:
            logger.error(f"Redis SREM failed for set '{name}': {e}")
            return 0
    
    def smembers(self, name: str, deserialize: bool = True) -> Set[Any]:
        """Get all members of a set"""
        try:
            members = self.client.smembers(name)
            if not deserialize:
                return members
            
            deserialized = set()
            for member in members:
                if isinstance(member, str) and self._is_json(member):
                    try:
                        # Note: dicts/lists can't be in sets, so this handles edge cases
                        deserialized.add(member)
                    except TypeError:
                        deserialized.add(member)
                else:
                    deserialized.add(member)
            
            return deserialized
        except Exception as e:
            logger.error(f"Redis SMEMBERS failed for set '{name}': {e}")
            return set()
    
    def sismember(self, name: str, value: Any) -> bool:
        """Check if value is a member of a set"""
        try:
            if isinstance(value, (dict, list, tuple)):
                value = json.dumps(value, default=str)
            return self.client.sismember(name, value)
        except Exception as e:
            logger.error(f"Redis SISMEMBER failed for set '{name}': {e}")
            return False
    
    def scard(self, name: str) -> int:
        """Get the number of members in a set"""
        try:
            return self.client.scard(name)
        except Exception as e:
            logger.error(f"Redis SCARD failed for set '{name}': {e}")
            return 0
    
    # =====================================
    # SORTED SET OPERATIONS
    # =====================================
    
    def zadd(self, name: str, mapping: Dict[Any, float], nx: bool = False, xx: bool = False) -> int:
        """Add members to sorted set"""
        try:
            return self.client.zadd(name, mapping, nx=nx, xx=xx)
        except Exception as e:
            logger.error(f"Redis ZADD failed for sorted set '{name}': {e}")
            return 0
    
    def zrem(self, name: str, *values: Any) -> int:
        """Remove members from sorted set"""
        try:
            return self.client.zrem(name, *values)
        except Exception as e:
            logger.error(f"Redis ZREM failed for sorted set '{name}': {e}")
            return 0
    
    def zcard(self, name: str) -> int:
        """Get the number of members in sorted set"""
        try:
            return self.client.zcard(name)
        except Exception as e:
            logger.error(f"Redis ZCARD failed for sorted set '{name}': {e}")
            return 0
    
    def zremrangebyscore(self, name: str, min_score: float, max_score: float) -> int:
        """Remove members by score range"""
        try:
            return self.client.zremrangebyscore(name, min_score, max_score)
        except Exception as e:
            logger.error(f"Redis ZREMRANGEBYSCORE failed for sorted set '{name}': {e}")
            return 0
    
    # =====================================
    # UTILITY METHODS
    # =====================================
    
    def keys(self, pattern: str = "*") -> List[str]:
        """
        Get keys matching pattern
        
        Warning: Use with caution in production (blocking operation)
        Consider using scan() for large datasets
        """
        try:
            return self.client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis KEYS failed for pattern '{pattern}': {e}")
            return []
    
    def scan(self, cursor: int = 0, match: Optional[str] = None, count: Optional[int] = None):
        """
        Scan keys incrementally (non-blocking alternative to keys())
        
        Returns:
            Tuple of (next_cursor, keys_list)
        """
        try:
            return self.client.scan(cursor=cursor, match=match, count=count)
        except Exception as e:
            logger.error(f"Redis SCAN failed: {e}")
            return (0, [])
    
    def pipeline(self, transaction: bool = True) -> Optional[redis.client.Pipeline]:
        """Get a pipeline for atomic operations"""
        try:
            return self.client.pipeline(transaction=transaction)
        except Exception as e:
            logger.error(f"Redis PIPELINE failed: {e}")
            return None
    
    def flushdb(self, asynchronous: bool = False) -> bool:
        """
        Clear current database
        
        Warning: Use with extreme caution!
        """
        try:
            return self.client.flushdb(asynchronous=asynchronous)
        except Exception as e:
            logger.error(f"Redis FLUSHDB failed: {e}")
            return False
    
    def info(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get Redis server information"""
        try:
            return self.client.info(section)
        except Exception as e:
            logger.error(f"Redis INFO failed: {e}")
            return {}
    
    def dbsize(self) -> int:
        """Get number of keys in current database"""
        try:
            return self.client.dbsize()
        except Exception as e:
            logger.error(f"Redis DBSIZE failed: {e}")
            return 0
    
    # =====================================
    # CACHING HELPERS
    # =====================================
    
    def cache_set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = 3600,
        namespace: str = "cache"
    ) -> bool:
        """Set cached value with namespace and TTL"""
        cache_key = f"{namespace}:{key}"
        return self.set(cache_key, value, ex=ttl)
    
    def cache_get(self, key: str, namespace: str = "cache") -> Optional[Any]:
        """Get cached value with namespace"""
        cache_key = f"{namespace}:{key}"
        return self.get(cache_key)
    
    def cache_delete(self, key: str, namespace: str = "cache") -> int:
        """Delete cached value with namespace"""
        cache_key = f"{namespace}:{key}"
        return self.delete(cache_key)
    
    def cache_exists(self, key: str, namespace: str = "cache") -> bool:
        """Check if cached value exists"""
        cache_key = f"{namespace}:{key}"
        return bool(self.exists(cache_key))
    
    def cache_get_or_set(
        self,
        key: str,
        value_func: callable,
        ttl: int = 3600,
        namespace: str = "cache"
    ) -> Any:
        """
        Get cached value or compute and cache it
        
        Args:
            key: Cache key
            value_func: Function to compute value if not cached
            ttl: Time to live in seconds
            namespace: Cache namespace
            
        Returns:
            Cached or computed value
        """
        cached_value = self.cache_get(key, namespace)
        if cached_value is not None:
            return cached_value
        
        value = value_func()
        self.cache_set(key, value, ttl, namespace)
        return value
    
    # =====================================
    # SESSION MANAGEMENT
    # =====================================
    
    def set_session(
        self, 
        session_id: str, 
        data: Dict[str, Any], 
        ttl: int = 86400
    ) -> bool:
        """Set session data (default TTL: 24 hours)"""
        return self.cache_set(session_id, data, ttl=ttl, namespace="session")
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return self.cache_get(session_id, namespace="session")
    
    def delete_session(self, session_id: str) -> int:
        """Delete session"""
        return self.cache_delete(session_id, namespace="session")
    
    def extend_session(self, session_id: str, ttl: int = 86400) -> bool:
        """Extend session expiration"""
        session_key = f"session:{session_id}"
        return self.expire(session_key, ttl)
    
    def update_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        ttl: int = 86400
    ) -> bool:
        """Update session data and refresh TTL"""
        session_key = f"session:{session_id}"
        existing = self.get_session(session_id) or {}
        existing.update(data)
        return self.set(session_key, existing, ex=ttl, serialize=True)
    
    # =====================================
    # RATE LIMITING
    # =====================================
    
    def rate_limit_check(
        self, 
        key: str, 
        limit: int, 
        window: int,
        namespace: str = "rate_limit"
    ) -> Dict[str, Any]:
        """
        Rate limiting using sliding window with sorted sets
        
        Args:
            key: Identifier (e.g., user_id, ip_address)
            limit: Maximum number of requests
            window: Time window in seconds
            namespace: Redis key namespace
            
        Returns:
            Dictionary with allowed status and metadata
        """
        try:
            rate_key = f"{namespace}:{key}"
            current_time = datetime.now().timestamp()
            window_start = current_time - window
            
            # Use pipeline for atomic operations
            pipe = self.client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(rate_key, 0, window_start)
            
            # Count current requests
            pipe.zcard(rate_key)
            
            # Add current request
            pipe.zadd(rate_key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(rate_key, window + 1)
            
            results = pipe.execute()
            current_count = results[1]  # Result of zcard
            
            if current_count >= limit:
                # Get oldest timestamp for reset time calculation
                oldest_entry = self.client.zrange(rate_key, 0, 0, withscores=True)
                reset_time = int(oldest_entry[0][1] + window) if oldest_entry else int(current_time + window)
                
                return {
                    "allowed": False,
                    "count": current_count,
                    "limit": limit,
                    "remaining": 0,
                    "reset_time": reset_time,
                    "retry_after": max(0, reset_time - int(current_time))
                }
            
            return {
                "allowed": True,
                "count": current_count + 1,
                "limit": limit,
                "remaining": limit - current_count - 1,
                "reset_time": int(current_time + window),
                "retry_after": 0
            }
            
        except Exception as e:
            logger.error(f"Rate limit check failed for key '{key}': {e}")
            # Fail open: allow request on error
            return {
                "allowed": True,
                "count": 0,
                "limit": limit,
                "remaining": limit,
                "reset_time": 0,
                "retry_after": 0,
                "error": str(e)
            }
    
    def rate_limit_reset(self, key: str, namespace: str = "rate_limit") -> bool:
        """Reset rate limit for a key"""
        rate_key = f"{namespace}:{key}"
        try:
            return bool(self.delete(rate_key))
        except Exception as e:
            logger.error(f"Rate limit reset failed for key '{key}': {e}")
            return False
    
    # =====================================
    # HELPER METHODS
    # =====================================
    
    @staticmethod
    def _is_json(value: str) -> bool:
        """Check if string is valid JSON"""
        try:
            json.loads(value)
            return True
        except (json.JSONDecodeError, TypeError):
            return False
    
    def __getattr__(self, name: str) -> Any:
        """
        Delegate undefined methods to underlying Redis client
        
        This allows direct access to redis-py methods not explicitly wrapped
        """
        if self._client is None:
            raise AttributeError(f"Redis client not initialized. Call .client first.")
        return getattr(self._client, name)
    
    def close(self) -> None:
        """Close Redis connection and cleanup resources"""
        try:
            if self._client:
                self._client.close()
            if self.pool:
                self.pool.disconnect()
            self._is_connected = False
            logger.info("✅ Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


# =====================================
# SINGLETON REDIS MANAGER
# =====================================

class RedisManager:
    """Thread-safe singleton Redis connection manager"""
    
    _instance: Optional["RedisManager"] = None
    _lock: Lock = Lock()
    _client: Optional[RedisClient] = None
    _config: Optional[RedisConfig] = None
    _initialized: bool = False
    
    def __new__(cls) -> "RedisManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(RedisManager, cls).__new__(cls)
        return cls._instance
    
    def initialize(
        self, 
        config: Optional[RedisConfig] = None,
        **kwargs
    ) -> None:
        """
        Initialize Redis client
        
        Args:
            config: RedisConfig object (preferred)
            **kwargs: Individual config parameters (deprecated, use config)
        """
        with self._lock:
            if self._initialized:
                logger.warning("Redis already initialized, skipping reinitialization")
                return
            
            # Use config or create from kwargs/env
            # Use config or create from kwargs/env
            if config is None:
                if kwargs:
                    config = RedisConfig(**kwargs)
                else:
                    config = RedisConfig.from_env()
            
            self._config = config
            
            try:
                self._client = RedisClient(config)
                
                # Test connection
                if self._client.ping():
                    self._initialized = True
                    logger.info(
                        f"✅ Connected to Redis: {config.host}:{config.port} "
                        f"(db: {config.db}, pool: {config.max_connections})"
                    )
                else:
                    raise RedisConnectionError("Failed to ping Redis server")
                    
            except (RedisConnectionError, RedisTimeoutError) as e:
                logger.error(f"❌ Failed to connect to Redis: {e}")
                self._cleanup()
                raise RedisConnectionError(f"Could not connect to Redis: {e}") from e
            except Exception as e:
                logger.error(f"❌ Unexpected error during Redis initialization: {e}")
                self._cleanup()
                raise
    
    def _cleanup(self) -> None:
        """Internal cleanup method"""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.error(f"Error during Redis cleanup: {e}")
        self._client = None
        self._config = None
        self._initialized = False
    
    @property
    def client(self) -> RedisClient:
        """Get Redis client (lazy initialization)"""
        if not self._initialized or self._client is None:
            self.initialize()
        return self._client
    
    @property
    def is_initialized(self) -> bool:
        """Check if Redis is initialized"""
        return self._initialized
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on Redis connection"""
        if not self._initialized:
            return {
                "status": "unhealthy",
                "error": "Redis not initialized",
                "timestamp": datetime.utcnow().isoformat()
            }
        return self._client.health_check()
    
    def reset_connection(self) -> None:
        """
        Reset Redis connection (useful for recovery)
        
        Warning: This will close all existing connections
        """
        logger.warning("Resetting Redis connection...")
        with self._lock:
            config = self._config
            self._cleanup()
            if config:
                self.initialize(config=config)
    
    def close(self) -> None:
        """Close Redis connection and cleanup resources"""
        logger.info("Closing Redis connection...")
        with self._lock:
            self._cleanup()
            logger.info("✅ Redis connection closed")


# Global Redis manager instance
redis_manager = RedisManager()


# =====================================
# FASTAPI DEPENDENCIES
# =====================================

def get_redis_client() -> RedisClient:
    """
    FastAPI dependency to get Redis client
    
    Returns:
        RedisClient instance with active connection pool
        
    Raises:
        HTTPException: If Redis is not available (503)
    
    Usage:
        @app.get("/items/{item_id}")
        async def get_item(
            item_id: str,
            redis: RedisClient = Depends(get_redis_client)
        ):
            cached = redis.get(f"item:{item_id}")
            if cached:
                return cached
            # ... fetch from database
    """
    global redis_manager
    
    # Lazy initialization
    if not redis_manager.is_initialized:
        try:
            redis_manager.initialize()
        except (RedisConnectionError, RedisTimeoutError) as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise HTTPException(
                status_code=503,
                detail="Redis service unavailable"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error initializing Redis: {e}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error during Redis initialization"
            ) from e
    
    # Verify connection is healthy
    try:
        if not redis_manager.client.ping():
            raise RedisConnectionError("Redis ping failed")
        return redis_manager.client
    except Exception as e:
        logger.error(f"Redis connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Redis temporarily unavailable"
        ) from e


def get_redis_health() -> Dict[str, Any]:
    """
    FastAPI dependency for health check endpoints
    
    Usage:
        @app.get("/health/redis")
        async def check_redis(health: dict = Depends(get_redis_health)):
            return health
    """
    return redis_manager.health_check()


# =====================================
# CONTEXT MANAGERS
# =====================================

@contextmanager
def redis_context():
    """
    Context manager for Redis access (useful for non-FastAPI code)
    
    Usage:
        with redis_context() as redis:
            redis.set("key", "value")
            value = redis.get("key")
    """
    try:
        yield get_redis_client()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Redis context: {e}")
        raise


@contextmanager
def redis_pipeline_context(transaction: bool = True):
    """
    Context manager for Redis pipeline operations
    
    Usage:
        with redis_pipeline_context() as pipe:
            pipe.set("key1", "value1")
            pipe.set("key2", "value2")
            pipe.incr("counter")
            results = pipe.execute()
    """
    redis_client = get_redis_client()
    pipe = redis_client.pipeline(transaction=transaction)
    
    try:
        yield pipe
        pipe.execute()
    except Exception as e:
        logger.error(f"Redis pipeline failed: {e}")
        pipe.reset()
        raise
    finally:
        pipe.reset()


# =====================================
# ASYNC REDIS CLIENT (Optional)
# =====================================

class AsyncRedisClient:
    """
    Async Redis client for high-performance async operations
    
    Note: This requires redis.asyncio which is available in redis-py >= 4.2.0
    """
    
    def __init__(self, config: RedisConfig):
        """Initialize async Redis client"""
        config.validate()
        self.config = config
        
        self.pool = AsyncConnectionPool(
            host=config.host,
            port=config.port,
            db=config.db,
            password=config.password,
            decode_responses=config.decode_responses,
            max_connections=config.max_connections,
            socket_timeout=config.socket_timeout,
            socket_connect_timeout=config.socket_connect_timeout,
        )
        
        self._client: Optional[AsyncRedis] = None
    
    async def get_client(self) -> AsyncRedis:
        """Get async Redis client instance"""
        if self._client is None:
            self._client = AsyncRedis(connection_pool=self.pool)
        return self._client
    
    async def ping(self) -> bool:
        """Test Redis connection"""
        try:
            client = await self.get_client()
            return await client.ping()
        except Exception as e:
            logger.error(f"Async Redis ping failed: {e}")
            return False
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ex: Optional[int] = None,
        serialize: bool = True
    ) -> bool:
        """Async set operation"""
        try:
            if serialize and not isinstance(value, (str, bytes, int, float)):
                value = json.dumps(value, default=str)
            
            client = await self.get_client()
            result = await client.set(key, value, ex=ex)
            return bool(result)
        except Exception as e:
            logger.error(f"Async Redis SET failed for key '{key}': {e}")
            return False
    
    async def get(self, key: str, deserialize: bool = True) -> Optional[Any]:
        """Async get operation"""
        try:
            client = await self.get_client()
            value = await client.get(key)
            
            if value is None:
                return None
            
            if deserialize and isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            
            return value
        except Exception as e:
            logger.error(f"Async Redis GET failed for key '{key}': {e}")
            return None
    
    async def delete(self, *keys: str) -> int:
        """Async delete operation"""
        try:
            client = await self.get_client()
            return await client.delete(*keys)
        except Exception as e:
            logger.error(f"Async Redis DELETE failed: {e}")
            return 0
    
    async def close(self) -> None:
        """Close async Redis connection"""
        try:
            if self._client:
                await self._client.close()
            await self.pool.disconnect()
            logger.info("✅ Async Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing async Redis connection: {e}")


# =====================================
# UTILITY FUNCTIONS
# =====================================

def setup_redis(config: Optional[RedisConfig] = None) -> RedisClient:
    """
    Setup function to initialize Redis connection
    
    Args:
        config: Optional RedisConfig object
        
    Returns:
        Initialized RedisClient
        
    Usage:
        # In your startup code
        redis_client = setup_redis()
    """
    redis_manager.initialize(config=config)
    
    # Test connection
    if redis_manager.client.ping():
        logger.info("✅ Redis connection established successfully")
    else:
        logger.error("❌ Redis connection failed")
    
    return redis_manager.client


def create_redis_key(namespace: str, *parts: str) -> str:
    """
    Create namespaced Redis key
    
    Args:
        namespace: Key namespace
        *parts: Key parts to join
        
    Returns:
        Formatted Redis key
        
    Example:
        >>> create_redis_key("user", "123", "profile")
        'user:123:profile'
    """
    all_parts = [namespace] + list(parts)
    return ":".join(str(part) for part in all_parts)


def parse_redis_key(key: str) -> List[str]:
    """
    Parse Redis key into parts
    
    Args:
        key: Redis key string
        
    Returns:
        List of key parts
        
    Example:
        >>> parse_redis_key("user:123:profile")
        ['user', '123', 'profile']
    """
    return key.split(":")


# =====================================
# DECORATORS
# =====================================

def redis_cache(
    ttl: int = 3600,
    namespace: str = "cache",
    key_prefix: Optional[str] = None
):
    """
    Decorator to cache function results in Redis
    
    Args:
        ttl: Cache TTL in seconds
        namespace: Redis namespace
        key_prefix: Optional key prefix
        
    Usage:
        @redis_cache(ttl=300, key_prefix="user_data")
        def get_user_data(user_id: str) -> dict:
            # Expensive operation
            return fetch_from_database(user_id)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [func.__name__]
            if key_prefix:
                key_parts.insert(0, key_prefix)
            
            # Add args to key
            key_parts.extend(str(arg) for arg in args)
            
            # Add sorted kwargs to key
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            
            cache_key = ":".join(key_parts)
            
            # Try to get from cache
            redis_client = get_redis_client()
            cached_value = redis_client.cache_get(cache_key, namespace=namespace)
            
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_value
            
            # Compute value
            logger.debug(f"Cache miss for key: {cache_key}")
            value = func(*args, **kwargs)
            
            # Store in cache
            redis_client.cache_set(cache_key, value, ttl=ttl, namespace=namespace)
            
            return value
        
        return wrapper
    return decorator


# =====================================
# BACKWARD COMPATIBILITY (deprecated)
# =====================================

def get_redis() -> RedisClient:
    """
    Deprecated: Use get_redis_client() instead
    
    This function is maintained for backward compatibility only.
    """
    logger.warning(
        "get_redis() is deprecated, use get_redis_client() instead",
        stacklevel=2
    )
    return get_redis_client()


# =====================================
# USAGE EXAMPLES
# =====================================

if __name__ == "__main__":
    # Example 1: Basic usage
    config = RedisConfig.from_env()
    redis_client = setup_redis(config)
    
    # Basic operations
    redis_client.set("test_key", {"message": "Hello Redis!"}, ex=300)
    value = redis_client.get("test_key")
    print(f"Retrieved: {value}")
    
    # Example 2: Caching
    redis_client.cache_set("user:123", {"name": "John", "email": "john@example.com"}, ttl=3600)
    user_data = redis_client.cache_get("user:123")
    print(f"User data: {user_data}")
    
    # Example 3: Rate limiting
    result = redis_client.rate_limit_check("api:user:123", limit=10, window=60)
    print(f"Rate limit result: {result}")
    
    # Example 4: Session management
    redis_client.set_session("session123", {"user_id": "123", "role": "admin"}, ttl=86400)
    session = redis_client.get_session("session123")
    print(f"Session: {session}")
    
    # Example 5: Pipeline operations
    with redis_pipeline_context() as pipe:
        pipe.set("key1", "value1")
        pipe.set("key2", "value2")
        pipe.incr("counter")
        results = pipe.execute()
        print(f"Pipeline results: {results}")
    
    # Example 6: Using decorator
    @redis_cache(ttl=300, key_prefix="expensive")
    def expensive_operation(user_id: str) -> dict:
        print(f"Computing expensive operation for {user_id}")
        return {"result": f"data_for_{user_id}"}
    
    # First call - cache miss
    result1 = expensive_operation("123")
    print(f"First call: {result1}")
    
    # Second call - cache hit
    result2 = expensive_operation("123")
    print(f"Second call: {result2}")
    
    # Health check
    health = redis_client.health_check()
    print(f"Health: {health}")
    
    # Cleanup
    redis_manager.close()