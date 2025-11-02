# services/user_service.py - User service with business logic

from typing import Optional, Dict, Any, List,Tuple
from datetime import datetime, timedelta,timezone
import asyncio
import hashlib
import secrets,uuid
import logging
from dataclasses import dataclass
from enum import Enum
from fastapi import Request, Depends, HTTPException
import requests
from cryptography.fernet import Fernet
import redis
from pymongo.collection import Collection

from .lago_billing import LagoBillingService
from services.email_services import EmailService
from services.audit import AuditService
# from db.models import User, AuditLog
from utils.user import SecurityUtils,AuditLogger
from utils.exceptions import (
    UserAlreadyExistsError,
    InvalidCredentialsError,
    AccountLockedError,
    RateLimitExceededError,
    ServiceUnavailableError
)
from services.minio import MinioAPIClient
from utils.db import(
    Database,get_database
)
from metrics.metrics import MetricsCollector,get_metrics

logger = logging.getLogger(__name__)

class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"

@dataclass
class RegistrationRequest:
    email: str
    password: str
    name: str
    terms_accepted: bool
    marketing_consent: bool = False
    referral_code: Optional[str] = None
    preferred_language:Optional[str]="en"
    
@dataclass
class RegisterRequestModel(RegistrationRequest):
    pass

@dataclass
class LoginRequest:
    email: str
    password: str
    remember_me: bool = False
    device_fingerprint: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

@dataclass
class UserProfile:
    user_id: str
    email: str
    name: str
    status: UserStatus
    created_at: datetime
    last_login: Optional[datetime]
    failed_login_attempts: int
    is_verified: bool
    lago_customer_id: Optional[str]
    preferences: Dict[str, Any]

class UserService:
    """Service class for user management operations"""
    
    def __init__(
        self,
        db:Database,
        redis_client: redis.Redis,
        kratos_service,
        lago_service: LagoBillingService,
        email_service: EmailService,
        audit_service: AuditService,
        security_utils: SecurityUtils,
        metrics: MetricsCollector = None,
        tenant_service = None
    ):
        self.db = db
        self.users_collection = db.users
        self.redis_client = redis_client
        self.kratos_service = kratos_service
        self.lago_service = lago_service
        self.email_service = email_service
        self.audit_service = audit_service
        self.security_utils = security_utils
        self.metrics = metrics
        
        # Configuration
        self.max_login_attempts = 5
        self.lockout_duration = timedelta(minutes=30)
        self.password_reset_timeout = timedelta(minutes=15)
        self.rate_limit_window = timedelta(minutes=5)
        self.max_registration_attempts = 100
    async def _generate_secret(self, length: int = 32) -> str:
        """Generate random secret (to be encrypted later)."""
        return secrets.token_urlsafe(length)
    async def register_anonymous_user(
        self,
        unique_id: Optional[str],
        geo_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        
        country = (geo_info.get("country") or {}).get("iso_code")

        # 1. Try existing user by unique_id
        user = None
        if unique_id:
            
            user = self.db.anonymous_users.find_one({"user_ref": unique_id})

        # 2. Try fallback by IP
        if not user:
            geo=geo_info.get("geo_id")
            query = {"ip_id": geo_info.get("geo_id")}
            ip_ref = self.db.user_ips.find_one(query)
            if ip_ref:
                user = self.db.anonymous_users.find_one({"_id": ip_ref["ref"]})

        # 3. Country mismatch check
        if user:
            last_ip = self.db.user_ips.find_one({"ref": user["_id"]}, sort=[("time", -1)])
            if last_ip and last_ip.get("country") and last_ip["country"] != country:
                # Audit mismatch
                await self.audit_service.log_event(
                    "geoip_country_mismatch",
                    ip_address=geo_info.get("geo_id"),
                    details={"user_id": user["_id"],
                             "old_country": last_ip["country"],
                             "new_country": country
                    },
                    severity="warning"
                )
                print(f"user country mismatch old {last_ip.get('country')} new {country}")
                user = None  # Force new anon user

        # 4. Create new anon user if needed
        if not user:
            # Redis counter
            counter = self.redis_client.incr("anon_counter")
            anon_uid = f"anon{counter}"
            pseudo_email = f"{anon_uid}@anonymous.com"

            # Bucket credentials
            bucket_key = anon_uid  # bucket = username
            bucket_secret = await self._generate_secret()
            
            user_doc = {
                "uid": anon_uid,
                "user_ref": unique_id or str(uuid.uuid4()),
                "email": pseudo_email,
                "created_at": datetime.now(timezone.utc),
                "bucket": {"key": bucket_key, "secret": bucket_secret},
                "properties": {"country": country, "last_seen": datetime.now(timezone.utc)},
                "is_anonymous": True,
                "role":["guest"],
                "permissions":[]
            }

            result = self.db.anonymous_users.insert_one(user_doc)
            user_doc["_id"] = result.inserted_id
            user = user_doc
            
        if user and "lago_customer_id" not in user:
            # Create billing customer
            pwd=user.get("bucket",{}).get("secret")
            request=RegistrationRequest(user["email"],pwd,user.get("uid"),False,False)
            
            try:
                
                
                lago_customer = await self._create_lago_customer(
                    request, str(user["_id"]), True, False
                )
                self.db.anonymous_users.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "billing_pending": False,
                        "lago_customer_id": lago_customer.get("customer", {}).get("lago_id"),
                        "lago_customer":lago_customer,
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )
            except ServiceUnavailableError as e:
                print("Billing unavailable, deferring customer creation", e)
                # Option A: enqueue background job (Celery, RQ, FastAPI BackgroundTasks)
                # Option B: mark user with a "billing_pending" flag
                self.db.anonymous_users.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "billing_pending": True,
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )

            # lago_customer = await self._create_lago_customer(request,str(user["_id"]),True,True)
            # print("lago",lago_customer)
            # self.db.anonymous_users.update_one(
            #     {"_id": user["_id"]},
            #     {
            #         "$set": {
            #             "lago_customer_id": lago_customer.get("customer", {}).get("lago_id"),
            #             "updated_at": datetime.now(timezone.utc).isoformat()
            #         }
            #     }
            # )
            
            # minio = MinioAPIClient()
            # response = await minio.create_user(username=bucket_key,password=bucket_secret)
            # print(response)
            # Redis mappings
            # self.redis_client.set(f"bucket:{bucket_key}", str(user["_id"]))
            # self.redis_client.set(f"user:{user['_id']}:bucket", bucket_key)

        # 5. Log IP usage
        ip_doc = {
            "ref": user["_id"],
            "type": "anonymous",
            "ip_id": geo_info.get("geo_id"),
            "country": country,
            "time": datetime.now(timezone.utc)
        }
        self.db.user_ips.insert_one(ip_doc)

        return user
    async def register_user(
        self, 
        request: RegistrationRequest,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Register a new user with comprehensive validation and setup
        """
        
        try:
            # Rate limiting check
            await self._check_registration_rate_limit(ip_address)
            
            # Validate input
            await self._validate_registration_request(request)
            
            # Check if user already exists
            exists,existing_user,from_cache = await self._get_user_by_email(request.email)
           
            if exists:
                # print(f"delete {existing_user.id if not from_cache else existing_user['kratos_id']}")
                dele=await self.delete_kratos_user(existing_user.id if not from_cache else existing_user['kratos_id'])
               
                await self.audit_service.log_event(
                    "registration_attempt_duplicate_email",
                    ip_address=ip_address,
                    details={"email": request.email},
                    severity="warning"
                )
                # raise UserAlreadyExistsError("User with this email already exists")
            
            # Create user in Kratos
            kratos_user,session,verifiable_addresses = await self._create_kratos_user(request)
         
            
            # Create billing customer
            lago_customer = await self._create_lago_customer(request,kratos_user.id,True,True)
            
            # Generate verification token
            verification_token = self._generate_verification_token()
            
            # Check for auto-promotion to superadmin
            role, permissions = await self._check_auto_promotion(request.email)
            
            # Create user record
            user_data = {
                "email": request.email,
                "name": self.security_utils.encrypt_sensitive_data(request.name),
                "kratos_id": kratos_user.id,
                "lago_customer_id": lago_customer.get("customer", {}).get("lago_id"),
                "external_id": lago_customer.get("customer", {}).get("external_id"),
                "lago_customer":lago_customer,
                "status": UserStatus.PENDING_VERIFICATION.value,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "last_login": None,
                "role": role, # Will be 'superadmin' for first user, 'user' for others
                "failed_login_attempts": 0,
                "account_locked": False,
                "is_verified": False,
                "terms_accepted": request.terms_accepted,
                "marketing_consent": request.marketing_consent,
                "registration_ip": ip_address,
                "verification_token": verification_token,
                "preferences": self._get_default_preferences(role),
                "verifiable_addresses":verifiable_addresses
                
                # "preferences": {
                #     "email_notifications": True,
                #     "sms_notifications": False,
                #     "marketing_emails": request.marketing_consent
                # }
            }
            
           
            
            # Handle referral if provided
            if request.referral_code:
                referrer = await self._process_referral(request.referral_code)
                if referrer:
                    user_data["referred_by"] = referrer["user_id"]
            
            # Save user to database
            result = self.db.users.insert_one(user_data)
            user_id = str(result.inserted_id)
          
            # Send verification email
            await self._send_verification_email(request.email, verification_token)
            
            # Log successful registration
            await self.audit_service.log_event(
                "user_registered",
                user_id=kratos_user.id,
                ip_address=ip_address,
                details={
                    "email": request.email,
                    "lago_customer_id": lago_customer.get("customer", {}).get("lago_id"),
                    "has_referral": bool(request.referral_code)
                }
            )
            
            message = "Registration successful. Please check your email for verification."
            if role == "superadmin":
                message += " You have been granted superadmin privileges."
                
                # Disable auto-promotion after first superadmin
                await self._disable_auto_promotion()
            
            return {
                "user_id": kratos_user.id,
                "email": request.email,
                "status": UserStatus.PENDING_VERIFICATION.value,
                "verification_required": True,
                "message": message
            },session
            
        except Exception as e:
            print(e)
            await self.audit_service.log_event(
                "registration_failed",
                ip_address=ip_address,
                details={"error": str(e), "email": request.email},
                severity="error"
            )
            raise
    async def _check_auto_promotion(self, email: str) -> tuple[str, List[str]]:
        """Check if user should be auto-promoted to superadmin"""
        
        # Get system config
        config_collection = self.db.system_config
        
        # Check if auto-promotion is enabled
        auto_promote_config = config_collection.find_one({"key": "auto_promote_first_user"})
        if not auto_promote_config or not auto_promote_config.get("value", False):
            return "user", []
        
        # Check if this is the designated superadmin email
        superadmin_email_config = config_collection.find_one({"key": "superadmin_email"})
        designated_email = superadmin_email_config.get("value") if superadmin_email_config else None
        
        if email != designated_email:
            return "user", []
        
        # Check if any superadmin already exists
        existing_superadmin = self.users_collection.find_one({"role": "superadmin"})
        if existing_superadmin:
            logger.warning(f"Auto-promotion blocked: superadmin already exists ({existing_superadmin['email']})")
            return "user", []
        
        # Get superadmin permissions from roles collection
        roles_collection = self.db.roles
        superadmin_role = roles_collection.find_one({"name": "superadmin"})
        permissions = superadmin_role.get("permissions", []) if superadmin_role else []
        
        logger.info(f"Auto-promoting user {email} to superadmin")
        
        return "superadmin", permissions
    
    async def _disable_auto_promotion(self):
        """Disable auto-promotion after first superadmin is created"""
        config_collection = self.db.system_config
        
        config_collection.update_one(
            {"key": "auto_promote_first_user"},
            {
                "$set": {
                    "value": False,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Log this important security event
        await self.audit_service.log_event(
            "auto_promotion_disabled",
            details={"reason": "First superadmin created"},
            severity="info"
        )
        
        logger.info("Auto-promotion to superadmin has been disabled")
    
    def _get_default_preferences(self, role: str) -> Dict[str, Any]:
        """Get default preferences based on role"""
        base_preferences = {
            "theme": "light",
            "email_notifications": True,
            "sms_notifications": False
        }
        
        if role == "superadmin":
            base_preferences.update({
                "theme": "dark",
                "dashboard_layout": "advanced",
                "show_system_metrics": True,
                "audit_log_access": True
            })
        elif role == "admin":
            base_preferences.update({
                "dashboard_layout": "standard",
                "show_user_metrics": True
            })
        
        return base_preferences
    
    async def authenticate_user(
        self, 
        request: LoginRequest
    ) -> Dict[str, Any]:
        """
        Authenticate user with comprehensive security checks
        """
        try:
            # Rate limiting check
            await self._check_login_rate_limit(request.email, request.ip_address)
            
            # Get user from database
            exists,user,from_cache = await self._get_user_by_email(request.email)
            if not user:
                await self._handle_failed_login("user_not_found", request)
                raise InvalidCredentialsError("Invalid credentials")
            
            # Check account status
            await self._check_account_status(user)
            
            # Authenticate with Kratos
            kratos_session = await self._authenticate_with_kratos(request)
            
            # Update user login information
            await self._update_successful_login(user, request)
            
            # Generate session token
            session_token = self.security_utils.generate_session_token(
                user["kratos_id"], 
                request.remember_me
            )
            
            # Store session in Redis
            await self._store_session(session_token, user["kratos_id"], request.remember_me)
            
            # Log successful login
            await self.audit_service.log_event(
                "user_login_success",
                user_id=user["kratos_id"],
                ip_address=request.ip_address,
                user_agent=request.user_agent,
                details={
                    "email": request.email,
                    "remember_me": request.remember_me,
                    "device_fingerprint": request.device_fingerprint
                }
            )
            
            return {
                "access_token": session_token,
                "token_type": "bearer",
                "expires_in": 86400 * 30 if request.remember_me else 86400,
                "user": await self._get_user_profile(user["kratos_id"]),
                "session_id": self.security_utils.extract_session_id(session_token)
            }
            
        except (InvalidCredentialsError, AccountLockedError):
            await self._handle_failed_login("invalid_credentials", request)
            raise
        except Exception as e:
            await self.audit_service.log_event(
                "login_system_error",
                ip_address=request.ip_address,
                details={"error": str(e)},
                severity="critical"
            )
            raise
    
    async def get_user_profile(self, user_id: str) -> UserProfile:
        """Get user profile by ID"""
        user = await self._get_user_by_kratos_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        return await self._get_user_profile(user_id)
    
    async def update_user_profile(
        self, 
        user_id: str, 
        updates: Dict[str, Any]
    ) -> UserProfile:
        """Update user profile"""
        # Validate updates
        allowed_fields = {
            "name", "preferences", "marketing_consent"
        }
        
        filtered_updates = {
            k: v for k, v in updates.items() 
            if k in allowed_fields
        }
        
        # Encrypt sensitive data
        if "name" in filtered_updates:
            filtered_updates["name"] = self.security_utils.encrypt_sensitive_data(
                filtered_updates["name"]
            )
        
        filtered_updates["updated_at"] = datetime.utcnow()
        
        # Update in database
        result = self.users_collection.update_one(
            {"kratos_id": user_id},
            {"$set": filtered_updates}
        )
        
        if result.matched_count == 0:
            raise ValueError("User not found")
        
        # Log update
        await self.audit_service.log_event(
            "user_profile_updated",
            user_id=user_id,
            details={"updated_fields": list(filtered_updates.keys())}
        )
        
        return await self._get_user_profile(user_id)
    
    async def request_password_reset(
        self, 
        email: str, 
        ip_address: Optional[str] = None
    ) -> Dict[str, str]:
        """Request password reset"""
        # Rate limiting
        reset_key = f"password_reset:{email}"
        if self.redis_client.exists(reset_key):
            raise RateLimitExceededError("Password reset already requested")
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        
        # Store reset token in Redis with expiration
        self.redis_client.setex(
            f"reset_token:{reset_token}",
            int(self.password_reset_timeout.total_seconds()),
            email
        )
        
        # Set rate limit
        self.redis_client.setex(reset_key, 900, "1")  # 15 minutes
        
        # Send reset email (even for non-existent users to prevent enumeration)
        await self.email_service.send_password_reset_email(email, reset_token)
        
        # Log request
        await self.audit_service.log_event(
            "password_reset_requested",
            ip_address=ip_address,
            details={"email": email}
        )
        
        return {"message": "If the email exists, a reset link has been sent"}
    
    async def verify_email(self, token: str) -> Dict[str, str]:
        """Verify user email with token"""
        user = self.users_collection.find_one({"verification_token": token})
        if not user:
            raise ValueError("Invalid verification token")
        
        # Update user status
        self.users_collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "is_verified": True,
                    "status": UserStatus.ACTIVE.value,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {"verification_token": ""}
            }
        )
        
        # Log verification
        await self.audit_service.log_event(
            "email_verified",
            user_id=user["kratos_id"],
            details={"email": user["email"]}
        )
        
        return {"message": "Email verified successfully"}
    
    async def logout_user(
        self, 
        session_token: str, 
        ip_address: Optional[str] = None
    ) -> Dict[str, str]:
        """Logout user and invalidate session"""
        try:
            # Validate and decode token
            token_data = self.security_utils.validate_session_token(session_token)
            
            # Remove session from Redis
            session_key = f"session:{token_data['jti']}"
            self.redis_client.delete(session_key)
            
            # Log logout
            await self.audit_service.log_event(
                "user_logout",
                user_id=token_data["user_id"],
                ip_address=ip_address,
                details={"session_id": token_data["jti"]}
            )
            
            return {"message": "Successfully logged out"}
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            raise
    
    async def lock_user_account(
        self, 
        user_id: str, 
        reason: str,
        admin_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Lock user account (admin function)"""
        result = self.users_collection.update_one(
            {"kratos_id": user_id},
            {
                "$set": {
                    "account_locked": True,
                    "status": UserStatus.LOCKED.value,
                    "locked_at": datetime.utcnow(),
                    "lock_reason": reason,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise ValueError("User not found")
        
        # Invalidate all user sessions
        await self._invalidate_user_sessions(user_id)
        
        # Log account lock
        await self.audit_service.log_event(
            "account_locked_by_admin",
            user_id=admin_id,
            details={"target_user_id": user_id, "reason": reason},
            severity="warning"
        )
        
        return {"message": "Account locked successfully"}
    
    async def unlock_user_account(
        self, 
        user_id: str,
        admin_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Unlock user account (admin function)"""
        result = self.users_collection.update_one(
            {"kratos_id": user_id},
            {
                "$set": {
                    "account_locked": False,
                    "status": UserStatus.ACTIVE.value,
                    "failed_login_attempts": 0,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {
                    "locked_at": "",
                    "lock_reason": ""
                }
            }
        )
        
        if result.matched_count == 0:
            raise ValueError("User not found")
        
        # Log account unlock
        await self.audit_service.log_event(
            "account_unlocked_by_admin",
            user_id=admin_id,
            details={"target_user_id": user_id}
        )
        
        return {"message": "Account unlocked successfully"}
    
    async def get_user_activity(
        self, 
        user_id: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get user activity history"""
        return await self.audit_service.get_user_activity(user_id, limit)
    
    # Private helper methods
    
    async def _validate_registration_request(self, request: RegistrationRequest):
        """Validate registration request"""
        # Email format validation is handled by Pydantic
        
        # Password strength validation
        if not self.security_utils.validate_password_strength(request.password):
            raise ValueError("Password does not meet security requirements")
        
        # Terms acceptance validation
        if not request.terms_accepted:
            raise ValueError("Terms and conditions must be accepted")
    
    async def _check_registration_rate_limit(self, ip_address: Optional[str]):
        """Check registration rate limiting"""
        if not ip_address:
            return
        
        rate_key = f"registration_rate:{ip_address}"
        current_attempts = self.redis_client.get(rate_key)
        
        if current_attempts and int(current_attempts) >= self.max_registration_attempts:
            raise RateLimitExceededError("Too many registration attempts")
        
        # Increment counter
        pipe = self.redis_client.pipeline()
        pipe.incr(rate_key)
        pipe.expire(rate_key, int(self.rate_limit_window.total_seconds()))
        pipe.execute()
    
    async def _check_login_rate_limit(self, email: str, ip_address: Optional[str]):
        """Check login rate limiting"""
        # Per-user rate limiting
        user_rate_key = f"login_attempts:{email}"
        attempts = self.redis_client.get(user_rate_key)
        
        if attempts and int(attempts) >= self.max_login_attempts:
            raise RateLimitExceededError("Too many login attempts")
        
        # Per-IP rate limiting
        if ip_address:
            ip_rate_key = f"login_attempts_ip:{ip_address}"
            ip_attempts = self.redis_client.get(ip_rate_key)
            
            if ip_attempts and int(ip_attempts) >= self.max_login_attempts * 3:
                raise RateLimitExceededError("Too many login attempts from this IP")
    
    async def _get_user_by_email(self, email: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[bool]]:
        """Get user by email"""
        obj= self.db.users.find_one({"email": email})
       
        from_cache=False
        if  obj is not None:
           from_cache=True
           return True,obj,from_cache
        obj =await self.kratos_service.get_identity_by_email(email)
        if obj is not None:
            return True,obj,from_cache
        return False,None,False
        
        
    
    async def _get_user_by_kratos_id(self, kratos_id: str) -> Optional[Dict[str, Any]]:
        """Get user by Kratos ID"""
        return self.users_collection.find_one({"kratos_id": kratos_id})
    async def delete_kratos_user(self,kratos_id):
        logger.warning(f"Deleting user {kratos_id}")
        kratos_deleted= await self.kratos_service.delete_identity(kratos_id)
       
        result =  self.db.users.delete_one({"kratos_id": kratos_id})

        if result.deleted_count > 0:
            logger.info(f"Deleted user {kratos_id} from MongoDB users collection")
        else:
            logger.warning(f"User {kratos_id} not found in MongoDB users collection")

            return True
        return kratos_deleted
    async def _create_kratos_user(self, request: RegistrationRequest) -> Dict[str, Any]:
        """Create user in Kratos"""
        try:
            traits={
                "name":request.name,
                "marketing_consent":request.marketing_consent,
                "preferred_language":request.preferred_language,
                # "referral_code":request.referral_code,
                "terms_accepted":request.terms_accepted
            }
            return await self.kratos_service.create_user_flow(
                email=request.email,
                password=request.password,
                traits = traits
                
            )
        except Exception as e:
            logger.error(f"Kratos user creation failed: {e}")
            raise ServiceUnavailableError("Authentication service unavailable")
    
    async def _create_lago_customer(self, request: RegistrationRequest,id:str,assign_subscription:bool=False,create_wallet:bool=True) -> Dict[str, Any]:
        """Create customer in Lago billing"""
        max_retries = 1
       
        for attempt in range(max_retries):
            try:
                try:
                    lago_customer=await self.lago_service.get_customer_info(id)
                except Exception as e:
                    lago_customer=None
                
                if(lago_customer):
                    return lago_customer
                else:
                    print("lago Customer not exists")
                    lago_customer=  self.lago_service.create_customer(
                        external_id=id,
                        name=request.name,
                        email=request.email
                    )
                    
                    # lago_user_id = lago_customer.get("customer", {}).get("lago_id")
                    if assign_subscription:
                        
                        subscription =await self.lago_service.create_user_subscription(user_id=id,
                                                                                       name="Default Subscription",
                                                                                       plan_code="starter",
                                                                                       billing_time="calendar",
                                                                                       external_id=f"sub_{uuid.uuid4().hex}",
                                                                                       subscription_at=datetime.now(timezone.utc).isoformat()
                                                                                    )
                    
                        lago_customer["subscription"]=subscription.get("subscription")
                    if create_wallet:
                        wallet = await self.lago_service.create_wallet(external_customer_id=id,rate_amount = 0.001,name="Default Wallet",external_id=f"sub_{uuid.uuid4().hex}")
                        lago_customer["default_wallet"]=wallet.get("wallet")
                        
                return lago_customer
            except Exception as e:
                logger.error(f"Lago customer creation failed: {e}")
                if attempt == max_retries - 1:
                    
                    raise ServiceUnavailableError(F"Billing service unavailable {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    def _generate_verification_token(self) -> str:
        """Generate email verification token"""
        return secrets.token_urlsafe(32)
    
    async def _send_verification_email(self, email: str, token: str):
        """Send verification email"""
        try:
            await self.email_service.send_verification_email(email, token)
        except Exception as e:
            logger.error(f"Failed to send verification email: {e}")
            # Don't fail registration if email fails
    
    async def _process_referral(self, referral_code: str) -> Optional[Dict[str, Any]]:
        """Process referral code"""
        # Find referring user
        referrer = self.users_collection.find_one({"referral_code": referral_code})
        if referrer:
            # Update referrer's referral count
            self.users_collection.update_one(
                {"_id": referrer["_id"]},
                {"$inc": {"referral_count": 1}}
            )
            return referrer
        return None
    
    async def _check_account_status(self, user: Dict[str, Any]):
        """Check if account can be used for login"""
        if user.get("account_locked"):
            raise AccountLockedError("Account is locked")
        
        if user.get("status") == UserStatus.SUSPENDED.value:
            raise AccountLockedError("Account is suspended")
        
        if user.get("status") == UserStatus.INACTIVE.value:
            raise AccountLockedError("Account is inactive")
    
    async def _authenticate_with_kratos(self, request: LoginRequest) -> Dict[str, Any]:
        """Authenticate with Kratos"""
        try:
            return await self.kratos_service.authenticate(
                email=request.email,
                password=request.password
            )
        except Exception as e:
            logger.error(f"Kratos authentication failed: {e}")
            raise InvalidCredentialsError("Invalid credentials")
    
    async def _update_successful_login(self, user: Dict[str, Any], request: LoginRequest):
        """Update user record after successful login"""
        self.users_collection.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "last_login": datetime.utcnow(),
                    "last_login_ip": request.ip_address,
                    "failed_login_attempts": 0,
                    "account_locked": False,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {"locked_at": "", "lock_reason": ""}
            }
        )
        
        # Clear rate limiting
        user_rate_key = f"login_attempts:{request.email}"
        self.redis_client.delete(user_rate_key)
    
    async def _handle_failed_login(self, reason: str, request: LoginRequest):
        """Handle failed login attempt"""
        # Increment rate limiting counter
        user_rate_key = f"login_attempts:{request.email}"
        pipe = self.redis_client.pipeline()
        pipe.incr(user_rate_key)
        pipe.expire(user_rate_key, 900)  # 15 minutes
        pipe.execute()
        
        # Update user failed attempts if user exists
        exists,user,from_cache = await self._get_user_by_email(request.email)
        if user and from_cache:
            failed_attempts = user.get("failed_login_attempts", 0) + 1
            update_data = {
                "failed_login_attempts": failed_attempts,
                "updated_at": datetime.utcnow()
            }
            
            # Lock account after max attempts
            if failed_attempts >= self.max_login_attempts:
                update_data.update({
                    "account_locked": True,
                    "status": UserStatus.LOCKED.value,
                    "locked_at": datetime.utcnow(),
                    "lock_reason": "Too many failed login attempts"
                })
            
            self.users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": update_data}
            )
        
        # Log failed attempt
        await self.audit_service.log_event(
            "login_failed",
            user_id=user.get("kratos_id") if user else None,
            ip_address=request.ip_address,
            user_agent=request.user_agent,
            details={"email": request.email, "reason": reason},
            severity="warning"
        )
    
    async def _store_session(self, token: str, user_id: str, remember_me: bool):
        """Store session in Redis"""
        import jwt as jwt_lib
        
        token_data = jwt_lib.decode(token, options={"verify_signature": False})
        session_key = f"session:{token_data['jti']}"
        session_ttl = 86400 * 30 if remember_me else 86400
        
        self.redis_client.setex(session_key, session_ttl, user_id)
    
    async def _get_user_profile(self, user_id: str) -> UserProfile:
        """Get formatted user profile"""
        user = await self._get_user_by_kratos_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Decrypt sensitive data
        decrypted_name = self.security_utils.decrypt_sensitive_data(user["name"])
        
        return UserProfile(
            user_id=user["kratos_id"],
            email=user["email"],
            name=decrypted_name,
            status=UserStatus(user["status"]),
            created_at=user["created_at"],
            last_login=user.get("last_login"),
            failed_login_attempts=user.get("failed_login_attempts", 0),
            is_verified=user.get("is_verified", False),
            lago_customer_id=user.get("lago_customer_id"),
            preferences=user.get("preferences", {})
        )
    
    async def _invalidate_user_sessions(self, user_id: str):
        """Invalidate all sessions for a user"""
        # Get all session keys for the user
        pattern = "session:*"
        session_keys = self.redis_client.keys(pattern)
        
        for key in session_keys:
            stored_user_id = self.redis_client.get(key)
            if stored_user_id and stored_user_id.decode() == user_id:
                self.redis_client.delete(key)
    async def _handle_first_user_promotion(self, email: str):
        """Handle auto-promotion of first user to superadmin"""
        # Check if auto-promotion is enabled
        config = self.db.system_config.find_one({"key": "auto_promote_first_user"})
        if not config or not config.get("value"):
            return
        
        # Check if this is the configured superadmin email
        admin_email_config = self.db.system_config.find_one({"key": "superadmin_email"})
        if admin_email_config and admin_email_config.get("value") == email:
            # This will be the superadmin - disable auto-promotion after this
            self.db.system_config.update_one(
                {"key": "auto_promote_first_user"},
                {"$set": {"value": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
    async def _determine_initial_role(self, email: str) -> str:
            """Determine initial role for new user"""
            # Check if this is the superadmin email
            admin_email_config = self.db.system_config.find_one({"key": "superadmin_email"})
            if admin_email_config and admin_email_config.get("value") == email:
                return "superadmin"
            
            return "user"
    def _generate_referral_code(self) -> str:
        """Generate unique referral code"""
        import secrets
        import string
        
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if not self.users.find_one({"referral_code": code}):
                return code
    
    async def _get_default_tenant_id(self) -> Optional[str]:
        """Get default tenant ID for new users"""
        # Look for a default tenant or create one if needed
        default_tenant = self.db.tenants.find_one({"name": "Default"})
        if default_tenant:
            return str(default_tenant["_id"])
        return None
    


def get_user_service(
    db: Database = Depends(get_database),
    metrics: MetricsCollector = Depends(get_metrics)
) -> UserService:
    """Dependency to get user service"""
    return UserService(db, metrics)