"""
Improved JWT Authentication implementation for Ory Kratos integration
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
import httpx
import jwt
import structlog
import tenacity
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from pydantic import BaseModel, validator
from pydantic_settings import BaseSettings
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

# Import our auth utilities
from services.auth import AuthUtilities

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
redis_db = int(os.getenv("REDIS_DB", 0))
admin_url = os.getenv("KRATOS_ADMIN_URL", "http://127.0.0.1:8717")
public_url = os.getenv("KRATOS_PUBLIC_URL", "http://127.0.0.1:4433")
redis_password = os.getenv("REDIS_PASSWORD",None)
# Configuration
class AuthConfig(BaseSettings):
    """Authentication configuration with environment variable support"""
    kratos_public_url: str = public_url
    kratos_admin_url: str = admin_url
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "RS256"
    jwks_cache_ttl: int = 300  # 5 minutes
    session_cache_ttl: int = 60  # 1 minute
    redis_url: str = f"redis://:{redis_password}@{redis_host}:{redis_port}"
    http_timeout: float = 10.0
    http_connect_timeout: float = 5.0
    max_connections: int = 100
    max_keepalive_connections: int = 20
    retry_attempts: int = 3
    retry_min_wait: int = 1
    retry_max_wait: int = 10
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,  # same as old case_sensitive=False
        "extra": "ignore",        # ignore unknown keys
    }
    

    def validate_required_vars(self):
        """Validate that required environment variables are set"""
        required_vars = ["kratos_public_url", "kratos_admin_url"]
        missing = [var for var in required_vars if not getattr(self, var)]
        if missing:
            raise ValueError(f"Missing required configuration: {missing}")

config = AuthConfig()
config.validate_required_vars()

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Security
security = HTTPBearer()

# Models
class SessionInfo(BaseModel):
    """User session information"""
    user_id: str
    tenant_id: Optional[str]
    permissions: List[str]
    roles: Dict[str, Any]

class TokenRequest(BaseModel):
    """Token validation request"""
    token: str
    
    @validator('token')
    def validate_token_format(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Invalid token format')
        return v

# Cache implementations
class AsyncCache:
    """Redis-based async cache implementation using redis.asyncio"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        if not self.redis:
            self.redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis.ping()
    
    async def get(self, key: str) -> Optional[dict]:
        """Get value from cache"""
        try:
            await self.connect()
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.warning("cache_get_failed", key=key, error=str(e))
            return None
    
    async def set(self, key: str, value: dict, ttl: int = 300):
        """Set value in cache with TTL"""
        try:
            await self.connect()
            await self.redis.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning("cache_set_failed", key=key, error=str(e))
    
    async def delete(self, key: str):
        """Delete key from cache"""
        try:
            await self.connect()
            await self.redis.delete(key)
        except Exception as e:
            logger.warning("cache_delete_failed", key=key, error=str(e))
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.aclose()

class JWKSManager:
    """Manages JWKS fetching and caching with background refresh"""
    
    def __init__(self, kratos_url: str, http_client: httpx.AsyncClient, cache: AsyncCache):
        self.kratos_url = kratos_url
        self.http_client = http_client
        self.cache = cache
        self.jwks_cache_key = "kratos_jwks"
        self.last_fetch_key = "kratos_jwks_last_fetch"
        self.refresh_task: Optional[asyncio.Task] = None
        self.refresh_lock = asyncio.Lock()
    
    async def get_jwks(self) -> Dict[str, Any]:
        """Get JWKS with automatic refresh"""
        jwks = await self.cache.get(self.jwks_cache_key)
        
        if jwks is None or await self._should_refresh():
            async with self.refresh_lock:
                # Double-check after acquiring lock
                jwks = await self.cache.get(self.jwks_cache_key)
                if jwks is None or await self._should_refresh():
                    jwks = await self._fetch_jwks()
        
        return jwks
    
    async def _should_refresh(self) -> bool:
        """Check if JWKS should be refreshed"""
        last_fetch = await self.cache.get(self.last_fetch_key)
        if not last_fetch:
            return True
        
        last_fetch_time = datetime.fromisoformat(last_fetch["timestamp"])
        return datetime.now(timezone.utc) - last_fetch_time > timedelta(minutes=4)
    
    @tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
    )
    async def _fetch_jwks(self) -> Dict[str, Any]:
        """Fetch JWKS from Kratos"""
        try:
            response = await self.http_client.get(f"{self.kratos_url}/.well-known/jwks.json")
            response.raise_for_status()
            jwks = response.json()
            
            # Cache JWKS and timestamp
            await self.cache.set(self.jwks_cache_key, jwks, config.jwks_cache_ttl)
            await self.cache.set(
                self.last_fetch_key,
                {"timestamp": datetime.now(timezone.utc).isoformat()},
                config.jwks_cache_ttl
            )
            
            logger.info("jwks_fetched_successfully", url=self.kratos_url)
            return jwks
            
        except httpx.TimeoutException:
            logger.error("kratos_jwks_timeout", url=self.kratos_url)
            raise HTTPException(status_code=503, detail="Authentication service timeout")
        except httpx.RequestError as e:
            logger.error("kratos_jwks_request_failed", url=self.kratos_url, error=str(e))
            raise HTTPException(status_code=503, detail="Authentication service unavailable")
        except Exception as e:
            logger.error("kratos_jwks_fetch_failed", url=self.kratos_url, error=str(e))
            raise HTTPException(status_code=503, detail="Authentication service error")

class JWTValidator:
    """Handles JWT token validation"""
    
    def __init__(self, jwks_manager: JWKSManager):
        self.jwks_manager = jwks_manager
    
    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate JWT token using Kratos JWKS"""
        try:
            # Get JWKS for signature verification
            jwks = await self.jwks_manager.get_jwks()
            
            # Decode token header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            key_id = unverified_header.get('kid')
            
            if not key_id:
                logger.warning("jwt_no_key_id")
                return None
            
            # Find the right key in JWKS
            signing_key = None
            for key in jwks.get('keys', []):
                if key.get('kid') == key_id:
                    signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                    break
            
            if not signing_key:
                logger.warning("jwt_signing_key_not_found", key_id=key_id)
                return None
            
            # Validate and decode JWT
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=[config.jwt_algorithm],
                options={"verify_exp": True, "verify_aud": False}
            )
            
            logger.info("jwt_validation_successful", user_id=payload.get('sub'))
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("jwt_token_expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("jwt_invalid_token", error=str(e))
            return None
        except Exception as e:
            logger.error("jwt_validation_error", error=str(e))
            return None

class KratosAuthenticator:
    """Handles authentication with Ory Kratos"""
    
    def __init__(self, auth_utils: AuthUtilities, config: AuthConfig):
        self.auth_utils = auth_utils
        self.config = config
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.http_timeout, connect=config.http_connect_timeout),
            limits=httpx.Limits(
                max_connections=config.max_connections,
                max_keepalive_connections=config.max_keepalive_connections
            )
        )
        self.cache = AsyncCache(config.redis_url)
        self.jwks_manager = JWKSManager(config.kratos_public_url, self.http_client, self.cache)
        self.jwt_validator = JWTValidator(self.jwks_manager)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()
        await self.cache.close()
    
    def _get_secure_cache_key(self, token: str, prefix: str = "session") -> str:
        """Generate secure cache key from token"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return f"{prefix}_{token_hash[:16]}"
    
    @tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=config.retry_min_wait, max=config.retry_max_wait),
        stop=tenacity.stop_after_attempt(config.retry_attempts),
        retry=tenacity.retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
    )
    async def validate_session_token(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Validate session token with Kratos whoami endpoint"""
        cache_key = self._get_secure_cache_key(session_token, "session")
        
        # Check cache first
        cached_session = await self.cache.get(cache_key)
        if cached_session:
            logger.debug("session_cache_hit", cache_key=cache_key[:8])
            return cached_session
        
        try:
            headers = {"Authorization": f"Bearer {session_token}"}
            response = await self.http_client.get(
                f"{self.config.kratos_public_url}/sessions/whoami",
                headers=headers
            )
            
            if response.status_code == 200:
                session_data = response.json()
                await self.cache.set(cache_key, session_data, self.config.session_cache_ttl)
                logger.info("session_validation_successful", user_id=session_data.get('identity', {}).get('id'))
                return session_data
            elif response.status_code == 401:
                logger.warning("session_validation_unauthorized")
                return None
            else:
                logger.error("kratos_whoami_error", status_code=response.status_code, response_text=response.text)
                return None
                
        except httpx.TimeoutException:
            logger.error("kratos_session_timeout")
            return None
        except httpx.RequestError as e:
            logger.error("kratos_session_request_failed", error=str(e))
            return None
        except Exception as e:
            logger.error("session_validation_error", error=str(e))
            return None
    
    async def validate_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate JWT token using Kratos JWKS"""
        return await self.jwt_validator.validate_token(token)
    
    @tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=config.retry_min_wait, max=config.retry_max_wait),
        stop=tenacity.stop_after_attempt(config.retry_attempts),
        retry=tenacity.retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
    )
    async def get_user_from_kratos(self, kratos_user_id: str) -> Optional[Dict[str, Any]]:
        """Get user details from Kratos Admin API"""
        try:
            response = await self.http_client.get(
                f"{self.config.kratos_admin_url}/admin/identities/{kratos_user_id}"
            )
            
            if response.status_code == 200:
                user_data = response.json()
                logger.info("kratos_user_fetched", user_id=kratos_user_id)
                return user_data
            else:
                logger.error("kratos_user_fetch_failed", user_id=kratos_user_id, status_code=response.status_code)
                return None
                
        except httpx.TimeoutException:
            logger.error("kratos_user_fetch_timeout", user_id=kratos_user_id)
            return None
        except httpx.RequestError as e:
            logger.error("kratos_user_fetch_request_failed", user_id=kratos_user_id, error=str(e))
            return None
        except Exception as e:
            logger.error("kratos_user_fetch_error", user_id=kratos_user_id, error=str(e))
            return None
    
    async def extract_user_info(self, auth_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract user information from Kratos auth data"""
        try:
            # Handle different Kratos response formats
            if 'identity' in auth_data:
                # Session-based authentication
                identity = auth_data['identity']
                user_id = identity['id']
                traits = identity.get('traits', {})
                email = traits.get('email')
                auth_method = "session"
            elif 'sub' in auth_data:
                # JWT-based authentication
                user_id = auth_data['sub']
                email = auth_data.get('email')
                auth_method = "jwt"
            else:
                logger.error("unknown_auth_data_format", auth_data_keys=list(auth_data.keys()))
                return None
            
            if not user_id:
                logger.error("no_user_id_in_auth_data")
                return None
            
            # Get user from our database
            user_doc = self.auth_utils.users.find_one({"kratos_id": user_id})
            if not user_doc:
                logger.error("user_not_found_in_database", user_id=user_id)
                return None
            
            user_info = {
                "kratos_id": user_id,
                "email": email or user_doc.get("email"),
                "global_role": user_doc.get("global_role", "user"),
                "is_verified": user_doc.get("is_verified", False),
                "account_locked": user_doc.get("account_locked", False),
                "status": user_doc.get("status", "active"),
                "auth_method": auth_method
            }
            
            logger.info("user_info_extracted", user_id=user_id, auth_method=auth_method)
            return user_info
            
        except Exception as e:
            logger.error("user_info_extraction_error", error=str(e))
            return None

# Simple dependency container replacement
class SimpleContainer:
    """Simple dependency container without external libraries"""
    
    def __init__(self):
        self._auth_utils = None
        self._kratos_auth = None
    
    def set_auth_utils(self, auth_utils):
        """Set auth utilities instance"""
        self._auth_utils = auth_utils
    
    def get_kratos_auth(self) -> KratosAuthenticator:
        """Get or create Kratos authenticator instance"""
        if self._kratos_auth is None:
            if self._auth_utils is None:
                raise HTTPException(
                    status_code=503, 
                    detail="Authentication not initialized"
                )
            self._kratos_auth = KratosAuthenticator(self._auth_utils, config)
        return self._kratos_auth

# Global container instance
container = SimpleContainer()

def get_authenticator() -> KratosAuthenticator:
    """Get Kratos authenticator instance"""
    return container.get_kratos_auth()

@limiter.limit("30/minute")
async def get_current_user(
    request,  # For rate limiting
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    authenticator: KratosAuthenticator = Depends(get_authenticator)
) -> SessionInfo:
    """
    Extract user information from JWT token or session token and validate with Kratos
    Supports both JWT tokens and Kratos session tokens
    """
    auth_start_time = datetime.now(timezone.utc)
    
    try:
        # Validate token format
        token_request = TokenRequest(token=credentials.credentials)
        token = token_request.token
        
        # First, try to validate as a Kratos session token
        auth_data = await authenticator.validate_session_token(token)
        auth_method = "session"
        
        # If session validation fails, try JWT validation
        if not auth_data:
            auth_data = await authenticator.validate_jwt_token(token)
            auth_method = "jwt"
        
        if not auth_data:
            logger.warning("authentication_failed", reason="invalid_token")
            raise HTTPException(
                status_code=401, 
                detail="Invalid or expired authentication token"
            )
        
        # Extract user information
        user_info = await authenticator.extract_user_info(auth_data)
        if not user_info:
            logger.warning("authentication_failed", reason="user_not_found")
            raise HTTPException(
                status_code=401,
                detail="User not found or inactive"
            )
        
        # Check if account is locked
        if user_info.get("account_locked"):
            logger.warning("authentication_failed", reason="account_locked", user_id=user_info["kratos_id"])
            raise HTTPException(
                status_code=403,
                detail="Account is locked"
            )
        
        # Check if account is active
        if user_info.get("status") != "active":
            logger.warning("authentication_failed", reason="inactive_account", 
                         user_id=user_info["kratos_id"], status=user_info.get("status"))
            raise HTTPException(
                status_code=403,
                detail=f"Account status: {user_info.get('status')}"
            )
        
        user_id = user_info["kratos_id"]
        
        # Get user permissions for the specified tenant
        permissions = authenticator.auth_utils.get_user_effective_permissions(
            user_id, 
            x_tenant_id
        )
        
        # Get user tenants and current tenant role
        user_tenants = []
        current_tenant_role = None
        
        if x_tenant_id:
            user_tenants = authenticator.auth_utils.get_user_tenants(user_id)
            for tenant in user_tenants:
                if str(tenant["_id"]) == x_tenant_id:
                    current_tenant_role = tenant.get("user_role")
                    break
            
            # Verify user has access to the requested tenant
            if not current_tenant_role:
                logger.warning("authentication_failed", reason="tenant_access_denied", 
                             user_id=user_id, tenant_id=x_tenant_id)
                raise HTTPException(
                    status_code=403,
                    detail="Access denied to specified tenant"
                )
        
        # Build roles information
        roles = {
            "global_role": user_info.get("global_role", "user"),
            "tenant_role": current_tenant_role
        }
        
        # Calculate authentication time
        auth_duration = (datetime.now(timezone.utc) - auth_start_time).total_seconds()
        
        # Log successful authentication
        authenticator.auth_utils.log_audit_event(
            "user_authenticated",
            user_id,
            {
                "tenant_id": x_tenant_id,
                "auth_method": auth_method,
                "permissions_count": len(permissions),
                "auth_duration_seconds": auth_duration
            },
            x_tenant_id
        )
        
        logger.info(
            "authentication_successful",
            user_id=user_id,
            tenant_id=x_tenant_id,
            auth_method=auth_method,
            permissions_count=len(permissions),
            auth_duration_seconds=auth_duration
        )
        
        return SessionInfo(
            user_id=user_id,
            tenant_id=x_tenant_id,
            permissions=permissions,
            roles=roles
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("authentication_error", error=str(e))
        raise HTTPException(
            status_code=401, 
            detail="Authentication failed"
        )

@limiter.limit("100/minute")
async def get_current_user_api_key(
    request,  # For rate limiting
    api_key: str = Header(None, alias="X-API-Key"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    authenticator: KratosAuthenticator = Depends(get_authenticator)
) -> SessionInfo:
    """
    Alternative authentication using API keys
    Useful for service-to-service communication
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required"
        )
    
    auth_start_time = datetime.now(timezone.utc)
    
    try:
        # Hash API key for secure logging
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:8]
        
        # Validate API key
        api_key_doc = authenticator.auth_utils.db.api_keys.find_one({
            "key": api_key,
            "status": "active",
            "expires_at": {"$gt": datetime.now(timezone.utc).isoformat()}
        })
        
        if not api_key_doc:
            logger.warning("api_key_authentication_failed", api_key_hash=api_key_hash)
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired API key"
            )
        
        user_id = api_key_doc["user_id"]
        
        # Check if API key has tenant restrictions
        if x_tenant_id and api_key_doc.get("tenant_id"):
            if str(api_key_doc["tenant_id"]) != x_tenant_id:
                logger.warning("api_key_tenant_mismatch", 
                             api_key_hash=api_key_hash, 
                             requested_tenant=x_tenant_id,
                             allowed_tenant=str(api_key_doc["tenant_id"]))
                raise HTTPException(
                    status_code=403,
                    detail="API key not valid for specified tenant"
                )
        
        # Get user permissions
        permissions = api_key_doc.get("permissions", [])
        if not permissions:
            permissions = authenticator.auth_utils.get_user_effective_permissions(
                user_id, 
                x_tenant_id
            )
        
        # Get user info
        user_doc = authenticator.auth_utils.users.find_one({"kratos_id": user_id})
        if not user_doc:
            logger.error("api_key_user_not_found", user_id=user_id, api_key_hash=api_key_hash)
            raise HTTPException(status_code=401, detail="User not found")
        
        # Check account status
        if user_doc.get("account_locked"):
            logger.warning("api_key_account_locked", user_id=user_id, api_key_hash=api_key_hash)
            raise HTTPException(status_code=403, detail="Account is locked")
        
        if user_doc.get("status") != "active":
            logger.warning("api_key_inactive_account", user_id=user_id, 
                         status=user_doc.get("status"), api_key_hash=api_key_hash)
            raise HTTPException(status_code=403, detail=f"Account status: {user_doc.get('status')}")
        
        roles = {
            "global_role": user_doc.get("global_role", "user"),
            "tenant_role": api_key_doc.get("role")
        }
        
        # Calculate authentication time
        auth_duration = (datetime.now(timezone.utc) - auth_start_time).total_seconds()
        
        # Log API key usage
        authenticator.auth_utils.log_audit_event(
            "api_key_used",
            user_id,
            {
                "api_key_id": str(api_key_doc["_id"]),
                "tenant_id": x_tenant_id,
                "permissions_count": len(permissions),
                "auth_duration_seconds": auth_duration
            },
            x_tenant_id
        )
        
        logger.info(
            "api_key_authentication_successful",
            user_id=user_id,
            api_key_id=str(api_key_doc["_id"]),
            tenant_id=x_tenant_id,
            permissions_count=len(permissions),
            auth_duration_seconds=auth_duration
        )
        
        return SessionInfo(
            user_id=user_id,
            tenant_id=x_tenant_id,
            permissions=permissions,
            roles=roles
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("api_key_authentication_error", error=str(e))
        raise HTTPException(
            status_code=401,
            detail="API key authentication failed"
        )

# Initialization function for your FastAPI app
def initialize_authentication(auth_utils: AuthUtilities):
    """Initialize authentication with auth utilities"""
    container.set_auth_utils(auth_utils)
    logger.info("authentication_initialized", 
                kratos_public_url=config.kratos_public_url,
                kratos_admin_url=config.kratos_admin_url)

# Health check for authentication service
async def auth_health_check() -> Dict[str, Any]:
    """Comprehensive health check for authentication services"""
    checks = {}
    overall_status = "healthy"
    
    # Check Kratos public endpoint
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start_time = datetime.now(timezone.utc)
            response = await client.get(f"{config.kratos_public_url}/health/ready")
            response_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            checks["kratos_public"] = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "response_time_seconds": response_time,
                # "url": config.kratos_public_url
            }
            
            if response.status_code != 200:
                overall_status = "unhealthy"
                
    except Exception as e:
        checks["kratos_public"] = {
            "status": "unhealthy",
            "error": str(e),
            # "url": config.kratos_public_url
        }
        overall_status = "unhealthy"
    
    # Check Kratos admin endpoint
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start_time = datetime.now(timezone.utc)
            response = await client.get(f"{config.kratos_admin_url}/admin/health/ready")
            response_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            checks["kratos_admin"] = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                # "response":response.text,
                "response_time_seconds": response_time,
                "url": config.kratos_admin_url
            }
            
            if response.status_code != 200:
                overall_status = "unhealthy"
                
    except Exception as e:
        checks["kratos_admin"] = {
            "status": "unhealthy",
            "error": str(e),
            "url": config.kratos_admin_url
        }
        overall_status = "unhealthy"
    
    # Check Redis connection
    try:
        cache = AsyncCache(config.redis_url)
        await cache.connect()
        await cache.set("health_check", {"timestamp": datetime.now(timezone.utc).isoformat()}, 10)
        test_value = await cache.get("health_check")
        await cache.close()
        
        checks["redis"] = {
            "status": "healthy" if test_value else "unhealthy",
            # "url": config.redis_url
        }
        
        if not test_value:
            overall_status = "degraded"
            
    except Exception as e:
        checks["redis"] = {
            "status": "unhealthy",
            "error": str(e),
            "url": config.redis_url
        }
        overall_status = "degraded"
    checks["overall_status"]=overall_status
    return {
        "overall_status":overall_status,
        "checks":checks
    }