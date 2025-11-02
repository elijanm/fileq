# services/superadmin_service.py - Superadmin management service

from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import logging
from dataclasses import dataclass

from pymongo.collection import Collection
from .audit_service import AuditService

logger = logging.getLogger(__name__)

class Role(Enum):
    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"
    SUPPORT = "support"
    BILLING_ADMIN = "billing_admin"

class Permission(Enum):
    # User management
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"
    USERS_DELETE = "users:delete"
    USERS_LOCK = "users:lock"
    USERS_IMPERSONATE = "users:impersonate"
    
    # Admin operations
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"
    ADMIN_SYSTEM = "admin:system"
    
    # Audit logs
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    
    # Roles and permissions
    ROLES_READ = "roles:read"
    ROLES_WRITE = "roles:write"
    ROLES_DELETE = "roles:delete"
    ROLES_ASSIGN = "roles:assign"
    
    # Billing
    BILLING_READ = "billing:read"
    BILLING_WRITE = "billing:write"
    
    # System
    SYSTEM_READ = "system:read"
    SYSTEM_WRITE = "system:write"
    SYSTEM_BACKUP = "system:backup"

@dataclass
class AdminUser:
    user_id: str
    email: str
    name: str
    role: Role
    permissions: List[str]
    created_at: datetime
    last_login: Optional[datetime]
    is_active: bool
    account_locked: bool

@dataclass
class RoleDefinition:
    name: str
    display_name: str
    description: str
    permissions: List[str]
    is_system_role: bool

class SuperAdminService:
    """Service for superadmin operations and role-based access control"""
    
    def __init__(
        self,
        users_collection: Collection,
        roles_collection: Collection,
        permissions_collection: Collection,
        audit_service: AuditService
    ):
        self.users_collection = users_collection
        self.roles_collection = roles_collection
        self.permissions_collection = permissions_collection
        self.audit_service = audit_service
    
    # User Management
    async def get_all_users(
        self, 
        admin_user_id: str,
        page: int = 1,
        limit: int = 50,
        filter_role: Optional[str] = None,
        filter_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get all users with pagination and filtering (superadmin/admin only)"""
        # Check permissions
        if not await self.has_permission(admin_user_id, Permission.USERS_READ.value):
            raise PermissionError("Insufficient permissions to view users")
        
        # Build query
        query = {}
        if filter_role:
            query["role"] = filter_role
        if filter_status:
            query["status"] = filter_status
        
        # Get paginated results
        skip = (page - 1) * limit
        users_cursor = self.users_collection.find(query).skip(skip).limit(limit)
        total_count = self.users_collection.count_documents(query)
        
        users = []
        for user_doc in users_cursor:
            users.append(AdminUser(
                user_id=user_doc["kratos_id"],
                email=user_doc["email"],
                name=user_doc.get("name", ""),
                role=Role(user_doc.get("role", "user")),
                permissions=user_doc.get("permissions", []),
                created_at=datetime.fromisoformat(user_doc["created_at"]),
                last_login=datetime.fromisoformat(user_doc["last_login"]) if user_doc.get("last_login") else None,
                is_active=user_doc.get("status") == "active",
                account_locked=user_doc.get("account_locked", False)
            ))
        
        # Audit log
        await self.audit_service.log_event(
            "admin_users_viewed",
            user_id=admin_user_id,
            details={
                "total_users": total_count,
                "page": page,
                "filters": {"role": filter_role, "status": filter_status}
            }
        )
        
        return {
            "users": users,
            "total": total_count,
            "page": page,
            "pages": (total_count + limit - 1) // limit,
            "has_more": skip + limit < total_count
        }
    
    async def update_user_role(
        self,
        admin_user_id: str,
        target_user_id: str,
        new_role: str
    ) -> Dict[str, str]:
        """Update user role (superadmin only)"""
        # Only superadmin can change roles
        admin_user = self.users_collection.find_one({"kratos_id": admin_user_id})
        if not admin_user or admin_user.get("role") != "superadmin":
            raise PermissionError("Only superadmin can change user roles")
        
        # Validate new role
        try:
            role_enum = Role(new_role)
        except ValueError:
            raise ValueError(f"Invalid role: {new_role}")
        
        # Get target user
        target_user = self.users_collection.find_one({"kratos_id": target_user_id})
        if not target_user:
            raise ValueError("User not found")
        
        # Prevent superadmin from demoting themselves
        if admin_user_id == target_user_id and new_role != "superadmin":
            raise PermissionError("Cannot demote yourself from superadmin")
        
        # Get role permissions
        role_doc = self.roles_collection.find_one({"name": new_role})
        if not role_doc:
            raise ValueError(f"Role definition not found: {new_role}")
        
        # Update user
        old_role = target_user.get("role", "user")
        result = self.users_collection.update_one(
            {"kratos_id": target_user_id},
            {
                "$set": {
                    "role": new_role,
                    "permissions": role_doc["permissions"],
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
        )
        
        if result.matched_count == 0:
            raise ValueError("Failed to update user role")
        
        # Audit log
        await self.audit_service.log_event(
            "user_role_changed",
            user_id=admin_user_id,
            target_user_id=target_user_id,
            details={
                "target_email": target_user["email"],
                "old_role": old_role,
                "new_role": new_role,
                "permissions_granted": role_doc["permissions"]
            },
            severity="warning"
        )
        
        return {"message": f"User role updated to {new_role}"}
    
    async def force_unlock_account(
        self,
        admin_user_id: str,
        target_user_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, str]:
        """Force unlock user account (admin/superadmin)"""
        if not await self.has_permission(admin_user_id, Permission.USERS_LOCK.value):
            raise PermissionError("Insufficient permissions to unlock accounts")
        
        target_user = self.users_collection.find_one({"kratos_id": target_user_id})
        if not target_user:
            raise ValueError("User not found")
        
        result = self.users_collection.update_one(
            {"kratos_id": target_user_id},
            {
                "$set": {
                    "account_locked": False,
                    "failed_login_attempts": 0,
                    "status": "active",
                    "updated_at": datetime.utcnow().isoformat()
                },
                "$unset": {
                    "locked_at": "",
                    "locked_by": "",
                    "lock_reason": ""
                }
            }
        )
        
        if result.matched_count == 0:
            raise ValueError("Failed to unlock account")
        
        # Audit log
        await self.audit_service.log_event(
            "account_force_unlocked",
            user_id=admin_user_id,
            target_user_id=target_user_id,
            details={
                "target_email": target_user["email"],
                "reason": reason or "Force unlock by admin"
            },
            severity="warning"
        )
        
        return {"message": "Account unlocked successfully"}
    
    async def delete_user(
        self,
        admin_user_id: str,
        target_user_id: str,
        reason: str
    ) -> Dict[str, str]:
        """Delete user account (superadmin only)"""
        # Only superadmin can delete users
        admin_user = self.users_collection.find_one({"kratos_id": admin_user_id})
        if not admin_user or admin_user.get("role") != "superadmin":
            raise PermissionError("Only superadmin can delete users")
        
        # Prevent self-deletion
        if admin_user_id == target_user_id:
            raise PermissionError("Cannot delete your own account")
        
        target_user = self.users_collection.find_one({"kratos_id": target_user_id})
        if not target_user:
            raise ValueError("User not found")
        
        # Prevent deletion of other superadmins
        if target_user.get("role") == "superadmin":
            raise PermissionError("Cannot delete another superadmin account")
        
        # Soft delete - mark as deleted instead of actual deletion
        result = self.users_collection.update_one(
            {"kratos_id": target_user_id},
            {
                "$set": {
                    "status": "deleted",
                    "deleted_at": datetime.utcnow().isoformat(),
                    "deleted_by": admin_user_id,
                    "deletion_reason": reason,
                    "account_locked": True
                }
            }
        )
        
        if result.matched_count == 0:
            raise ValueError("Failed to delete user")
        
        # Audit log
        await self.audit_service.log_event(
            "user_deleted",
            user_id=admin_user_id,
            target_user_id=target_user_id,
            details={
                "target_email": target_user["email"],
                "target_role": target_user.get("role", "user"),
                "reason": reason
            },
            severity="critical"
        )
        
        return {"message": "User account deleted"}
    
    # Role Management
    async def get_all_roles(self, admin_user_id: str) -> List[RoleDefinition]:
        """Get all role definitions"""
        if not await self.has_permission(admin_user_id, Permission.ROLES_READ.value):
            raise PermissionError("Insufficient permissions to view roles")
        
        roles = []
        for role_doc in self.roles_collection.find({}):
            roles.append(RoleDefinition(
                name=role_doc["name"],
                display_name=role_doc["display_name"],
                description=role_doc["description"],
                permissions=role_doc["permissions"],
                is_system_role=role_doc.get("is_system_role", False)
            ))
        
        return roles
    
    async def create_custom_role(
        self,
        admin_user_id: str,
        name: str,
        display_name: str,
        description: str,
        permissions: List[str]
    ) -> Dict[str, str]:
        """Create custom role (superadmin only)"""
        admin_user = self.users_collection.find_one({"kratos_id": admin_user_id})
        if not admin_user or admin_user.get("role") != "superadmin":
            raise PermissionError("Only superadmin can create custom roles")
        
        # Check if role already exists
        if self.roles_collection.find_one({"name": name}):
            raise ValueError("Role already exists")
        
        # Validate permissions
        valid_permissions = [perm.value for perm in Permission]
        invalid_perms = [p for p in permissions if p not in valid_permissions]
        if invalid_perms:
            raise ValueError(f"Invalid permissions: {invalid_perms}")
        
        role_doc = {
            "name": name,
            "display_name": display_name,
            "description": description,
            "permissions": permissions,
            "is_system_role": False,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": admin_user_id
        }
        
        self.roles_collection.insert_one(role_doc)
        
        # Audit log
        await self.audit_service.log_event(
            "custom_role_created",
            user_id=admin_user_id,
            details={
                "role_name": name,
                "permissions": permissions,
                "display_name": display_name
            }
        )
        
        return {"message": f"Custom role '{name}' created successfully"}
    
    # System Operations
    async def get_system_stats(self, admin_user_id: str) -> Dict[str, Any]:
        """Get system statistics (admin/superadmin only)"""
        if not await self.has_permission(admin_user_id, Permission.SYSTEM_READ.value):
            raise PermissionError("Insufficient permissions to view system stats")
        
        # User statistics
        total_users = self.users_collection.count_documents({})
        active_users = self.users_collection.count_documents({"status": "active"})
        locked_users = self.users_collection.count_documents({"account_locked": True})
        pending_verification = self.users_collection.count_documents({"status": "pending_verification"})
        
        # Role distribution
        role_distribution = {}