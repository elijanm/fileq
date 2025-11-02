# services/tenant_service.py - Multi-tenant management service

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import secrets
from dataclasses import dataclass
from bson import ObjectId
from services.email_services import EmailService
from services.audit import AuditService
from pymongo.collection import Collection

logger = logging.getLogger(__name__)

class TenantStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    PENDING_SETUP = "pending_setup"

class SubscriptionPlan(Enum):
    TRIAL = "trial"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

class TenantUserRole(Enum):
    OWNER = "owner"
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    BILLING_ADMIN = "billing_admin"

@dataclass
class Tenant:
    id: str
    name: str
    subdomain: str
    domain: Optional[str]
    status: TenantStatus
    subscription_plan: SubscriptionPlan
    settings: Dict[str, Any]
    created_at: datetime
    trial_ends_at: Optional[datetime]
    user_count: int = 0
    admin_count: int = 0

@dataclass
class TenantUser:
    tenant_id: str
    user_id: str
    email: str
    name: str
    role: TenantUserRole
    status: str
    permissions: List[str]
    joined_at: Optional[datetime]
    last_accessed: Optional[datetime]

@dataclass
class TenantInvitation:
    id: str
    tenant_id: str
    email: str
    role: TenantUserRole
    token: str
    invited_by: str
    expires_at: datetime
    status: str

class TenantService:
    """Service for multi-tenant operations"""
    
    def __init__(
        self,
        tenants_collection: Collection,
        tenant_users_collection: Collection,
        tenant_invitations_collection: Collection,
        users_collection: Collection,
        audit_service: AuditService,
        email_service: EmailService
    ):
        self.tenants_collection = tenants_collection
        self.tenant_users_collection = tenant_users_collection
        self.tenant_invitations_collection = tenant_invitations_collection
        self.users_collection = users_collection
        self.audit_service = audit_service
        self.email_service = email_service
    
    # Tenant Management
    async def create_tenant(
        self,
        creator_user_id: str,
        name: str,
        subdomain: str,
        domain: Optional[str] = None,
        subscription_plan: str = "trial"
    ) -> Dict[str, Any]:
        """Create a new tenant"""
        
        # Validate subdomain uniqueness
        if self.tenants_collection.find_one({"subdomain": subdomain}):
            raise ValueError("Subdomain already exists")
        
        # Validate domain uniqueness if provided
        if domain and self.tenants_collection.find_one({"domain": domain}):
            raise ValueError("Domain already exists")
        
        # Create tenant
        tenant_data = {
            "name": name,
            "subdomain": subdomain,
            "domain": domain,
            "status": TenantStatus.TRIAL.value,
            "subscription_plan": subscription_plan,
            "settings": self._get_default_settings(subscription_plan),
            "billing_info": {
                "lago_customer_id": None,
                "stripe_customer_id": None,
                "billing_email": None,
                "billing_address": None
            },
            "created_at": datetime.utcnow().isoformat(),
            "created_by": creator_user_id,
            "trial_ends_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "metadata": {}
        }
        
        result = self.tenants_collection.insert_one(tenant_data)
        tenant_id = result.inserted_id
        
        # Add creator as tenant owner
        await self._add_user_to_tenant(
            tenant_id=str(tenant_id),
            user_id=creator_user_id,
            role=TenantUserRole.OWNER.value,
            added_by=creator_user_id
        )
        
        # Set as primary tenant if user doesn't have one
        user = self.users_collection.find_one({"kratos_id": creator_user_id})
        if not user.get("primary_tenant_id"):
            self.users_collection.update_one(
                {"kratos_id": creator_user_id},
                {"$set": {"primary_tenant_id": tenant_id}}
            )
        
        # Audit log
        await self.audit_service.log_event(
            "tenant_created",
            user_id=creator_user_id,
            tenant_id=tenant_id,
            details={
                "tenant_name": name,
                "subdomain": subdomain,
                "subscription_plan": subscription_plan
            }
        )
        
        return {
            "tenant_id": str(tenant_id),
            "name": name,
            "subdomain": subdomain,
            "status": TenantStatus.TRIAL.value,
            "trial_ends_at": tenant_data["trial_ends_at"]
        }
    
    async def get_tenant_by_subdomain(self, subdomain: str) -> Optional[Tenant]:
        """Get tenant by subdomain"""
        tenant_doc = self.tenants_collection.find_one({"subdomain": subdomain})
        if not tenant_doc:
            return None
        
        return self._doc_to_tenant(tenant_doc)
    
    async def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        try:
            tenant_doc = self.tenants_collection.find_one({"_id": ObjectId(tenant_id)})
        except:
            return None
        
        if not tenant_doc:
            return None
        
        return self._doc_to_tenant(tenant_doc)
    
    async def get_user_tenants(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all tenants for a user"""
        tenant_users = self.tenant_users_collection.find({
            "user_id": user_id,
            "status": "active"
        })
        
        tenants = []
        for tenant_user in tenant_users:
            tenant = await self.get_tenant_by_id(str(tenant_user["tenant_id"]))
            if tenant:
                tenants.append({
                    "tenant": tenant,
                    "role": tenant_user["role"],
                    "permissions": tenant_user.get("permissions", []),
                    "joined_at": tenant_user.get("joined_at"),
                    "last_accessed": tenant_user.get("last_accessed")
                })
        
        return tenants
    
    async def update_tenant_settings(
        self,
        admin_user_id: str,
        tenant_id: str,
        settings: Dict[str, Any]
    ) -> Dict[str, str]:
        """Update tenant settings"""
        
        # Check if user has permission to update tenant
        if not await self._user_can_manage_tenant(admin_user_id, tenant_id):
            raise PermissionError("Insufficient permissions to update tenant")
        
        # Update tenant
        result = self.tenants_collection.update_one(
            {"_id": ObjectId(tenant_id)},
            {
                "$set": {
                    "settings": settings,
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
        )
        
        if result.matched_count == 0:
            raise ValueError("Tenant not found")
        
        # Audit log
        await self.audit_service.log_event(
            "tenant_settings_updated",
            user_id=admin_user_id,
            tenant_id=ObjectId(tenant_id),
            details={"updated_settings": list(settings.keys())}
        )
        
        return {"message": "Tenant settings updated successfully"}
    
    # User-Tenant Management
    async def invite_user_to_tenant(
        self,
        inviter_user_id: str,
        tenant_id: str,
        email: str,
        role: str,
        message: Optional[str] = None
    ) -> Dict[str, str]:
        """Invite user to tenant"""
        
        # Check permissions
        if not await self._user_can_manage_users(inviter_user_id, tenant_id):
            raise PermissionError("Insufficient permissions to invite users")
        
        # Check if user is already in tenant
        existing_user = self.tenant_users_collection.find_one({
            "tenant_id": ObjectId(tenant_id),
            "user_id": {"$in": [email, self._get_user_id_by_email(email)]}
        })
        
        if existing_user:
            raise ValueError("User is already a member of this tenant")
        
        # Check for existing invitation
        existing_invitation = self.tenant_invitations_collection.find_one({
            "tenant_id": ObjectId(tenant_id),
            "email": email,
            "status": "pending"
        })
        
        if existing_invitation:
            raise ValueError("Invitation already sent to this email")
        
        # Generate invitation token
        invitation_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=7)  # 7 days to accept
        
        # Create invitation
        invitation_data = {
            "tenant_id": ObjectId(tenant_id),
            "email": email,
            "role": role,
            "permissions": self._get_role_permissions(role),
            "token": invitation_token,
            "invited_by": inviter_user_id,
            "message": message,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat()
        }
        
        result = self.tenant_invitations_collection.insert_one(invitation_data)
        
        # Get tenant info for email
        tenant = await self.get_tenant_by_id(tenant_id)
        inviter = self.users_collection.find_one({"kratos_id": inviter_user_id})
        
        # Send invitation email
        try:
            await self.email_service.send_tenant_invitation_email(
                to_email=email,
                tenant_name=tenant.name,
                inviter_name=inviter.get("name", "Someone"),
                role=role,
                invitation_token=invitation_token,
                message=message
            )
        except Exception as e:
            logger.error(f"Failed to send invitation email: {e}")
        
        # Audit log
        await self.audit_service.log_event(
            "user_invited_to_tenant",
            user_id=inviter_user_id,
            tenant_id=ObjectId(tenant_id),
            details={
                "invited_email": email,
                "role": role,
                "invitation_id": str(result.inserted_id)
            }
        )
        
        return {
            "message": "Invitation sent successfully",
            "invitation_id": str(result.inserted_id),
            "expires_at": expires_at.isoformat()
        }
    
    async def accept_tenant_invitation(
        self,
        user_id: str,
        invitation_token: str
    ) -> Dict[str, Any]:
        """Accept tenant invitation"""
        
        # Find invitation
        invitation = self.tenant_invitations_collection.find_one({
            "token": invitation_token,
            "status": "pending"
        })
        
        if not invitation:
            raise ValueError("Invalid or expired invitation")
        
        # Check if invitation has expired
        if datetime.fromisoformat(invitation["expires_at"]) < datetime.utcnow():
            self.tenant_invitations_collection.update_one(
                {"_id": invitation["_id"]},
                {"$set": {"status": "expired"}}
            )
            raise ValueError("Invitation has expired")
        
        # Verify email matches user
        user = self.users_collection.find_one({"kratos_id": user_id})
        if not user or user["email"] != invitation["email"]:
            raise ValueError("Invitation email does not match user account")
        
        # Add user to tenant
        await self._add_user_to_tenant(
            tenant_id=str(invitation["tenant_id"]),
            user_id=user_id,
            role=invitation["role"],
            permissions=invitation.get("permissions", []),
            added_by=invitation["invited_by"]
        )
        
        # Update invitation status
        self.tenant_invitations_collection.update_one(
            {"_id": invitation["_id"]},
            {
                "$set": {
                    "status": "accepted",
                    "accepted_at": datetime.utcnow().isoformat()
                }
            }
        )
        
        # Set as primary tenant if user doesn't have one
        if not user.get("primary_tenant_id"):
            self.users_collection.update_one(
                {"kratos_id": user_id},
                {"$set": {"primary_tenant_id": invitation["tenant_id"]}}
            )
        
        # Get tenant info
        tenant = await self.get_tenant_by_id(str(invitation["tenant_id"]))
        
        # Audit log
        await self.audit_service.log_event(
            "tenant_invitation_accepted",
            user_id=user_id,
            tenant_id=invitation["tenant_id"],
            details={
                "role": invitation["role"],
                "invited_by": invitation["invited_by"]
            }
        )
        
        return {
            "message": "Successfully joined tenant",
            "tenant": {
                "id": str(invitation["tenant_id"]),
                "name": tenant.name,
                "subdomain": tenant.subdomain
            },
            "role": invitation["role"]
        }
    
    async def remove_user_from_tenant(
        self,
        admin_user_id: str,
        tenant_id: str,
        target_user_id: str
    ) -> Dict[str, str]:
        """Remove user from tenant"""
        
        # Check permissions
        if not await self._user_can_manage_users(admin_user_id, tenant_id):
            raise PermissionError("Insufficient permissions to remove users")
        
        # Prevent removing tenant owner unless there's another owner
        target_membership = self.tenant_users_collection.find_one({
            "tenant_id": ObjectId(tenant_id),
            "user_id": target_user_id
        })
        
        if not target_membership:
            raise ValueError("User is not a member of this tenant")
        
        if target_membership["role"] == "owner":
            other_owners = self.tenant_users_collection.count_documents({
                "tenant_id": ObjectId(tenant_id),
                "role": "owner",
                "user_id": {"$ne": target_user_id},
                "status": "active"
            })
            
            if other_owners == 0:
                raise ValueError("Cannot remove the last owner from tenant")
        
        # Remove user from tenant
        result = self.tenant_users_collection.delete_one({
            "tenant_id": ObjectId(tenant_id),
            "user_id": target_user_id
        })
        
        if result.deleted_count == 0:
            raise ValueError("Failed to remove user from tenant")
        
        # If this was user's primary tenant, clear it
        user = self.users_collection.find_one({"kratos_id": target_user_id})
        if user and str(user.get("primary_tenant_id")) == tenant_id:
            # Find another tenant or set to None
            other_membership = self.tenant_users_collection.find_one({
                "user_id": target_user_id,
                "status": "active"
            })
            
            new_primary = other_membership["tenant_id"] if other_membership else None
            self.users_collection.update_one(
                {"kratos_id": target_user_id},
                {"$set": {"primary_tenant_id": new_primary}}
            )
        
        # Audit log
        await self.audit_service.log_event(
            "user_removed_from_tenant",
            user_id=admin_user_id,
            tenant_id=ObjectId(tenant_id),
            target_user_id=target_user_id,
            details={
                "target_role": target_membership["role"]
            },
            severity="warning"
        )
        
        return {"message": "User removed from tenant successfully"}
    
    async def switch_user_tenant(
        self,
        user_id: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Switch user's active tenant"""
        
        # Verify user has access to tenant
        membership = self.tenant_users_collection.find_one({
            "tenant_id": ObjectId(tenant_id),
            "user_id": user_id,
            "status": "active"
        })
        
        if not membership:
            raise PermissionError("User does not have access to this tenant")
        
        # Update user's primary tenant
        self.users_collection.update_one(
            {"kratos_id": user_id},
            {"$set": {"primary_tenant_id": ObjectId(tenant_id)}}
        )
        
        # Update last accessed time
        self.tenant_users_collection.update_one(
            {
                "tenant_id": ObjectId(tenant_id),
                "user_id": user_id
            },
            {"$set": {"last_accessed": datetime.utcnow().isoformat()}}
        )
        
        # Get tenant info
        tenant = await self.get_tenant_by_id(tenant_id)
        
        # Audit log
        await self.audit_service.log_event(
            "tenant_switched",
            user_id=user_id,
            tenant_id=ObjectId(tenant_id),
            details={
                "tenant_name": tenant.name,
                "user_role": membership["role"]
            }
        )
        
        return {
            "message": "Successfully switched tenant",
            "tenant": {
                "id": tenant_id,
                "name": tenant.name,
                "subdomain": tenant.subdomain
            },
            "role": membership["role"],
            "permissions": membership.get("permissions", [])
        }
    
    async def get_tenant_users(
        self,
        admin_user_id: str,
        tenant_id: str,
        page: int = 1,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get all users in a tenant"""
        
        # Check permissions
        if not await self._user_has_tenant_access(admin_user_id, tenant_id):
            raise PermissionError("Insufficient permissions to view tenant users")
        
        # Get paginated users
        skip = (page - 1) * limit
        tenant_users_cursor = self.tenant_users_collection.find({
            "tenant_id": ObjectId(tenant_id)
        }).skip(skip).limit(limit)
        
        total_count = self.tenant_users_collection.count_documents({
            "tenant_id": ObjectId(tenant_id)
        })
        
        users = []
        for tenant_user in tenant_users_cursor:
            # Get user details
            user = self.users_collection.find_one({"kratos_id": tenant_user["user_id"]})
            if user:
                users.append(TenantUser(
                    tenant_id=str(tenant_user["tenant_id"]),
                    user_id=tenant_user["user_id"],
                    email=user["email"],
                    name=user.get("name", ""),
                    role=TenantUserRole(tenant_user["role"]),
                    status=tenant_user["status"],
                    permissions=tenant_user.get("permissions", []),
                    joined_at=datetime.fromisoformat(tenant_user["joined_at"]) if tenant_user.get("joined_at") else None,
                    last_accessed=datetime.fromisoformat(tenant_user["last_accessed"]) if tenant_user.get("last_accessed") else None
                ))
        
        return {
            "users": users,
            "total": total_count,
            "page": page,
            "pages": (total_count + limit - 1) // limit
        }
    
    # Utility Methods
    async def _add_user_to_tenant(
        self,
        tenant_id: str,
        user_id: str,
        role: str,
        permissions: List[str] = None,
        added_by: str = None
    ):
        """Add user to tenant"""
        
        tenant_user_data = {
            "tenant_id": ObjectId(tenant_id),
            "user_id": user_id,
            "role": role,
            "status": "active",
            "permissions": permissions or self._get_role_permissions(role),
            "invited_by": added_by,
            "joined_at": datetime.utcnow().isoformat(),
            "last_accessed": datetime.utcnow().isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
        
        self.tenant_users_collection.insert_one(tenant_user_data)
    
    def _get_role_permissions(self, role: str) -> List[str]:
        """Get default permissions for role"""
        role_permissions = {
            "owner": [
                "tenants:read", "tenants:write", "tenants:manage_users",
                "tenants:manage_settings", "tenants:billing", "tenants:invite_users"
            ],
            "admin": [
                "tenants:read", "tenants:manage_users", "tenants:invite_users"
            ],
            "user": [
                "tenants:read"
            ],
            "guest": [
                "tenants:read"
            ],
            "billing_admin": [
                "tenants:read", "tenants:billing"
            ]
        }
        
        return role_permissions.get(role, [])
    
    def _get_default_settings(self, subscription_plan: str) -> Dict[str, Any]:
        """Get default settings for subscription plan"""
        
        base_settings = {
            "branding": {
                "logo_url": None,
                "primary_color": "#3b82f6",
                "secondary_color": "#1e40af"
            },
            "features": {
                "sso_enabled": False,
                "mfa_required": False,
                "api_access": True,
                "audit_logs": True,
                "custom_roles": False,
                "integrations": []
            },
            "security": {
                "password_policy": {
                    "min_length": 8,
                    "require_uppercase": True,
                    "require_lowercase": True,
                    "require_numbers": True,
                    "require_special": False
                },
                "session_timeout": 28800,
                "ip_whitelist": None,
                "allowed_domains": None
            }
        }
        
        # Plan-specific limits
        if subscription_plan == "trial":
            base_settings["limits"] = {
                "max_users": 5,
                "max_admins": 2,
                "storage_gb": 1,
                "api_calls_per_month": 1000
            }
        elif subscription_plan == "basic":
            base_settings["limits"] = {
                "max_users": 50,
                "max_admins": 5,
                "storage_gb": 10,
                "api_calls_per_month": 10000
            }
        elif subscription_plan == "professional":
            base_settings["limits"] = {
                "max_users": 500,
                "max_admins": 25,
                "storage_gb": 100,
                "api_calls_per_month": 100000
            }
            base_settings["features"]["sso_enabled"] = True
            base_settings["features"]["custom_roles"] = True
        elif subscription_plan == "enterprise":
            base_settings["limits"] = {
                "max_users": None,
                "max_admins": None,
                "storage_gb": None,
                "api_calls_per_month": None
            }
            base_settings["features"]["sso_enabled"] = True
            base_settings["features"]["mfa_required"] = True
            base_settings["features"]["custom_roles"] = True
        
        return base_settings
    
    async def _user_can_manage_tenant(self, user_id: str, tenant_id: str) -> bool:
        """Check if user can manage tenant"""
        # Check if user is superadmin
        user = self.users_collection.find_one({"kratos_id": user_id})
        if user and user.get("global_role") == "superadmin":
            return True
        
        # Check if user is tenant owner or admin
        membership = self.tenant_users_collection.find_one({
            "tenant_id": ObjectId(tenant_id),
            "user_id": user_id,
            "status": "active"
        })
        
        return membership and membership["role"] in ["owner", "admin"]
    
    async def _user_can_manage_users(self, user_id: str, tenant_id: str) -> bool:
        """Check if user can manage users in tenant"""
        return await self._user_can_manage_tenant(user_id, tenant_id)
    
    async def _user_has_tenant_access(self, user_id: str, tenant_id: str) -> bool:
        """Check if user has access to tenant"""
        # Check if user is superadmin
        user = self.users_collection.find_one({"kratos_id": user_id})
        if user and user.get("global_role") == "superadmin":
            return True
        
        # Check if user is member of tenant
        membership = self.tenant_users_collection.find_one({
            "tenant_id": ObjectId(tenant_id),
            "user_id": user_id,
            "status": "active"
        })
        
        return membership is not None
    
    def _get_user_id_by_email(self, email: str) -> Optional[str]:
        """Get user ID by email"""
        user = self.users_collection.find_one({"email": email})
        return user["kratos_id"] if user else None
    
    def _doc_to_tenant(self, doc: Dict[str, Any]) -> Tenant:
        """Convert MongoDB document to Tenant object"""
        # Count users and admins
        user_count = self.tenant_users_collection.count_documents({
            "tenant_id": doc["_id"],
            "status": "active"
        })
        
        admin_count = self.tenant_users_collection.count_documents({
            "tenant_id": doc["_id"],
            "role": {"$in": ["owner", "admin"]},
            "status": "active"
        })
        
        return Tenant(
            id=str(doc["_id"]),
            name=doc["name"],
            subdomain=doc["subdomain"],
            domain=doc.get("domain"),
            status=TenantStatus(doc["status"]),
            subscription_plan=SubscriptionPlan(doc["subscription_plan"]),
            settings=doc.get("settings", {}),
            created_at=datetime.fromisoformat(doc["created_at"]),
            trial_ends_at=datetime.fromisoformat(doc["trial_ends_at"]) if doc.get("trial_ends_at") else None,
            user_count=user_count,
            admin_count=admin_count
        )