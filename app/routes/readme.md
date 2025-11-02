from fastapi import APIRouter, HTTPException, Request, Body, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
import requests
import os
import logging
import time
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import asyncio
from contextlib import asynccontextmanager

# Monitoring and metrics

from prometheus_client import Counter, Histogram, Gauge, generate_latest
import structlog

# Security imports

from cryptography.fernet import Fernet
import jwt
from passlib.context import CryptContext
import redis

# Rate limiting

from slowapi import Limiter, \_rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Services

from services import lago_billing
from db import users, audit_logs

# --------------------------

# Configuration & Security Setup

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

# --------------------------

# Prometheus Metrics

# --------------------------

auth_requests_total = Counter(
'auth_requests_total',
'Total authentication requests',
['method', 'status', 'endpoint']
)

auth_request_duration = Histogram(
'auth_request_duration_seconds',
'Time spent processing authentication requests',
['endpoint']
)

active_sessions = Gauge(
'auth_active_sessions',
'Number of currently active sessions'
)

failed_login_attempts = Counter(
'auth_failed_login_attempts_total',
'Total failed login attempts',
['reason', 'source_ip']
)

security_events = Counter(
'auth_security_events_total',
'Security-related events',
['event_type', 'severity']
)

# --------------------------

# Enhanced Schemas

# --------------------------

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

class SecurityUtils:
@staticmethod
def hash_password(password: str) -> str:
return pwd_context.hash(password)

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
event_type: str,
user_id: Optional[str] = None,
ip_address: Optional[str] = None,
user_agent: Optional[str] = None,
details: Optional[Dict] = None,
severity: str = "info"
):
audit_entry = {
"timestamp": datetime.utcnow().isoformat(),
"event_type": event_type,
"user_id": user_id,
"ip_address": ip_address,
"user_agent": user_agent,
"details": details or {},
"severity": severity,
"session_id": secrets.token_urlsafe(16)
}

        # Store in database
        audit_logs.insert_one(audit_entry)

        # Log to structured logger
        logger.info(
            "audit_event",
            event_type=event_type,
            user_id=user_id,
            severity=severity,
            **audit_entry
        )

        # Update Prometheus metrics
        security_events.labels(event_type=event_type, severity=severity).inc()

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

# --------------------------

# Router Setup

# --------------------------

router = APIRouter(prefix="/auth", tags=["auth"])

# --------------------------

# Enhanced Registration

# --------------------------

@router.post("/register")
@limiter.limit("5/minute")
async def register_user(request: Request, req: RegisterRequest):
start_time = time.time()
client_ip = request.client.host

    try:
        with auth_request_duration.labels(endpoint='register').time():
            # Check if user already exists
            existing_user = users.find_one({"email": req.email})
            if existing_user:
                await AuditLogger.log_event(
                    "registration_attempt_duplicate_email",
                    ip_address=client_ip,
                    details={"email": req.email},
                    severity="warning"
                )
                raise HTTPException(status_code=400, detail="User already exists")

            # Step 1: Register in Kratos with enhanced security
            flow_response = requests.get(f"{KRATOS_PUBLIC_URL}/self-service/registration/api")
            if flow_response.status_code >= 400:
                raise HTTPException(status_code=500, detail="Authentication service unavailable")

            flow = flow_response.json()
            flow_id = flow["id"]

            payload = {
                "method": "password",
                "password": req.password,
                "traits": {
                    "email": req.email,
                    "name": req.name,
                    "terms_accepted": req.terms_accepted,
                    "marketing_consent": req.marketing_consent
                },
            }

            kratos_response = requests.post(
                f"{KRATOS_PUBLIC_URL}/self-service/registration?flow={flow_id}",
                json=payload,
            )

            if kratos_response.status_code >= 400:
                error_details = kratos_response.json()
                await AuditLogger.log_event(
                    "registration_failed_kratos",
                    ip_address=client_ip,
                    details={"error": error_details, "email": req.email},
                    severity="error"
                )
                raise HTTPException(status_code=kratos_response.status_code, detail=error_details)

            kratos_user = kratos_response.json()

            # Step 2: Create Lago customer with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    lago_customer = lago_billing.create_customer(
                        external_id=req.email,
                        name=req.name,
                        email=req.email
                    )
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        await AuditLogger.log_event(
                            "lago_customer_creation_failed",
                            ip_address=client_ip,
                            details={"error": str(e), "email": req.email},
                            severity="error"
                        )
                        raise HTTPException(status_code=500, detail="Billing service unavailable")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

            # Step 3: Store user data with encrypted sensitive information
            user_doc = {
                "email": req.email,
                "name": SecurityUtils.encrypt_sensitive_data(req.name),
                "kratos_id": kratos_user.get("id"),
                "lago_customer_id": lago_customer.get("customer", {}).get("lago_id"),
                "external_id": lago_customer.get("customer", {}).get("external_id"),
                "created_at": datetime.utcnow().isoformat(),
                "last_login": None,
                "failed_login_attempts": 0,
                "account_locked": False,
                "terms_accepted": req.terms_accepted,
                "marketing_consent": req.marketing_consent,
                "registration_ip": client_ip
            }

            users.insert_one(user_doc)

            # Audit log successful registration
            await AuditLogger.log_event(
                "user_registered",
                user_id=kratos_user.get("id"),
                ip_address=client_ip,
                details={
                    "email": req.email,
                    "lago_customer_id": lago_customer.get("customer", {}).get("lago_id")
                }
            )

            auth_requests_total.labels(method='register', status='success', endpoint='register').inc()

            return {
                "msg": "User registered successfully",
                "user_id": kratos_user.get("id"),
                "requires_verification": True
            }

    except HTTPException:
        auth_requests_total.labels(method='register', status='error', endpoint='register').inc()
        raise
    except Exception as e:
        auth_requests_total.labels(method='register', status='error', endpoint='register').inc()
        await AuditLogger.log_event(
            "registration_system_error",
            ip_address=client_ip,
            details={"error": str(e)},
            severity="critical"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

# --------------------------

# Enhanced Login

# --------------------------

@router.post("/login")
@limiter.limit("10/minute")
async def login_user(request: Request, req: LoginRequest):
client_ip = request.client.host
user_agent = request.headers.get("User-Agent", "")

    try:
        with auth_request_duration.labels(endpoint='login').time():
            # Check rate limiting for this specific user
            user_rate_key = f"login_attempts:{req.email}"
            attempts = redis_client.get(user_rate_key)
            if attempts and int(attempts) >= 5:
                await AuditLogger.log_event(
                    "login_rate_limited",
                    ip_address=client_ip,
                    details={"email": req.email},
                    severity="warning"
                )
                failed_login_attempts.labels(reason='rate_limited', source_ip=client_ip).inc()
                raise HTTPException(status_code=429, detail="Too many login attempts")

            # Check if account is locked
            user_doc = users.find_one({"email": req.email})
            if user_doc and user_doc.get("account_locked"):
                await AuditLogger.log_event(
                    "login_attempt_locked_account",
                    user_id=user_doc.get("kratos_id"),
                    ip_address=client_ip,
                    details={"email": req.email},
                    severity="warning"
                )
                failed_login_attempts.labels(reason='account_locked', source_ip=client_ip).inc()
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

            if login_response.status_code >= 400:
                # Increment failed attempts counter
                redis_client.incr(user_rate_key)
                redis_client.expire(user_rate_key, 900)  # 15 minutes

                # Update user failed attempts
                if user_doc:
                    failed_attempts = user_doc.get("failed_login_attempts", 0) + 1
                    update_data = {"failed_login_attempts": failed_attempts}

                    # Lock account after 5 failed attempts
                    if failed_attempts >= 5:
                        update_data["account_locked"] = True
                        update_data["locked_at"] = datetime.utcnow().isoformat()

                    users.update_one(
                        {"email": req.email},
                        {"$set": update_data}
                    )

                await AuditLogger.log_event(
                    "login_failed",
                    user_id=user_doc.get("kratos_id") if user_doc else None,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={"email": req.email, "reason": "invalid_credentials"},
                    severity="warning"
                )

                failed_login_attempts.labels(reason='invalid_credentials', source_ip=client_ip).inc()
                raise HTTPException(status_code=401, detail="Invalid credentials")

            session_data = login_response.json()
            user_id = session_data.get("identity", {}).get("id")

            # Generate our own session token
            session_token = SecurityUtils.generate_session_token(user_id, req.remember_me)
            session_jti = jwt.decode(session_token, JWT_SECRET, algorithms=["HS256"])["jti"]

            # Store session in Redis
            session_key = f"session:{session_jti}"
            session_ttl = 86400 * 30 if req.remember_me else 86400  # 30 days or 1 day
            redis_client.setex(session_key, session_ttl, user_id)

            # Reset failed attempts and unlock account
            users.update_one(
                {"email": req.email},
                {
                    "$set": {
                        "last_login": datetime.utcnow().isoformat(),
                        "last_login_ip": client_ip,
                        "failed_login_attempts": 0,
                        "account_locked": False
                    },
                    "$unset": {"locked_at": ""}
                }
            )

            # Clear rate limiting
            redis_client.delete(user_rate_key)

            # Update active sessions metric
            active_sessions.inc()

            # Audit successful login
            await AuditLogger.log_event(
                "user_login_success",
                user_id=user_id,
                ip_address=client_ip,
                user_agent=user_agent,
                details={
                    "email": req.email,
                    "remember_me": req.remember_me,
                    "device_fingerprint": req.device_fingerprint
                }
            )

            auth_requests_total.labels(method='login', status='success', endpoint='login').inc()

            return {
                "msg": "Login successful",
                "access_token": session_token,
                "token_type": "bearer",
                "expires_in": session_ttl,
                "user_id": user_id
            }

    except HTTPException:
        auth_requests_total.labels(method='login', status='error', endpoint='login').inc()
        raise
    except Exception as e:
        auth_requests_total.labels(method='login', status='error', endpoint='login').inc()
        await AuditLogger.log_event(
            "login_system_error",
            ip_address=client_ip,
            details={"error": str(e)},
            severity="critical"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

# --------------------------

# Enhanced Password Recovery

# --------------------------

@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, email: EmailStr):
client_ip = request.client.host

    try:
        with auth_request_duration.labels(endpoint='forgot_password').time():
            # Rate limit password reset requests per email
            reset_key = f"password_reset:{email}"
            if redis_client.exists(reset_key):
                await AuditLogger.log_event(
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
                await AuditLogger.log_event(
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
            redis_client.setex(reset_key, 900, "1")

            # Audit password reset request
            await AuditLogger.log_event(
                "password_reset_requested",
                ip_address=client_ip,
                details={"email": email}
            )

            auth_requests_total.labels(method='password_reset', status='success', endpoint='forgot_password').inc()

            return {"msg": "If the email exists, a recovery link has been sent"}

    except HTTPException:
        auth_requests_total.labels(method='password_reset', status='error', endpoint='forgot_password').inc()
        raise
    except Exception as e:
        auth_requests_total.labels(method='password_reset', status='error', endpoint='forgot_password').inc()
        await AuditLogger.log_event(
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
        await AuditLogger.log_event(
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

        await AuditLogger.log_event(
            "social_login_initiated",
            ip_address=client_ip,
            details={"provider": provider, "flow_id": flow_id}
        )

        auth_requests_total.labels(method='social', status='success', endpoint='social_login').inc()

        return {
            "login_flow_id": flow_id,
            "redirect_url": f"{KRATOS_PUBLIC_URL}/self-service/methods/oidc/{provider}?flow={flow_id}"
        }

    except Exception as e:
        auth_requests_total.labels(method='social', status='error', endpoint='social_login').inc()
        await AuditLogger.log_event(
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
async def whoami(request: Request, current_user: Dict = Depends(get_current_user)):
try:
with auth_request_duration.labels(endpoint='whoami').time(): # Get user details from database
user_doc = users.find_one({"kratos_id": current_user["user_id"]})
if not user_doc:
raise HTTPException(status_code=404, detail="User not found")

            # Decrypt sensitive data
            decrypted_name = SecurityUtils.decrypt_sensitive_data(user_doc["name"])

            user_info = {
                "user_id": current_user["user_id"],
                "email": user_doc["email"],
                "name": decrypted_name,
                "created_at": user_doc["created_at"],
                "last_login": user_doc.get("last_login"),
                "lago_customer_id": user_doc.get("lago_customer_id")
            }

            auth_requests_total.labels(method='whoami', status='success', endpoint='whoami').inc()
            return user_info

    except HTTPException:
        auth_requests_total.labels(method='whoami', status='error', endpoint='whoami').inc()
        raise
    except Exception as e:
        auth_requests_total.labels(method='whoami', status='error', endpoint='whoami').inc()
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
        redis_client.delete(session_key)

        # Decrement active sessions
        active_sessions.dec()

        # Audit logout
        await AuditLogger.log_event(
            "user_logout",
            user_id=current_user["user_id"],
            ip_address=client_ip,
            details={"session_id": current_user["jti"]}
        )

        auth_requests_total.labels(method='logout', status='success', endpoint='logout').inc()

        return {"msg": "Successfully logged out"}

    except Exception as e:
        auth_requests_total.labels(method='logout', status='error', endpoint='logout').inc()
        await AuditLogger.log_event(
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
async def get_audit_logs(
request: Request,
current_user: Dict = Depends(get_current_user),
limit: int = 100,
skip: int = 0,
event_type: Optional[str] = None,
severity: Optional[str] = None
): # TODO: Add admin role check

    query = {}
    if event_type:
        query["event_type"] = event_type
    if severity:
        query["severity"] = severity

    logs = list(audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit))

    return {
        "logs": logs,
        "total": audit_logs.count_documents(query),
        "page": skip // limit + 1
    }

@router.post("/admin/unlock-account")
async def unlock_account(
request: Request,
email: EmailStr,
current_user: Dict = Depends(get_current_user)
): # TODO: Add admin role check

    users.update_one(
        {"email": email},
        {
            "$set": {"account_locked": False, "failed_login_attempts": 0},
            "$unset": {"locked_at": ""}
        }
    )

    await AuditLogger.log_event(
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
async def health_check():
try: # Check Kratos connectivity
kratos_health = requests.get(f"{KRATOS_PUBLIC_URL}/health/ready", timeout=5)
kratos_ok = kratos_health.status_code == 200

        # Check Redis connectivity
        redis_ok = redis_client.ping()

        # Check database connectivity
        db_ok = users.find_one({}, {"_id": 1}) is not None

        overall_health = kratos_ok and redis_ok and db_ok

        return {
            "status": "healthy" if overall_health else "unhealthy",
            "services": {
                "kratos": "up" if kratos_ok else "down",
                "redis": "up" if redis_ok else "down",
                "database": "up" if db_ok else "down"
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# --------------------------

# Cleanup Tasks (Background)

# --------------------------

async def cleanup_expired_audits():
"""Remove audit logs older than retention period"""
cutoff_date = datetime.utcnow() - timedelta(days=AUDIT_RETENTION_DAYS)
result = audit_logs.delete_many({
"timestamp": {"$lt": cutoff_date.isoformat()}
})

    logger.info(f"Cleaned up {result.deleted_count} expired audit logs")

async def cleanup_expired_sessions():
"""Remove expired sessions from Redis""" # This would be handled by Redis TTL, but we can add additional cleanup logic
pass

# docker-compose.yml - Production-ready setup

version: '3.8'

services:
auth-api:
build: .
ports: - "8000:8000"
environment: - KRATOS_PUBLIC_URL=http://kratos:4433 - REDIS_URL=redis://redis:6379 - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - JWT_SECRET=${JWT_SECRET} - MONGODB_URI=${MONGODB_URI} - AUDIT_RETENTION_DAYS=90 - LOG_LEVEL=INFO - ENVIRONMENT=production
depends_on: - redis - kratos - mongodb
networks: - auth-network
restart: unless-stopped
healthcheck:
test: ["CMD", "curl", "-f", "http://localhost:8000/auth/health"]
interval: 30s
timeout: 10s
retries: 3
logging:
driver: "json-file"
options:
max-size: "10m"
max-file: "3"

redis:
image: redis:7-alpine
ports: - "6379:6379"
command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
volumes: - redis_data:/data
networks: - auth-network
restart: unless-stopped
healthcheck:
test: ["CMD", "redis-cli", "ping"]
interval: 30s
timeout: 10s
retries: 3

kratos:
image: oryd/kratos:v1.0.0
ports: - "4433:4433" - "4434:4434"
environment: - DSN=sqlite:///var/lib/kratos/db.sqlite?\_fk=true&mode=rwc - LOG_LEVEL=trace
volumes: - ./kratos:/etc/config/kratos - kratos_data:/var/lib/kratos
networks: - auth-network
restart: unless-stopped
command: serve -c /etc/config/kratos/kratos.yml --dev --watch-courier

kratos-migrate:
image: oryd/kratos:v1.0.0
environment: - DSN=sqlite:///var/lib/kratos/db.sqlite?\_fk=true&mode=rwc
volumes: - ./kratos:/etc/config/kratos - kratos_data:/var/lib/kratos
networks: - auth-network
command: -c /etc/config/kratos/kratos.yml migrate sql -e --yes
depends_on: - kratos

mongodb:
image: mongo:7
ports: - "27017:27017"
environment: - MONGO_INITDB_ROOT_USERNAME=${MONGO_ROOT_USERNAME}
      - MONGO_INITDB_ROOT_PASSWORD=${MONGO_ROOT_PASSWORD} - MONGO_INITDB_DATABASE=auth_db
volumes: - mongodb_data:/data/db - ./mongo-init.js:/docker-entrypoint-initdb.d/mongo-init.js:ro
networks: - auth-network
restart: unless-stopped
healthcheck:
test: echo 'db.runCommand("ping").ok' | mongosh localhost:27017/test --quiet
interval: 30s
timeout: 10s
retries: 3

prometheus:
image: prom/prometheus:latest
ports: - "9090:9090"
volumes: - ./prometheus.yml:/etc/prometheus/prometheus.yml - prometheus_data:/prometheus
networks: - auth-network
restart: unless-stopped
command: - '--config.file=/etc/prometheus/prometheus.yml' - '--storage.tsdb.path=/prometheus' - '--web.console.libraries=/etc/prometheus/console_libraries' - '--web.console.templates=/etc/prometheus/consoles' - '--storage.tsdb.retention.time=200h' - '--web.enable-lifecycle'

grafana:
image: grafana/grafana:latest
ports: - "3000:3000"
environment: - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD} - GF_USERS_ALLOW_SIGN_UP=false
volumes: - grafana_data:/var/lib/grafana - ./grafana/dashboards:/etc/grafana/provisioning/dashboards - ./grafana/datasources:/etc/grafana/provisioning/datasources
networks: - auth-network
restart: unless-stopped

nginx:
image: nginx:alpine
ports: - "80:80" - "443:443"
volumes: - ./nginx.conf:/etc/nginx/nginx.conf - ./ssl:/etc/nginx/ssl
networks: - auth-network
restart: unless-stopped
depends_on: - auth-api

volumes:
redis_data:
kratos_data:
mongodb_data:
prometheus_data:
grafana_data:

networks:
auth-network:
driver: bridge

---

# .env template

ENCRYPTION_KEY=your-32-byte-base64-encryption-key
JWT_SECRET=your-jwt-secret-key
REDIS_PASSWORD=your-redis-password
MONGO_ROOT_USERNAME=admin
MONGO_ROOT_PASSWORD=your-mongo-password
MONGODB_URI=mongodb://admin:your-mongo-password@mongodb:27017/auth_db?authSource=admin
GRAFANA_ADMIN_PASSWORD=your-grafana-password

---

# prometheus.yml - Prometheus configuration

global:
scrape_interval: 15s
evaluation_interval: 15s

rule_files:

- "auth_alerts.yml"

scrape_configs:

- job_name: 'auth-api'
  static_configs:

  - targets: ['auth-api:8000']
    metrics_path: '/auth/metrics'
    scrape_interval: 30s

- job_name: 'kratos'
  static_configs:

  - targets: ['kratos:4434']
    metrics_path: '/metrics'

- job_name: 'redis'
  static_configs:
  - targets: ['redis:6379']

alerting:
alertmanagers: - static_configs: - targets: - alertmanager:9093

---

# auth_alerts.yml - Alerting rules

groups:

- name: auth_security
  rules:

  - alert: HighFailedLoginRate
    expr: rate(auth_failed_login_attempts_total[5m]) > 5
    for: 2m
    labels:
    severity: warning
    annotations:
    summary: "High failed login attempt rate detected"
    description: "Failed login rate is {{ $value }} per second"

  - alert: AccountLockoutSpike
    expr: increase(auth_security_events_total{event_type="login_attempt_locked_account"}[5m]) > 10
    for: 1m
    labels:
    severity: critical
    annotations:
    summary: "Multiple account lockout attempts detected"
    description: "{{ $value }} account lockout attempts in the last 5 minutes"

  - alert: AuthServiceDown
    expr: up{job="auth-api"} == 0
    for: 30s
    labels:
    severity: critical
    annotations:
    summary: "Authentication service is down"
    description: "Auth API has been down for more than 30 seconds"

  - alert: HighResponseTime
    expr: histogram_quantile(0.95, rate(auth_request_duration_seconds_bucket[5m])) > 2
    for: 5m
    labels:
    severity: warning
    annotations:
    summary: "High authentication response time"
    description: "95th percentile response time is {{ $value }} seconds"

---

# nginx.conf - Reverse proxy with security headers

events {
worker_connections 1024;
}

http {
include /etc/nginx/mime.types;
default_type application/octet-stream;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;
    error_log /var/log/nginx/error.log warn;

    upstream auth_backend {
        server auth-api:8000;
        keepalive 32;
    }

    server {
        listen 80;
        server_name _;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name _;

        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;

        # Security settings
        client_max_body_size 1m;
        client_body_timeout 60s;
        client_header_timeout 60s;

        # Auth endpoints with stricter rate limiting
        location /auth/register {
            limit_req zone=auth burst=5 nodelay;
            proxy_pass http://auth_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /auth/login {
            limit_req zone=auth burst=10 nodelay;
            proxy_pass http://auth_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # General API endpoints
        location /auth/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://auth_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Block access to sensitive endpoints
        location /auth/admin/ {
            allow 10.0.0.0/8;    # Internal networks only
            allow 172.16.0.0/12;
            allow 192.168.0.0/16;
            deny all;

            proxy_pass http://auth_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Metrics endpoint (restricted)
        location /auth/metrics {
            allow 10.0.0.0/8;    # Internal networks only
            deny all;

            proxy_pass http://auth_backend;
        }
    }

}
