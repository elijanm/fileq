# rbac_services.py - Role and Permission Management Services

from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
import logging
from enum import Enum
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)

class RoleType(str, Enum):
    SYSTEM = "system"
    CUSTOM = "custom"
    TENANT_SPECIFIC = "tenant_specific"

class PermissionCategory(str, Enum):
    USER_MANAGEMENT = "user_management"
    TENANT_MANAGEMENT = "tenant_management"
    RBAC = "rbac"
    SECURITY = "security"
    INTEGRATIONS = "integrations"
    SYSTEM = "system"

@dataclass
class Permission:
    name: str
    resource: str
    action: str
    description: str
    category: PermissionCategory
    is_system_permission: bool = True
    created_at: Optional[datetime] = None

@dataclass
class Role:
    name: str
    display_name: str
    description: str
    type: RoleType
    permissions: List[str]
    tenant_id: Optional[ObjectId] = None
    inherits_from: Optional[List[ObjectId]] = None
    is_system_role: bool = False
    is_default: bool = False
    created_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class RBACException(Exception):
    """Base exception for RBAC operations"""
    pass

class PermissionDenied(RBACException):
    """Raised when user lacks required permission"""
    pass

class RoleNotFound(RBACException):
    """Raised when role is not found"""
    pass

class PermissionNotFound(RBACException):
    """Raised when permission is not found"""
    pass

def require_permission(permission: str, tenant_id: Optional[str] = None):
    """Decorator to enforce permission requirements on methods"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Extract user_id from self or kwargs
            user_id = getattr(self, 'current_user_id', None) or kwargs.get('user_id')
            if not user_id:
                raise PermissionDenied("No user context available")
            
            if not self.has_permission(user_id, permission, tenant_id):
                raise PermissionDenied(f"User {user_id} lacks permission: {permission}")
            
            return func(self, *args, **kwargs)
        return wrapper
    return decorator

class PermissionService:
    """Service for managing permissions"""
    
    def __init__(self, db: Database):
        self.db = db
        self.permissions: Collection = db.permissions
        
    def create_permission(
        self, 
        permission: Permission,
        created_by: Optional[str] = None
    ) -> str:
        """Create a new permission"""
        try:
            permission_doc = {
                "name": permission.name,
                "resource": permission.resource,
                "action": permission.action,
                "description": permission.description,
                "category": permission.category.value,
                "is_system_permission": permission.is_system_permission,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            result = self.permissions.insert_one(permission_doc)
            
            logger.info(f"Permission {permission.name} created by {created_by}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Failed to create permission {permission.name}: {str(e)}")
            raise RBACException(f"Failed to create permission: {str(e)}")
    
    def get_permission(self, name: str) -> Optional[Dict[str, Any]]:
        """Get permission by name"""
        return self.permissions.find_one({"name": name})
    
    def list_permissions(
        self, 
        category: Optional[PermissionCategory] = None,
        is_system: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """List permissions with optional filtering"""
        query = {}
        if category:
            query["category"] = category.value
        if is_system is not None:
            query["is_system_permission"] = is_system
            
        return list(self.permissions.find(query).sort("category", 1))
    
    def delete_permission(self, name: str, deleted_by: str) -> bool:
        """Delete a permission (only non-system permissions)"""
        permission = self.get_permission(name)
        if not permission:
            raise PermissionNotFound(f"Permission {name} not found")
        
        if permission.get("is_system_permission", False):
            raise RBACException("Cannot delete system permissions")
        
        result = self.permissions.delete_one({"name": name})
        
        if result.deleted_count > 0:
            logger.info(f"Permission {name} deleted by {deleted_by}")
            return True
        return False

class RoleService:
    """Service for managing roles"""
    
    def __init__(self, db: Database):
        self.db = db
        self.roles: Collection = db.roles
        self.permissions_service = PermissionService(db)
        
    def create_role(
        self, 
        role: Role, 
        created_by: Optional[str] = None
    ) -> str:
        """Create a new role"""
        try:
            # Validate permissions exist
            self._validate_permissions(role.permissions)
            
            role_doc = {
                "name": role.name,
                "display_name": role.display_name,
                "description": role.description,
                "type": role.type.value,
                "tenant_id": role.tenant_id,
                "permissions": role.permissions,
                "inherits_from": role.inherits_from,
                "is_system_role": role.is_system_role,
                "is_default": role.is_default,
                "created_by": created_by,
                "metadata": role.metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None
            }
            
            result = self.roles.insert_one(role_doc)
            
            logger.info(f"Role {role.name} created by {created_by}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Failed to create role {role.name}: {str(e)}")
            raise RBACException(f"Failed to create role: {str(e)}")
    
    def get_role(
        self, 
        name: str, 
        tenant_id: Optional[ObjectId] = None
    ) -> Optional[Dict[str, Any]]:
        """Get role by name and optional tenant"""
        query = {"name": name}
        if tenant_id:
            query["tenant_id"] = tenant_id
        else:
            query["tenant_id"] = None
            
        return self.roles.find_one(query)
    
    def get_role_by_id(self, role_id: ObjectId) -> Optional[Dict[str, Any]]:
        """Get role by ID"""
        return self.roles.find_one({"_id": role_id})
    
    def list_roles(
        self, 
        tenant_id: Optional[ObjectId] = None,
        role_type: Optional[RoleType] = None,
        is_system: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """List roles with optional filtering"""
        query = {}
        
        if tenant_id:
            query["$or"] = [
                {"tenant_id": tenant_id},
                {"tenant_id": None, "type": "system"}  # Include system roles
            ]
        elif tenant_id is None:
            query["tenant_id"] = None
            
        if role_type:
            query["type"] = role_type.value
        if is_system is not None:
            query["is_system_role"] = is_system
            
        return list(self.roles.find(query).sort("name", 1))
    
    def update_role(
        self, 
        role_id: ObjectId, 
        updates: Dict[str, Any],
        updated_by: str
    ) -> bool:
        """Update role"""
        role = self.get_role_by_id(role_id)
        if not role:
            raise RoleNotFound(f"Role {role_id} not found")
        
        if role.get("is_system_role", False):
            # Restrict updates to system roles
            allowed_updates = {"display_name", "description", "metadata"}
            if not set(updates.keys()).issubset(allowed_updates):
                raise RBACException("Cannot modify permissions of system roles")
        
        # Validate permissions if being updated
        if "permissions" in updates:
            self._validate_permissions(updates["permissions"])
        
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = self.roles.update_one(
            {"_id": role_id},
            {"$set": updates}
        )
        
        if result.modified_count > 0:
            logger.info(f"Role {role_id} updated by {updated_by}")
            return True
        return False
    
    def delete_role(self, role_id: ObjectId, deleted_by: str) -> bool:
        """Delete role (only custom roles)"""
        role = self.get_role_by_id(role_id)
        if not role:
            raise RoleNotFound(f"Role {role_id} not found")
        
        if role.get("is_system_role", False):
            raise RBACException("Cannot delete system roles")
        
        # Check if role is in use
        users_with_role = self.db.tenant_users.count_documents({
            "custom_role_id": role_id
        })
        
        if users_with_role > 0:
            raise RBACException(f"Cannot delete role: {users_with_role} users assigned")
        
        result = self.roles.delete_one({"_id": role_id})
        
        if result.deleted_count > 0:
            logger.info(f"Role {role_id} deleted by {deleted_by}")
            return True
        return False
    
    def get_effective_permissions(
        self, 
        role_id: ObjectId,
        visited: Optional[Set[ObjectId]] = None
    ) -> List[str]:
        """Get all permissions for a role including inherited permissions"""
        if visited is None:
            visited = set()
        
        if role_id in visited:
            # Circular inheritance detected
            logger.warning(f"Circular role inheritance detected for role {role_id}")
            return []
        
        visited.add(role_id)
        
        role = self.get_role_by_id(role_id)
        if not role:
            return []
        
        permissions = set(role.get("permissions", []))
        
        # Add inherited permissions
        inherits_from = role.get("inherits_from", [])
        if inherits_from:
            for parent_role_id in inherits_from:
                if isinstance(parent_role_id, str):
                    parent_role_id = ObjectId(parent_role_id)
                parent_permissions = self.get_effective_permissions(
                    parent_role_id, visited.copy()
                )
                permissions.update(parent_permissions)
        
        return list(permissions)
    
    def _validate_permissions(self, permissions: List[str]) -> None:
        """Validate that all permissions exist"""
        for perm in permissions:
            if not self.permissions_service.get_permission(perm):
                raise PermissionNotFound(f"Permission {perm} does not exist")

class UserPermissionService:
    """Service for managing user permissions and role assignments"""
    
    def __init__(self, db: Database):
        self.db = db
        self.users: Collection = db.users
        self.tenant_users: Collection = db.tenant_users
        self.role_service = RoleService(db)
        self.current_user_id: Optional[str] = None
    
    def set_current_user(self, user_id: str) -> None:
        """Set the current user context for permission checks"""
        self.current_user_id = user_id
    
    def has_permission(
        self, 
        user_id: str, 
        permission: str, 
        tenant_id: Optional[str] = None
    ) -> bool:
        """Check if user has a specific permission"""
        try:
            user = self.users.find_one({"kratos_id": user_id})
            if not user:
                return False
            
            # Superadmin has all permissions
            if user.get("global_role") == "superadmin":
                return True
            
            # Check global permissions
            global_permissions = user.get("global_permissions", [])
            if permission in global_permissions:
                return True
            
            # Check tenant-specific permissions
            if tenant_id:
                tenant_user = self.tenant_users.find_one({
                    "user_id": user_id,
                    "tenant_id": ObjectId(tenant_id),
                    "status": "active"
                })
                
                if tenant_user:
                    # Check direct tenant permissions
                    tenant_permissions = tenant_user.get("permissions", [])
                    if permission in tenant_permissions:
                        return True
                    
                    # Check role-based permissions
                    role_permissions = self._get_user_role_permissions(
                        tenant_user, tenant_id
                    )
                    if permission in role_permissions:
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking permission {permission} for user {user_id}: {str(e)}")
            return False
    
    def has_any_permission(
        self, 
        user_id: str, 
        permissions: List[str], 
        tenant_id: Optional[str] = None
    ) -> bool:
        """Check if user has any of the specified permissions"""
        return any(
            self.has_permission(user_id, perm, tenant_id) 
            for perm in permissions
        )
    
    def has_all_permissions(
        self, 
        user_id: str, 
        permissions: List[str], 
        tenant_id: Optional[str] = None
    ) -> bool:
        """Check if user has all of the specified permissions"""
        return all(
            self.has_permission(user_id, perm, tenant_id) 
            for perm in permissions
        )
    
    @require_permission("roles:assign")
    def assign_role_to_user(
        self, 
        user_id: str, 
        role_name: str, 
        tenant_id: Optional[str] = None,
        assigned_by: Optional[str] = None
    ) -> bool:
        """Assign a role to a user"""
        try:
            if tenant_id:
                # Tenant-specific role assignment
                role = self.role_service.get_role(
                    role_name, 
                    ObjectId(tenant_id) if tenant_id else None
                )
                if not role:
                    raise RoleNotFound(f"Role {role_name} not found for tenant {tenant_id}")
                
                result = self.tenant_users.update_one(
                    {
                        "user_id": user_id,
                        "tenant_id": ObjectId(tenant_id)
                    },
                    {
                        "$set": {
                            "role": role_name,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
                
                success = result.modified_count > 0
            else:
                # Global role assignment
                result = self.users.update_one(
                    {"kratos_id": user_id},
                    {
                        "$set": {
                            "global_role": role_name,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
                
                success = result.modified_count > 0
            
            if success:
                logger.info(f"Role {role_name} assigned to user {user_id} by {assigned_by}")
                
                # Log audit event
                self._log_audit_event(
                    "role_assigned",
                    user_id,
                    assigned_by,
                    tenant_id,
                    {"role": role_name}
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to assign role {role_name} to user {user_id}: {str(e)}")
            raise RBACException(f"Failed to assign role: {str(e)}")
    
    @require_permission("users:write")
    def add_permission_to_user(
        self, 
        user_id: str, 
        permission: str, 
        tenant_id: Optional[str] = None,
        granted_by: Optional[str] = None
    ) -> bool:
        """Add a specific permission to a user"""
        try:
            if tenant_id:
                # Add to tenant-specific permissions
                result = self.tenant_users.update_one(
                    {
                        "user_id": user_id,
                        "tenant_id": ObjectId(tenant_id)
                    },
                    {
                        "$addToSet": {"permissions": permission},
                        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                    }
                )
            else:
                # Add to global permissions
                result = self.users.update_one(
                    {"kratos_id": user_id},
                    {
                        "$addToSet": {"global_permissions": permission},
                        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                    }
                )
            
            success = result.modified_count > 0
            
            if success:
                logger.info(f"Permission {permission} granted to user {user_id} by {granted_by}")
                
                # Log audit event
                self._log_audit_event(
                    "permission_granted",
                    user_id,
                    granted_by,
                    tenant_id,
                    {"permission": permission}
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to add permission {permission} to user {user_id}: {str(e)}")
            raise RBACException(f"Failed to add permission: {str(e)}")
    
    @require_permission("users:write")
    def remove_permission_from_user(
        self, 
        user_id: str, 
        permission: str, 
        tenant_id: Optional[str] = None,
        removed_by: Optional[str] = None
    ) -> bool:
        """Remove a specific permission from a user"""
        try:
            if tenant_id:
                # Remove from tenant-specific permissions
                result = self.tenant_users.update_one(
                    {
                        "user_id": user_id,
                        "tenant_id": ObjectId(tenant_id)
                    },
                    {
                        "$pull": {"permissions": permission},
                        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                    }
                )
            else:
                # Remove from global permissions
                result = self.users.update_one(
                    {"kratos_id": user_id},
                    {
                        "$pull": {"global_permissions": permission},
                        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                    }
                )
            
            success = result.modified_count > 0
            
            if success:
                logger.info(f"Permission {permission} removed from user {user_id} by {removed_by}")
                
                # Log audit event
                self._log_audit_event(
                    "permission_revoked",
                    user_id,
                    removed_by,
                    tenant_id,
                    {"permission": permission}
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to remove permission {permission} from user {user_id}: {str(e)}")
            raise RBACException(f"Failed to remove permission: {str(e)}")
    
    def get_user_permissions(
        self, 
        user_id: str, 
        tenant_id: Optional[str] = None
    ) -> List[str]:
        """Get all effective permissions for a user"""
        try:
            permissions = set()
            
            user = self.users.find_one({"kratos_id": user_id})
            if not user:
                return []
            
            # Superadmin gets all permissions
            if user.get("global_role") == "superadmin":
                all_permissions = self.db.permissions.find({}, {"name": 1})
                return [perm["name"] for perm in all_permissions]
            
            # Add global permissions
            global_permissions = user.get("global_permissions", [])
            permissions.update(global_permissions)
            
            # Add global role permissions
            global_role = user.get("global_role")
            if global_role:
                role = self.role_service.get_role(global_role)
                if role:
                    role_permissions = self.role_service.get_effective_permissions(
                        role["_id"]
                    )
                    permissions.update(role_permissions)
            
            # Add tenant-specific permissions
            if tenant_id:
                tenant_user = self.tenant_users.find_one({
                    "user_id": user_id,
                    "tenant_id": ObjectId(tenant_id),
                    "status": "active"
                })
                
                if tenant_user:
                    # Add direct tenant permissions
                    tenant_permissions = tenant_user.get("permissions", [])
                    permissions.update(tenant_permissions)
                    
                    # Add tenant role permissions
                    role_permissions = self._get_user_role_permissions(
                        tenant_user, tenant_id
                    )
                    permissions.update(role_permissions)
            
            return list(permissions)
            
        except Exception as e:
            logger.error(f"Error getting permissions for user {user_id}: {str(e)}")
            return []
    
    def get_users_with_permission(
        self, 
        permission: str, 
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all users who have a specific permission"""
        users_with_permission = []
        
        # Find users with global permission or superadmin role
        global_query = {
            "$or": [
                {"global_role": "superadmin"},
                {"global_permissions": permission}
            ]
        }
        
        global_users = self.users.find(global_query)
        for user in global_users:
            users_with_permission.append({
                "user_id": user["kratos_id"],
                "email": user["email"],
                "source": "global",
                "role": user.get("global_role"),
                "tenant_id": None
            })
        
        # Find users with tenant-specific permission
        if tenant_id:
            tenant_query = {
                "tenant_id": ObjectId(tenant_id),
                "status": "active",
                "$or": [
                    {"permissions": permission}
                ]
            }
            
            tenant_users = self.tenant_users.find(tenant_query)
            for tenant_user in tenant_users:
                user = self.users.find_one({"kratos_id": tenant_user["user_id"]})
                if user:
                    users_with_permission.append({
                        "user_id": user["kratos_id"],
                        "email": user["email"],
                        "source": "tenant",
                        "role": tenant_user.get("role"),
                        "tenant_id": tenant_id
                    })
        
        return users_with_permission
    
    def _get_user_role_permissions(
        self, 
        tenant_user: Dict[str, Any], 
        tenant_id: str
    ) -> List[str]:
        """Get permissions from user's role in tenant"""
        permissions = []
        
        # Get permissions from role
        role_name = tenant_user.get("role")
        if role_name:
            role = self.role_service.get_role(role_name, ObjectId(tenant_id))
            if role:
                permissions.extend(
                    self.role_service.get_effective_permissions(role["_id"])
                )
        
        # Get permissions from custom role
        custom_role_id = tenant_user.get("custom_role_id")
        if custom_role_id:
            permissions.extend(
                self.role_service.get_effective_permissions(custom_role_id)
            )
        
        return permissions
    
    def _log_audit_event(
        self, 
        event_type: str, 
        target_user_id: str, 
        admin_user_id: Optional[str],
        tenant_id: Optional[str], 
        details: Dict[str, Any]
    ) -> None:
        """Log an audit event"""
        try:
            audit_doc = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "tenant_id": ObjectId(tenant_id) if tenant_id else None,
                "user_id": None,
                "target_user_id": target_user_id,
                "admin_user_id": admin_user_id,
                "ip_address": None,  # Would be populated from request context
                "user_agent": None,  # Would be populated from request context
                "details": details,
                "severity": "info",
                "session_id": None,  # Would be populated from request context
                "action": event_type,
                "resource": "rbac",
                "before_state": None,
                "after_state": details,
                "correlation_id": f"{event_type}_{datetime.now().timestamp()}"
            }
            
            self.db.audit_logs.insert_one(audit_doc)
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {str(e)}")

# Utility functions for common permission patterns

def check_tenant_access(user_id: str, tenant_id: str, db: Database) -> bool:
    """Check if user has any access to a tenant"""
    user_permission_service = UserPermissionService(db)
    
    # Check if user is in tenant
    tenant_user = db.tenant_users.find_one({
        "user_id": user_id,
        "tenant_id": ObjectId(tenant_id),
        "status": "active"
    })
    
    return tenant_user is not None

def get_user_tenants(user_id: str, db: Database) -> List[Dict[str, Any]]:
    """Get all tenants a user has access to"""
    tenant_users = db.tenant_users.find({
        "user_id": user_id,
        "status": "active"
    })
    
    tenant_ids = [tu["tenant_id"] for tu in tenant_users]
    
    if not tenant_ids:
        return []
    
    tenants = db.tenants.find({
        "_id": {"$in": tenant_ids},
        "status": {"$in": ["active", "trial"]}
    })
    
    return list(tenants)

def is_tenant_admin(user_id: str, tenant_id: str, db: Database) -> bool:
    """Check if user is an admin of a specific tenant"""
    tenant_user = db.tenant_users.find_one({
        "user_id": user_id,
        "tenant_id": ObjectId(tenant_id),
        "status": "active",
        "role": {"$in": ["owner", "admin"]}
    })
    
    return tenant_user is not None

def can_manage_user(
    admin_user_id: str, 
    target_user_id: str, 
    tenant_id: Optional[str],
    db: Database
) -> bool:
    """Check if admin can manage another user"""
    user_permission_service = UserPermissionService(db)
    
    # Superadmin can manage anyone
    admin_user = db.users.find_one({"kratos_id": admin_user_id})
    if admin_user and admin_user.get("global_role") == "superadmin":
        return True
    
    # Check if admin has user management permissions
    if not user_permission_service.has_permission(
        admin_user_id, 
        "users:write", 
        tenant_id
    ):
        return False
    
    # Admin cannot manage users with higher privileges
    target_user = db.users.find_one({"kratos_id": target_user_id})
    if target_user and target_user.get("global_role") == "superadmin":
        return False
    
    # In tenant context, check role hierarchy
    if tenant_id:
        admin_tenant_user = db.tenant_users.find_one({
            "user_id": admin_user_id,
            "tenant_id": ObjectId(tenant_id),
            "status": "active"
        })
        
        target_tenant_user = db.tenant_users.find_one({
            "user_id": target_user_id,
            "tenant_id": ObjectId(tenant_id),
            "status": "active"
        })
        
        if not admin_tenant_user or not target_tenant_user:
            return False
        
        admin_role = admin_tenant_user.get("role")
        target_role = target_tenant_user.get("role")
        
        # Role hierarchy: owner > admin > user > guest
        role_hierarchy = {"guest": 1, "user": 2, "admin": 3, "owner": 4}
        
        admin_level = role_hierarchy.get(admin_role, 0)
        target_level = role_hierarchy.get(target_role, 0)
        
        return admin_level > target_level
    
    return True