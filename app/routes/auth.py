from fastapi import APIRouter, HTTPException, Request, Body, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
import requests
import os
import logging
import time,json
import hashlib
import secrets
from pymongo import ReturnDocument

from datetime import datetime, timedelta,timezone
from typing import Optional, Dict, Any
import asyncio
from bson import ObjectId
from contextlib import asynccontextmanager
from services.system_config import SystemConfigService
from services.user_service import RegistrationRequest

# Monitoring and metrics
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import structlog

# Security imports
from cryptography.fernet import Fernet
import jwt
from passlib.context import CryptContext
import redis
from services.audit import AuditService
# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Services

# from utils.db import  #users, request.app.state.db.audit_logs
from dotenv import load_dotenv
# Import Dramatiq actors
load_dotenv()

# --------------------------
# Configuration & Security Setup
# --------------------------
KRATOS_PUBLIC_URL = os.getenv("KRATOS_PUBLIC_URL", "http://kratos:4433")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode()).strip()
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "90"))
ENFORCE_STRICT_PWD_POLICY = bool(os.getenv("ENFORCE_STRICT_PWD_POLICY", False))

def make_redis_url(host=None, port=None, db=None, password=None):
    redis_host = host or os.getenv("REDIS_HOST", "localhost")
    redis_port = int(port or os.getenv("REDIS_PORT", 6379))
    redis_db = int(db or os.getenv("REDIS_DB", 0))
    redis_password = password or os.getenv("REDIS_PASSWORD", None)

    if redis_password:
        return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        return f"redis://{redis_host}:{redis_port}/{redis_db}"
    
# Security context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)
fernet = Fernet(ENCRYPTION_KEY.encode())

# Rate limiting
# request.app.state.redis_client = redis.from_url(REDIS_URL)

limiter = Limiter(key_func=get_remote_address, storage_uri=make_redis_url())

# Structured logging
logger = structlog.get_logger()



# --------------------------
# Enhanced Schemas
# --------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    terms_accepted: bool = False
    marketing_consent: bool = False
    preferred_language:Optional[str]="en"
    
    @validator('password')
    def validate_password(cls, v):
        if not ENFORCE_STRICT_PWD_POLICY:
            return v
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
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


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False
    device_fingerprint: Optional[str] = None


class OTPLoginRequest(BaseModel):
    phone: str
    code: str
    device_fingerprint: Optional[str] = None


# --------------------------
# Security Utilities
# --------------------------
from cryptography.fernet import InvalidToken

class SecurityUtils:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return pwd_context.verify(password, hashed)
    
    @staticmethod
    def generate_session_token(user_id: str, remember_me: bool = False) -> str:
        expiry = datetime.now(timezone.utc) + (timedelta(days=30) if remember_me else timedelta(hours=24))
        payload = {
            "user_id": user_id,
            "exp": expiry,
            "iat": datetime.now(timezone.utc),
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
        try:
            return fernet.decrypt(encrypted_data.encode()).decode()
        except InvalidToken:
            raise ValueError(f"Invalid or corrupted encrypted data. Key mismatch? {ENCRYPTION_KEY}")
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")


# # --------------------------
# # Audit Logging
# # --------------------------
# class AuditLogger:
#     @staticmethod
#     async def log_event(
#         event_type: str,
#         user_id: Optional[str] = None,
#         ip_address: Optional[str] = None,
#         user_agent: Optional[str] = None,
#         details: Optional[Dict] = None,
#         severity: str = "info"
#     ):
#         audit_entry = {
#             "timestamp": datetime.now(timezone.utc).isoformat(),
#             "event_type": event_type,
#             "user_id": user_id,
#             "ip_address": ip_address,
#             "user_agent": user_agent,
#             "details": details or {},
#             "severity": severity,
#             "session_id": secrets.token_urlsafe(16)
#         }
        
#         # Store in database
#         request.app.state.db.audit_logs.insert_one(audit_entry)
        
#         # Log to structured logger
#         logger.info(
#             "audit_event",
#             event_type=event_type,
#             user_id=user_id,
#             severity=severity,
#             **audit_entry
#         )
        
#         # Update Prometheus metrics
#         security_events.labels(event_type=event_type, severity=severity).inc()


# --------------------------
# Security Middleware
# --------------------------
from utils.auth.permission_checker import SessionInfo,RoleType,create_memory_checker
checker = create_memory_checker(max_entries=20000, ttl_seconds=600)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None
) -> Dict[str, Any]:
 
    try:
        token_data = SecurityUtils.validate_session_token(credentials.credentials)
        client_ip = request.client.host
      
        # Check if session is still valid in Redis
        session_key = f"session:{token_data['jti']}"
        if not request.app.state.redis_client.exists(session_key):
            raise HTTPException(status_code=401, detail="Session expired")
        
        # Update last activity
        # request.app.state.redis_client.set(session_key, token_data['user_id'],86400)
        
        user = request.app.state.db.users.find_one_and_update(
                {"kratos_id": token_data["user_id"]},
                {
                    "$set": {
                        "activities.last_activity": datetime.now(timezone.utc).isoformat(),
                        "activities.last_login_ip": client_ip,
                    }
                },
                return_document=ReturnDocument.AFTER,  # return updated doc
                projection={"_id": 1,"name":1,
                            "email":1,"created_at":1,
                            "activities":1,"last_login":1,
                            "account_locked":1,
                            "is_verified":1,"role":1
                        }  # return only the _id
            )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return SessionInfo(
            user_id=str(user["_id"]),
            tenant_id=None,
            permissions= [],
            roles={
                RoleType.GLOBAL:user['role'],
            },  # role_type -> role_name
            metadata={
                **token_data,
                **user
            }
            
        )
    
  
    except Exception as e:
        await  AuditService.log_event(
            "authentication_failed",
            ip_address=request.client.host if request else None,
            details={"reason": str(e)},
            severity="warning"
        )
        u=SessionInfo(
            user_id="random",
            tenant_id=None,
            permissions= ["kunia"],
            roles={
                RoleType.GLOBAL:"guest",
            },  # role_type -> role_name
            metadata={
              
            }
            
        )
        await u.anonymous(request,request.get("uid"))
        return u
        raise


# --------------------------
# Router Setup
# --------------------------
router = APIRouter(prefix="/auth", tags=["auth"])


# --------------------------
# Enhanced Registration
# --------------------------
@router.post("/register")
@limiter.limit("20/minute")
async def register_user(request: Request, req: RegistrationRequest):
    start_time = time.time()
    client_ip = request.client.host
    
    try:
        with request.app.state.metrics.auth_request_duration.labels(endpoint='register').time():
            identity,session= await request.app.state.user_service.register_user(req,client_ip)
            return {
                "identity":identity,
                "session":session,
            }
           
    except HTTPException:
        request.app.state.metrics.auth_requests_total.labels(method='register', status='error', endpoint='register').inc()
        raise
    except Exception as e:
        request.app.state.metrics.auth_requests_total.labels(method='register', status='error', endpoint='register').inc()
        await  AuditService.log_event(
            "registration_system_error",
            ip_address=client_ip,
            details={"error": str(e)},
            severity="critical"
        )
        print(e)
        raise HTTPException(status_code=500, detail=f"Internal server error {e}")
            

# --------------------------
# Enhanced Login
# --------------------------
@router.post("/login")
@limiter.limit("10/minute")
async def login_user(request: Request, req: LoginRequest):
    client_ip = request.client.host
    user_agent = request.headers.get("User-Agent", "")
    
    try:
        with request.app.state.metrics.auth_request_duration.labels(endpoint='login').time():
            # Check rate limiting for this specific user
            user_rate_key = f"login_attempts:{req.email}"
            attempts = request.app.state.redis_client.get(user_rate_key)
            if attempts and int(attempts) >= 5:
                await  AuditService.log_event(
                    "login_rate_limited",
                    ip_address=client_ip,
                    details={"email": req.email},
                    severity="warning"
                )
                request.app.state.metrics.failed_login_attempts.labels(reason='rate_limited', source_ip=client_ip).inc()
                raise HTTPException(status_code=429, detail="Too many login attempts")
           
            # Check if account is locked
            user_doc = request.app.state.db.users.find_one({"email": req.email})
            if user_doc and user_doc.get("account_locked"):
                await  AuditService.log_event(
                    "login_attempt_locked_account",
                    user_id=user_doc.get("kratos_id"),
                    ip_address=client_ip,
                    details={"email": req.email},
                    severity="warning"
                )
                request.app.state.metrics.failed_login_attempts.labels(reason='account_locked', source_ip=client_ip).inc()
                raise HTTPException(status_code=423, detail="Account is locked")
            
            # Perform Kratos login
            flow_response = requests.get(f"{KRATOS_PUBLIC_URL}/self-service/login/api")
            flow = flow_response.json()
            flow_id = flow["id"]
            
            payload = {
                "method": "password",
                "identifier": req.email,
                "password": req.password,
            }
            
            login_response = requests.post(
                f"{KRATOS_PUBLIC_URL}/self-service/login?flow={flow_id}",
                json=payload,
            )
            
         
            if login_response.status_code == 401:
                # Increment failed attempts counter
                request.app.state.redis_client.incr(user_rate_key)
                request.app.state.redis_client.expire(user_rate_key, 900)  # 15 minutes
                
                # Update user failed attempts
                if user_doc:
                    failed_attempts = user_doc.get("failed_login_attempts", 0) + 1
                    update_data = {"failed_login_attempts": failed_attempts}
                    
                    # Lock account after 5 failed attempts
                    if failed_attempts >= 5:
                        update_data["account_locked"] = True
                        update_data["locked_at"] = datetime.now(timezone.utc).isoformat()
                    
                    request.app.state.db.users.update_one(
                        {"email": req.email},
                        {"$set": update_data}
                    )
                
                await  AuditService.log_event(
                    "login_failed",
                    user_id=user_doc.get("kratos_id") if user_doc else None,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={"email": req.email, "reason": "invalid_credentials"},
                    severity="warning"
                )
                
                request.app.state.metrics.failed_login_attempts.labels(reason='invalid_credentials', source_ip=client_ip).inc()
                raise HTTPException(status_code=401, detail="Invalid credentials")
            session_data = login_response.json()
            
            if  login_response.status_code == 400:
                await AuditService.log_event(
                        "login_denied",
                        user_id=user_doc.get("kratos_id") if user_doc else None,
                        ip_address=client_ip,
                        user_agent=user_agent,
                        details={"email": req.email, "reason": "email_not_verified"},
                        severity="info"
                    )
                details = (
                    session_data.get("ui", {})
                    .get("messages", [{}])[0]
                    .get("text", "Email not verified")
                )
                raise HTTPException(status_code=401, detail=details)
            
            user_id = session_data.get("session", {}).get("identity", {}).get("id")
           
            # Generate our own session token
            session_token = SecurityUtils.generate_session_token(user_id, req.remember_me)
            session_jti = jwt.decode(session_token, JWT_SECRET, algorithms=["HS256"])["jti"]
            
            # Store session in Redis
            session_key = f"session:{session_jti}"
            session_ttl = 86400 * 30 if req.remember_me else 86400  # 30 days or 1 day
            
            minimal = {
                "local_user_id":str(user_doc['_id']),
                "krato_user_id": user_id,
                "kratos_session_id": session_data["session"]["id"],
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            request.app.state.redis_client.set(session_key, json.dumps(minimal),session_ttl)
            
            
            tmp_id=ObjectId()
            # Reset failed attempts and unlock account
            request.app.state.db.users.update_one(
                {"email": req.email},
                {
                    "$set": {
                        "session":tmp_id,
                        "last_activity": datetime.now(timezone.utc).isoformat(),
                        "last_login": datetime.now(timezone.utc).isoformat(),
                        "last_login_ip": client_ip,
                        "failed_login_attempts": 0,
                        "account_locked": False
                    },
                    "$unset": {"locked_at": ""}
                }
            )
            
            # Clear rate limiting
            request.app.state.redis_client.delete(user_rate_key)
            
            # Update active sessions metric
            request.app.state.metrics.active_sessions.labels(tenant_id=user_id).inc()
            
            # Audit successful login
            await  AuditService.log_event(
                "user_login_success",
                user_id=user_id,
                ip_address=client_ip,
                user_agent=user_agent,
                details={
                    "tmp_id":str(tmp_id),
                    "email": req.email,
                    "remember_me": req.remember_me,
                    "device_fingerprint": req.device_fingerprint
                }
            )
            
            request.app.state.metrics.auth_requests_total.labels(method='login', status='success', endpoint='login').inc()
            user_name = session_data.get("session", {}).get("identity", {}).get("traits", {}).get("name")
            return {
                "msg": "Login successful",
                "access_token": session_token,
                "token_type": "bearer",
                "expires_in": session_ttl,
                "user": {
                    "user_id":str(tmp_id),
                    "name":user_name,
                    "plan":"starter"
                }
            }
            
    except HTTPException:
        request.app.state.metrics.auth_requests_total.labels(method='login', status='error', endpoint='login').inc()
        raise
    except Exception as e:
     
        request.app.state.metrics.auth_requests_total.labels(method='login', status='error', endpoint='login').inc()
        await  AuditService.log_event(
            "login_system_error",
            ip_address=client_ip,
            details={"error": str(e)},
            severity="critical"
        )
        raise HTTPException(status_code=500, detail=f"Internal server error {e}")

# --------------------------
# Enhanced Password Recovery
# --------------------------

@router.post("/verify-account")
@limiter.limit("5/minute")
async def verify_account(flow_id: str, email: EmailStr, code: str,request: Request):
    payload = {
        "method": "code",       # tells Kratos we’re verifying via code
        "email": email,
        "code": code
    }
    resp = requests.post(
        f"{KRATOS_PUBLIC_URL}/self-service/verification?flow={flow_id}&code={code}",
        json=payload
    )
    resp.raise_for_status()
    data= resp.text
    return {"text":data}
# --------------------------
# Enhanced Password Recovery
# --------------------------
@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, email: EmailStr):
    client_ip = request.client.host
    
    try:
        with request.app.state.metrics.auth_request_duration.labels(endpoint='forgot_password').time():
            # Rate limit password reset requests per email
            reset_key = f"password_reset:{email}"
            if request.app.state.redis_client.exists(reset_key):
                await  AuditService.log_event(
                    "password_reset_rate_limited",
                    ip_address=client_ip,
                    details={"email": email},
                    severity="warning"
                )
                raise HTTPException(status_code=429, detail="Password reset already requested")
            
            flow_response = requests.get(f"{KRATOS_PUBLIC_URL}/self-service/recovery/api")
            flow = flow_response.json()
            flow_id = flow["id"]
            
            payload = {"method": "link", "email": email}
            
            recovery_response = requests.post(
                f"{KRATOS_PUBLIC_URL}/self-service/recovery?flow={flow_id}",
                json=payload,
            )
            
            if recovery_response.status_code >= 400:
                await  AuditService.log_event(
                    "password_reset_failed",
                    ip_address=client_ip,
                    details={"email": email, "error": recovery_response.json()},
                    severity="error"
                )
                raise HTTPException(
                    status_code=recovery_response.status_code,
                    detail=recovery_response.json()
                )
            
            # Set rate limit for 15 minutes
            request.app.state.redis_client.setex(reset_key, 900, "1")
            
            # Audit password reset request
            await  AuditService.log_event(
                "password_reset_requested",
                ip_address=client_ip,
                details={"email": email}
            )
            
            request.app.state.metrics.auth_requests_total.labels(method='password_reset', status='success', endpoint='forgot_password').inc()
            
            return {"msg": "If the email exists, a recovery link has been sent"}
            
    except HTTPException:
        request.app.state.metrics.auth_requests_total.labels(method='password_reset', status='error', endpoint='forgot_password').inc()
        raise
    except Exception as e:
        request.app.state.metrics.auth_requests_total.labels(method='password_reset', status='error', endpoint='forgot_password').inc()
        await  AuditService.log_event(
            "password_reset_system_error",
            ip_address=client_ip,
            details={"error": str(e)},
            severity="critical"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# --------------------------
# Enhanced Social Login
# --------------------------
@router.get("/login/social/{provider}")
@limiter.limit("10/minute")
async def login_social(request: Request, provider: str):
    client_ip = request.client.host
    
    # Validate provider
    allowed_providers = ["google", "github", "facebook", "microsoft"]
    if provider not in allowed_providers:
        await  AuditService.log_event(
            "social_login_invalid_provider",
            ip_address=client_ip,
            details={"provider": provider},
            severity="warning"
        )
        raise HTTPException(status_code=400, detail="Invalid social provider")
    
    try:
        flow_response = requests.get(f"{KRATOS_PUBLIC_URL}/self-service/login/api")
        flow = flow_response.json()
        flow_id = flow["id"]
        
        await  AuditService.log_event(
            "social_login_initiated",
            ip_address=client_ip,
            details={"provider": provider, "flow_id": flow_id}
        )
        
        request.app.state.metrics.auth_requests_total.labels(method='social', status='success', endpoint='social_login').inc()
        
        return {
            "login_flow_id": flow_id,
            "redirect_url": f"{KRATOS_PUBLIC_URL}/self-service/methods/oidc/{provider}?flow={flow_id}"
        }
        
    except Exception as e:
        request.app.state.metrics.auth_requests_total.labels(method='social', status='error', endpoint='social_login').inc()
        await  AuditService.log_event(
            "social_login_system_error",
            ip_address=client_ip,
            details={"error": str(e), "provider": provider},
            severity="critical"
        )
        raise HTTPException(status_code=500, detail="Social login service unavailable")


# --------------------------
# Enhanced WhoAmI
# --------------------------
@router.get("/me")
async def whoami(request: Request, current_user: SessionInfo = Depends(get_current_user)):
    try:
        
        with request.app.state.metrics.auth_request_duration.labels(endpoint='whoami').time():
            print(current_user)
            user_info = {
                "user_id": current_user.metadata.get("tmp_id"),
                "email": current_user.metadata["email"],
                "name": current_user.metadata['name'],
                "created_at": current_user.metadata["created_at"],
                "last_login": current_user.metadata.get("last_login"),
            }
            
            request.app.state.metrics.auth_requests_total.labels(method='whoami', status='success', endpoint='whoami').inc()
            return user_info
            
    except HTTPException:
        request.app.state.metrics.auth_requests_total.labels(method='whoami', status='error', endpoint='whoami').inc()
        raise
    except Exception as e:
        print(f"err {e}")
        request.app.state.metrics.auth_requests_total.labels(method='whoami', status='error', endpoint='whoami').inc()
        raise HTTPException(status_code=500, detail="Failed to retrieve user information")


# --------------------------
# Enhanced Logout
# --------------------------
@router.post("/logout")
async def logout(request: Request, current_user: Dict = Depends(get_current_user)):
    client_ip = request.client.host
    
    try:
        # Invalidate session in Redis
        session_key = f"session:{current_user['jti']}"
        request.app.state.redis_client.delete(session_key)
        
        # Decrement active sessions
        request.app.state.metrics.active_sessions.dec()
        
        # Audit logout
        await  AuditService.log_event(
            "user_logout",
            user_id=current_user["user_id"],
            ip_address=client_ip,
            details={"session_id": current_user["jti"]}
        )
        
        request.app.state.metrics.auth_requests_total.labels(method='logout', status='success', endpoint='logout').inc()
        
        return {"msg": "Successfully logged out"}
        
    except Exception as e:
        request.app.state.metrics.auth_requests_total.labels(method='logout', status='error', endpoint='logout').inc()
        await  AuditService.log_event(
            "logout_system_error",
            user_id=current_user["user_id"],
            ip_address=client_ip,
            details={"error": str(e)},
            severity="error"
        )
        raise HTTPException(status_code=500, detail="Logout failed")


# --------------------------
# Admin Endpoints
# --------------------------
@router.get("/admin/audit-logs")
@checker.require_role("admin",error_message="You don’t have the required role (Admin) to perform this action.")
async def audit_logs(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = 100,
    skip: int = 0,
    event_type: Optional[str] = None,
    severity: Optional[str] = None
):
    # TODO: Add admin role check
    
    query = {}
    if event_type:
        query["event_type"] = event_type
    if severity:
        query["severity"] = severity
    
    logs = list(request.app.state.db.audit_logs.find(query,{"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit))
    
    return {
        "logs": logs,
        "total": request.app.state.db.audit_logs.count_documents(query),
        "page": skip // limit + 1
    }


@router.post("/admin/unlock-account")
@checker.require_role("admin",error_message="You don’t have the required role (Admin) to perform this action.")
async def unlock_account(
    request: Request,
    email: EmailStr,
    current_user: Dict = Depends(get_current_user)
):
    # TODO: Add admin role check
    
    request.app.state.db.users.update_one(
        {"email": email},
        {
            "$set": {"account_locked": False, "failed_login_attempts": 0},
            "$unset": {"locked_at": ""}
        }
    )
    
    await  AuditService.log_event(
        "account_unlocked_by_admin",
        user_id=current_user["user_id"],
        ip_address=request.client.host,
        details={"target_email": email}
    )
    
    return {"msg": "Account unlocked successfully"}


# --------------------------
# Metrics Endpoint
# --------------------------
@router.get("/metrics")
async def get_metrics():
    return generate_latest().decode()


# --------------------------
# Health Check
# --------------------------
@router.get("/health")
async def health_check(request: Request):
    try:
        # Check Kratos connectivity
        kratos_health = requests.get(f"{KRATOS_PUBLIC_URL}/health/ready", timeout=5)
        kratos_ok = kratos_health.status_code == 200
        lago_service = request.app.state.lago_service.health_check()
        lago_ok = True if "message" in lago_service and lago_service["message"]=="Success" else False
        # Check Redis connectivity
        redis_ok = request.app.state.redis_client.ping()
        
        # Check database connectivity
        db_ok = request.app.state.db.command("ping")
        
        overall_health = kratos_ok and redis_ok and db_ok and lago_ok
        
        return {
            "status": "healthy" if overall_health else "unhealthy",
            "services": {
                "kratos": "up" if kratos_ok else "down",
                "redis": "up" if redis_ok else "down",
                "database": "up" if db_ok else "down",
                "billing": "up" if lago_ok else "down",
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# --------------------------
# Cleanup Tasks (Background)
# --------------------------
async def cleanup_expired_audits(db):
    """Remove audit logs older than retention period"""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=AUDIT_RETENTION_DAYS)
    result = db.audit_logs.delete_many({
        "timestamp": {"$lt": cutoff_date.isoformat()}
    })
    
    logger.info(f"Cleaned up {result.deleted_count} expired audit logs")


async def cleanup_expired_sessions(db):
    """Remove expired sessions from Redis"""
    # This would be handled by Redis TTL, but we can add additional cleanup logic
    pass