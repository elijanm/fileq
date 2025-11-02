from typing import Dict, Any, Optional,Union
from fastapi import Request, Depends, HTTPException, Body
import time
import logging
from pymongo.database import Database
import os
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import user_agents
import hashlib
import secrets
from utils.db import get_database,Database
from metrics.metrics import get_metrics
from metrics.metrics import MetricsCollector
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
from services.rbac_services import UserPermissionService, RoleService, PermissionService
from typing import List
import requests
# Monitoring and metrics
import structlog

# Security imports
from cryptography.fernet import Fernet
import jwt
from passlib.context import CryptContext
import redis

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


logger = structlog.get_logger()


#Configuration & Security Setup
# --------------------------
KRATOS_PUBLIC_URL = os.getenv("KRATOS_PUBLIC_URL", "http://kratos:4433")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key())
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "90"))

# Security context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
fernet = Fernet(ENCRYPTION_KEY)

# Rate limiting
redis_client = redis.from_url(REDIS_URL)
limiter = Limiter(key_func=get_remote_address, storage_uri=REDIS_URL)

# Structured logging
logger = structlog.get_logger()

# =====================================
# CLIENT INFO EXTRACTOR
# =====================================

@dataclass
class ClientInfo:
    ip_address: str
    user_agent: str
    country: Optional[str]
    city: Optional[str]
    is_mobile: bool
    browser: str
    os: str
    device: str
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False
    device_fingerprint: Optional[str] = None


class OTPLoginRequest(BaseModel):
    phone: str
    code: str
    device_fingerprint: Optional[str] = None
    

def get_client_info(request: Request) -> Dict[str, Any]:
    """Extract client information from request"""
    
    # Get IP address (handle proxies and load balancers)
    ip_address = get_real_ip(request)
    
    # Parse user agent
    user_agent_string = request.headers.get("User-Agent", "")
    ua = user_agents.parse(user_agent_string)
    
    # Basic client info
    client_info = {
        "ip_address": ip_address,
        "user_agent": user_agent_string,
        "is_mobile": ua.is_mobile,
        "browser": f"{ua.browser.family} {ua.browser.version_string}",
        "os": f"{ua.os.family} {ua.os.version_string}",
        "device": ua.device.family,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Add geolocation info if available (you'd integrate with a GeoIP service)
    geo_info = get_geolocation(ip_address)
    if geo_info:
        client_info.update(geo_info)
    
    return client_info

def get_real_ip(request: Request) -> str:
    """Extract real IP address from request headers"""
    # Check common proxy headers in order of preference
    headers_to_check = [
        "CF-Connecting-IP",      # Cloudflare
        "X-Forwarded-For",       # Standard proxy header
        "X-Real-IP",             # Nginx proxy
        "X-Forwarded",           # Less common
        "Forwarded-For",         # Less common
        "Forwarded"              # RFC 7239
    ]
    
    for header in headers_to_check:
        ip = request.headers.get(header)
        if ip:
            # X-Forwarded-For can contain multiple IPs, take the first one
            if "," in ip:
                ip = ip.split(",")[0].strip()
            
            # Validate IP address
            try:
                ipaddress.ip_address(ip.strip())
                return ip.strip()
            except ValueError:
                continue
    
    # Fallback to client host
    return request.client.host if request.client else "unknown"


def get_geolocation(ip_address: str) -> Optional[Dict[str, str]]:
    """Get geolocation info for IP address (placeholder - integrate with GeoIP service)"""
    # This is a placeholder. In production, you'd integrate with:
    # - MaxMind GeoIP2
    # - IP2Location
    # - ipstack
    # - etc.
    
    try:
        # Example integration with a hypothetical GeoIP service
        # import geoip2.database
        # reader = geoip2.database.Reader('/path/to/GeoLite2-City.mmdb')
        # response = reader.city(ip_address)
        # return {
        #     "country": response.country.name,
        #     "city": response.city.name,
        #     "region": response.subdivisions.most_specific.name,
        #     "postal_code": response.postal.code,
        #     "latitude": float(response.location.latitude),
        #     "longitude": float(response.location.longitude)
        # }
        
        # For now, return None (no geo data)
        return None
        
    except Exception as e:
        logger.warning(f"Failed to get geolocation for IP {ip_address}: {str(e)}")
        return None


# =====================================
# USER SERVICE
# =====================================



class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    terms_accepted: bool = False
    marketing_consent: bool = False
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('terms_accepted')
    def validate_terms(cls, v):
        if not v:
            raise ValueError('Terms and conditions must be accepted')
        return v

class UserService:
    """Enhanced user service with RBAC integration"""
    
    def __init__(self, db: Database, metrics: MetricsCollector):
        self.db = db
        self.metrics = metrics
        self.users = db.users
        self.tenant_users = db.tenant_users
        self.audit_logs = db.audit_logs
        
        # Initialize RBAC services
        self.permission_service = UserPermissionService(db)
        self.role_service = RoleService(db)
    
    async def register_user(
        self, 
        registration_request: RegisterRequest,
        ip_address: str
    ) -> Dict[str, Any]:
        """Register a new user"""
        start_time = time.time()
        
        try:
            # Check if this is the first user (auto-promotion to superadmin)
            await self._handle_first_user_promotion(registration_request.email)
            
            # Create user in Kratos (external identity provider)
            kratos_result = await self._create_kratos_identity(registration_request)
            
            # Create user in our database
            user_doc = {
                "email": registration_request.email,
                "kratos_id": kratos_result["identity_id"],
                "lago_customer_id": None,
                "external_id": None,
                "name": registration_request.name,  # Should be encrypted in production
                "global_role": await self._determine_initial_role(registration_request.email),
                "primary_tenant_id": None,
                "is_system_user": False,
                "global_permissions": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None,
                "last_login": None,
                "last_login_ip": None,
                "failed_login_attempts": 0,
                "account_locked": False,
                "locked_at": None,
                "locked_by": None,
                "lock_reason": None,
                "terms_accepted": registration_request.terms_accepted,
                "marketing_consent": registration_request.marketing_consent,
                "registration_ip": ip_address,
                "status": "pending_verification",
                "is_verified": False,
                "verification_token": None,
                "password_reset_token": None,
                "password_reset_expires": None,
                "preferences": {
                    "theme": "light",
                    "email_notifications": True,
                    "dashboard_layout": "default"
                },
                "referral_code": self._generate_referral_code(),
                "referred_by": registration_request.referral_code,
                "referral_count": 0
            }
            
            result = self.users.insert_one(user_doc)
            
            # Log audit event
            await self._log_audit_event(
                "user_registered",
                kratos_result["identity_id"],
                None,
                None,
                {
                    "email": registration_request.email,
                    "registration_ip": ip_address,
                    "terms_accepted": registration_request.terms_accepted
                }
            )
            
            # Record metrics
            duration = time.time() - start_time
            self.metrics.record_registration(None, "success")
            self.metrics.db_operation_duration.labels(
                operation="insert",
                collection="users"
            ).observe(duration)
            
            return {
                "user_id": kratos_result["identity_id"],
                "email": registration_request.email,
                "status": "pending_verification",
                "verification_required": True
            }
            
        except Exception as e:
            self.metrics.record_registration(None, "error")
            logger.error(f"User registration failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Registration failed")
    


# =====================================
# TENANT SERVICE
# =====================================

class TenantService:
    """Service for tenant management"""
    
    def __init__(self, db: Database, metrics: MetricsCollector):
        self.db = db
        self.metrics = metrics
        self.tenants = db.tenants
        self.tenant_users = db.tenant_users
    
    async def _add_user_to_tenant(
        self, 
        tenant_id: str, 
        user_id: str, 
        role: str = "user",
        invited_by: Optional[str] = None
    ) -> bool:
        """Add user to tenant with specified role"""
        try:
            tenant_user_doc = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "role": role,
                "status": "active",
                "permissions": [],
                "custom_role_id": None,
                "invited_by": invited_by,
                "invited_at": datetime.now(timezone.utc).isoformat() if invited_by else None,
                "joined_at": datetime.now(timezone.utc).isoformat(),
                "last_accessed": None,
                "access_granted_by": invited_by,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None
            }
            
            result = self.tenant_users.insert_one(tenant_user_doc)
            return result.inserted_id is not None
            
        except Exception as e:
            logger.error(f"Failed to add user {user_id} to tenant {tenant_id}: {str(e)}")
            return False

def get_tenant_service(
    db: Database = Depends(get_database),
    metrics: MetricsCollector = Depends(get_metrics)
) -> TenantService:
    """Dependency to get tenant service"""
    return TenantService(db, metrics)

# --------------------------
# Security Utilities
# --------------------------
import re
class SecurityUtils:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)
    
    @staticmethod
    def validate_password_strength(password: str, min_length: int = 8) -> bool:
        """
        Validate password strength:
        - At least `min_length` chars
        - Contains lowercase, uppercase, number, and special char
        """
        if len(password) < min_length:
            return False

        if not re.search(r"[a-z]", password):
            return False

        if not re.search(r"[A-Z]", password):
            return False

        if not re.search(r"\d", password):
            return False

        if not re.search(r"[@$!%*?&#]", password):
            return False

        return True
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return pwd_context.verify(password, hashed)
    
    @staticmethod
    def generate_session_token(user_id: str, remember_me: bool = False) -> str:
        expiry = datetime.utcnow() + (timedelta(days=30) if remember_me else timedelta(hours=24))
        payload = {
            "user_id": user_id,
            "exp": expiry,
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(16)
        }
        return jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    
    @staticmethod
    def validate_session_token(token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    @staticmethod
    def encrypt_sensitive_data(data: str) -> str:
        return fernet.encrypt(data.encode()).decode()
    
    @staticmethod
    def decrypt_sensitive_data(encrypted_data: str) -> str:
        return fernet.decrypt(encrypted_data.encode()).decode()


# --------------------------
# Audit Logging
# --------------------------

class AuditLogger:
    @staticmethod
    async def log_event(
        event_type: Union[str, List[str]],
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict] = None,
        severity: str = "info",
        db: Database = None,
        metrics: MetricsCollector = None
    ):
        try:
            # Normalize to list for consistency
            if isinstance(event_type, str):
                event_types = [event_type]
            else:
                event_types = event_type

            audit_entries = []
            for et in event_types:
                entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event_type": et,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "details": details or {},
                    "severity": severity,
                    "session_id": secrets.token_urlsafe(16),
                }
                audit_entries.append(entry)

                # Structured logger
                logger.info(
                    "audit_event",
                    event_type_=et,
                    **entry
                )

                # Metrics
                if metrics is not None:
                    metrics.security_events.labels(
                        tenant_id=tenant_id,
                        event_type=et,
                        severity=severity
                    ).inc()

            # Insert batch into Mongo if available
            if db is not None:
                db.audit_logs.insert_many(audit_entries)

        except Exception as e:
            print(e)
            logger.error("audit_log_failed", error=str(e))
       


# --------------------------
# Security Middleware
# --------------------------
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None
) -> Dict[str, Any]:
    try:
        token_data = SecurityUtils.validate_session_token(credentials.credentials)
        
        # Check if session is still valid in Redis
        session_key = f"session:{token_data['jti']}"
        if not redis_client.exists(session_key):
            raise HTTPException(status_code=401, detail="Session expired")
        
        # Update last activity
        redis_client.setex(session_key, 86400, token_data['user_id'])
        
        return token_data
    except Exception as e:
        await AuditLogger.log_event(
            "authentication_failed",
            ip_address=request.client.host if request else None,
            details={"reason": str(e)},
            severity="warning"
        )
        raise

# =====================================
# TENANT CONTEXT EXTRACTOR
# =====================================

# def get_tenant_context(request: Request) -> Optional[str]:
#     """Extract tenant context from request"""
    
#     # Method 1: Check subdomain
#     host = request.headers.get("host", "")
#     if host:
#         # Extract subdomain (e.g., "acme.yourapp.com" -> "acme")
#         parts = host.split(".")
#         if len(parts) > 2:  # subdomain.domain.tld
#             subdomain = parts[0]
#             # Look up tenant by subdomain
#             # This would typically be cached for performance
#             # tenant = get_tenant_by_subdomain(subdomain)
#             # return str(tenant["_id"]) if tenant else None
    
#     # Method 2: Check custom domain
#     # tenant = get_tenant_by_domain(host)
#     # if tenant:
#     #     return str(tenant["_id"])
    
#     # Method 3: Check header (for API requests)
#     tenant_id = request.headers.get("X-Tenant-ID")
#     if tenant_id:
#         return tenant_id
    
#     # Method 4: Check query parameter
#     tenant_id = request.query_params.get("tenant_id")
#     if tenant_id:
#         return tenant_id
    
#     # No tenant context found
#     return None


# =====================================
# STARTUP CONFIGURATION
# =====================================

def setup_auth_dependencies():
    """Setup function to initialize all dependencies"""
    
    # Initialize database connection
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DATABASE", "auth_db")
    # db_manager.initialize(mongo_uri, db_name)
    
    logger.info("Authentication dependencies initialized")
    
# Example usage in your main FastAPI app:
# 
# from fastapi import FastAPI
# from auth_dependencies import setup_auth_dependencies
# 
# app = FastAPI()
# 
# @app.on_event("startup")
# async def startup_event():
#     setup_auth_dependencies()