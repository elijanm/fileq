# rbac_utilities.py - Utility functions and helpers for RBAC system

from typing import List, Dict, Any, Optional, Set, Union, Tuple
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.database import Database
from dataclasses import dataclass
from functools import lru_cache
import logging
from enum import Enum
import json
import hashlib

logger = logging.getLogger(__name__)

class PermissionScope(str, Enum):
    GLOBAL = "global"
    TENANT = "tenant"
    RESOURCE = "resource"

class AuditAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    ASSIGN = "assign"
    REVOKE = "revoke"
    LOGIN = "login"
    LOGOUT = "logout"

@dataclass
class PermissionCheck:
    user_id: str
    permission: str
    tenant_id: Optional[str] = None
    resource_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

@dataclass
class RoleAssignment:
    user_id: str
    role_name: str
    tenant_id: Optional[str] = None
    assigned_by: Optional[str] = None
    assigned_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class PermissionMatrix:
    """Utility class for managing permission matrices and hierarchies"""
    
    # Define permission hierarchy (higher level includes lower level permissions)
    PERMISSION_HIERARCHY = {
        "write": ["read"],
        "delete": ["write", "read"],
        "admin": ["delete", "write", "read"],
        "owner": ["admin", "delete", "write", "read"]
    }
    
    # Define resource-specific permission patterns
    RESOURCE_PERMISSIONS = {
        "users": ["read", "write", "delete", "lock", "impersonate"],
        "tenants": ["read", "write", "delete", "manage_users", "manage_settings", "billing"],
        "roles": ["read", "write", "delete", "assign"],
        "audit": ["read", "export"],
        "webhooks": ["read", "write", "delete"],
        "integrations": ["read", "write", "delete"],
        "system": ["read", "write", "backup"]
    }
    
    @classmethod
    def get_implied_permissions(cls, permission: str) -> List[str]:
        """Get all permissions implied by a higher-level permission"""
        action = permission.split(":")[-1] if ":" in permission else permission
        return cls.PERMISSION_HIERARCHY.get(action, [])
    
    @classmethod
    def has_implicit_permission(cls, user_permissions: List[str], required_permission: str) -> bool:
        """Check if user has permission through hierarchy"""
        if required_permission in user_permissions:
            return True
        
        resource = required_permission.split(":")[0] if ":" in required_permission else ""
        action = required_permission.split(":")[-1] if ":" in required_permission else required_permission
        
        # Check for higher-level permissions that include this one
        for user_perm in user_permissions:
            user_resource = user_perm.split(":")[0] if ":" in user_perm else ""
            user_action = user_perm.split(":")[-1] if ":" in user_perm else user_perm
            
            if resource == user_resource or not resource:
                implied = cls.get_implied_permissions(user_action)
                if action in implied:
                    return True
        
        return False
    
    @classmethod
    def get_resource_permissions(cls, resource: str) -> List[str]:
        """Get all possible permissions for a resource"""
        base_permissions = cls.RESOURCE_PERMISSIONS.get(resource, [])
        return [f"{resource}:{perm}" for perm in base_permissions]

class RBACCache:
    """Caching utility for RBAC operations to improve performance"""
    
    def __init__(self, cache_ttl: int = 300):  # 5 minutes default
        self.cache_ttl = cache_ttl
        self._permission_cache = {}
        self._role_cache = {}
        self._user_cache = {}
    
    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """Check if cache entry is still valid"""
        return (datetime.now(timezone.utc) - timestamp).seconds < self.cache_ttl
    
    def get_user_permissions(self, user_id: str, tenant_id: Optional[str] = None) -> Optional[List[str]]:
        """Get cached user permissions"""
        cache_key = f"{user_id}:{tenant_id or 'global'}"
        cache_entry = self._permission_cache.get(cache_key)
        
        if cache_entry and self._is_cache_valid(cache_entry['timestamp']):
            return cache_entry['permissions']
        return None
    
    def set_user_permissions(self, user_id: str, permissions: List[str], tenant_id: Optional[str] = None):
        """Cache user permissions"""
        cache_key = f"{user_id}:{tenant_id or 'global'}"
        self._permission_cache[cache_key] = {
            'permissions': permissions,
            'timestamp': datetime.now(timezone.utc)
        }
    
    def invalidate_user_cache(self, user_id: str, tenant_id: Optional[str] = None):
        """Invalidate cached permissions for a user"""
        if tenant_id:
            cache_key = f"{user_id}:{tenant_id}"
            self._permission_cache.pop(cache_key, None)
        else:
            # Invalidate all caches for this user
            keys_to_remove = [k for k in self._permission_cache.keys() if k.startswith(f"{user_id}:")]
            for key in keys_to_remove:
                self._permission_cache.pop(key, None)
    
    def clear_cache(self):
        """Clear all caches"""
        self._permission_cache.clear()
        self._role_cache.clear()
        self._user_cache.clear()

class PermissionBuilder:
    """Builder class for creating complex permission structures"""
    
    def __init__(self):
        self.permissions = []
    
    def add_resource_permissions(self, resource: str, actions: List[str]) -> 'PermissionBuilder':
        """Add permissions for a specific resource"""
        for action in actions:
            self.permissions.append(f"{resource}:{action}")
        return self
    
    def add_wildcard_permission(self, resource: str) -> 'PermissionBuilder':
        """Add wildcard permission for a resource (all actions)"""
        self.permissions.append(f"{resource}:*")
        return self
    
    def add_scoped_permission(self, resource: str, action: str, scope: str) -> 'PermissionBuilder':
        """Add scoped permission (e.g., users:read:own)"""
        self.permissions.append(f"{resource}:{action}:{scope}")
        return self
    
    def build(self) -> List[str]:
        """Return the built permission list"""
        return list(set(self.permissions))  # Remove duplicates

class AuditLogger:
    """Enhanced audit logging utility"""
    
    def __init__(self, db: Database):
        self.db = db
        self.audit_logs = db.audit_logs
    
    def log_permission_check(
        self, 
        user_id: str, 
        permission: str, 
        granted: bool,
        tenant_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log permission check events"""
        self._create_audit_log(
            event_type="permission_check",
            user_id=user_id,
            tenant_id=tenant_id,
            details={
                "permission": permission,
                "granted": granted,
                "resource_id": resource_id
            },
            severity="info" if granted else "warning",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def log_role_change(
        self, 
        target_user_id: str, 
        old_role: Optional[str], 
        new_role: str,
        admin_user_id: str,
        tenant_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log role assignment changes"""
        self._create_audit_log(
            event_type="role_changed",
            target_user_id=target_user_id,
            admin_user_id=admin_user_id,
            tenant_id=tenant_id,
            details={
                "old_role": old_role,
                "new_role": new_role,
                "action": "role_assignment"
            },
            severity="info",
            ip_address=ip_address
        )
    
    def log_permission_grant(
        self, 
        target_user_id: str, 
        permission: str,
        admin_user_id: str,
        tenant_id: Optional[str] = None,
        temporary: bool = False,
        expires_at: Optional[datetime] = None
    ):
        """Log permission grants"""
        self._create_audit_log(
            event_type="permission_granted",
            target_user_id=target_user_id,
            admin_user_id=admin_user_id,
            tenant_id=tenant_id,
            details={
                "permission": permission,
                "temporary": temporary,
                "expires_at": expires_at.isoformat() if expires_at else None
            },
            severity="info"
        )
    
    def log_access_denied(
        self, 
        user_id: str, 
        attempted_action: str,
        resource: str,
        tenant_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log access denied events"""
        self._create_audit_log(
            event_type="access_denied",
            user_id=user_id,
            tenant_id=tenant_id,
            details={
                "attempted_action": attempted_action,
                "resource": resource,
                "reason": "insufficient_permissions"
            },
            severity="warning",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def _create_audit_log(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        target_user_id: Optional[str] = None,
        admin_user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Create audit log entry"""
        try:
            audit_doc = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "tenant_id": ObjectId(tenant_id) if tenant_id else None,
                "user_id": user_id,
                "target_user_id": target_user_id,
                "admin_user_id": admin_user_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "details": details or {},
                "severity": severity,
                "session_id": None,  # Would be populated from request context
                "action": event_type,
                "resource": "rbac",
                "before_state": None,
                "after_state": details,
                "correlation_id": self._generate_correlation_id(event_type)
            }
            
            self.audit_logs.insert_one(audit_doc)
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")
    
    def _generate_correlation_id(self, event_type: str) -> str:
        """Generate correlation ID for audit events"""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(f"{event_type}_{timestamp}".encode()).hexdigest()[:16]

class RoleTemplates:
    """Pre-defined role templates for common use cases"""
    
    @staticmethod
    def get_basic_user_role() -> Dict[str, Any]:
        """Basic user role with minimal permissions"""
        return {
            "name": "basic_user",
            "display_name": "Basic User",
            "description": "Standard user with basic access",
            "permissions": [
                "tenants:switch"
            ]
        }
    
    @staticmethod
    def get_content_manager_role() -> Dict[str, Any]:
        """Content manager role for managing content within tenant"""
        return {
            "name": "content_manager",
            "display_name": "Content Manager",
            "description": "Manage content and basic user operations",
            "permissions": [
                "users:read",
                "tenants:read",
                "tenants:switch"
            ]
        }
    
    @staticmethod
    def get_tenant_admin_role() -> Dict[str, Any]:
        """Tenant administrator role"""
        return {
            "name": "tenant_admin",
            "display_name": "Tenant Administrator",
            "description": "Full administrative access within tenant",
            "permissions": [
                "users:read", "users:write", "users:lock",
                "tenants:read", "tenants:manage_users", "tenants:manage_settings",
                "tenants:invite_users", "tenants:switch",
                "roles:read", "roles:assign",
                "audit:read",
                "webhooks:read", "webhooks:write",
                "integrations:read", "integrations:write"
            ]
        }
    
    @staticmethod
    def get_billing_admin_role() -> Dict[str, Any]:
        """Billing administrator role"""
        return {
            "name": "billing_admin",
            "display_name": "Billing Administrator",
            "description": "Manage billing and subscription settings",
            "permissions": [
                "users:read",
                "tenants:read", "tenants:billing", "tenants:switch",
                "audit:read"
            ]
        }
    
    @staticmethod
    def get_support_role() -> Dict[str, Any]:
        """Customer support role"""
        return {
            "name": "support",
            "display_name": "Support Agent",
            "description": "Customer support with limited admin access",
            "permissions": [
                "users:read", "users:lock",
                "tenants:read", "tenants:switch",
                "audit:read"
            ]
        }

class PermissionValidator:
    """Utility for validating permission patterns and structures"""
    
    VALID_PERMISSION_PATTERN = r'^[a-z_]+:[a-z_]+(?::[a-z_]+)?
    
    @staticmethod
    def validate_permission_format(permission: str) -> bool:
        """Validate permission string format"""
        import re
        return bool(re.match(PermissionValidator.VALID_PERMISSION_PATTERN, permission))
    
    @staticmethod
    def validate_role_permissions(permissions: List[str], available_permissions: List[str]) -> Tuple[bool, List[str]]:
        """Validate that all role permissions exist and are properly formatted"""
        invalid_permissions = []
        
        for perm in permissions:
            if not PermissionValidator.validate_permission_format(perm):
                invalid_permissions.append(f"Invalid format: {perm}")
            elif perm not in available_permissions and not perm.endswith(':*'):
                invalid_permissions.append(f"Permission not found: {perm}")
        
        return len(invalid_permissions) == 0, invalid_permissions
    
    @staticmethod
    def suggest_permissions(partial_permission: str, available_permissions: List[str]) -> List[str]:
        """Suggest permissions based on partial input"""
        suggestions = []
        for perm in available_permissions:
            if partial_permission.lower() in perm.lower():
                suggestions.append(perm)
        return suggestions[:10]  # Limit to 10 suggestions

class RBACMetrics:
    """Utility for gathering RBAC-related metrics and analytics"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_permission_usage_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics on permission usage"""
        pipeline = [
            {"$match": {"event_type": "permission_check"}},
            {"$group": {
                "_id": "$details.permission",
                "total_checks": {"$sum": 1},
                "granted": {"$sum": {"$cond": [{"$eq": ["$details.granted", True]}, 1, 0]}},
                "denied": {"$sum": {"$cond": [{"$eq": ["$details.granted", False]}, 1, 0]}}
            }},
            {"$sort": {"total_checks": -1}}
        ]
        
        if tenant_id:
            pipeline[0]["$match"]["tenant_id"] = ObjectId(tenant_id)
        
        results = list(self.db.audit_logs.aggregate(pipeline))
        
        return {
            "permission_stats": results,
            "total_permissions": len(results),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    
    def get_role_distribution(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get distribution of roles across users"""
        if tenant_id:
            pipeline = [
                {"$match": {"tenant_id": ObjectId(tenant_id)}},
                {"$group": {"_id": "$role", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            results = list(self.db.tenant_users.aggregate(pipeline))
        else:
            pipeline = [
                {"$group": {"_id": "$global_role", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            results = list(self.db.users.aggregate(pipeline))
        
        return {
            "role_distribution": results,
            "tenant_id": tenant_id,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    
    def get_access_patterns(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get access patterns for a specific user"""
        from_date = datetime.now(timezone.utc) - timezone.timedelta(days=days)
        
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "timestamp": {"$gte": from_date.isoformat()}
            }},
            {"$group": {
                "_id": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": {"$dateFromString": {"dateString": "$timestamp"}}}},
                    "event_type": "$event_type"
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id.date": -1}}
        ]
        
        results = list(self.db.audit_logs.aggregate(pipeline))
        
        return {
            "user_id": user_id,
            "access_patterns": results,
            "period_days": days,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

# Utility functions for common RBAC operations

def create_permission_hierarchy(permissions: List[str]) -> Dict[str, List[str]]:
    """Create a hierarchy map from a list of permissions"""
    hierarchy = {}
    
    for perm in permissions:
        parts = perm.split(':')
        if len(parts) >= 2:
            resource = parts[0]
            action = parts[1]
            
            if resource not in hierarchy:
                hierarchy[resource] = []
            
            if action not in hierarchy[resource]:
                hierarchy[resource].append(action)
    
    return hierarchy

def expand_wildcard_permissions(permissions: List[str], available_permissions: List[str]) -> List[str]:
    """Expand wildcard permissions to explicit permissions"""
    expanded = []
    
    for perm in permissions:
        if perm.endswith(':*'):
            resource = perm[:-2]
            # Find all permissions for this resource
            resource_perms = [p for p in available_permissions if p.startswith(f"{resource}:")]
            expanded.extend(resource_perms)
        else:
            expanded.append(perm)
    
    return list(set(expanded))  # Remove duplicates

def merge_permission_sets(*permission_sets: List[str]) -> List[str]:
    """Merge multiple permission sets, removing duplicates"""
    merged = set()
    for perm_set in permission_sets:
        merged.update(perm_set)
    return list(merged)

def filter_permissions_by_scope(
    permissions: List[str], 
    scope: PermissionScope,
    tenant_id: Optional[str] = None
) -> List[str]:
    """Filter permissions by scope (global, tenant, resource)"""
    filtered = []
    
    for perm in permissions:
        parts = perm.split(':')
        
        if scope == PermissionScope.GLOBAL:
            # Global permissions don't have tenant/resource scope
            if len(parts) == 2:
                filtered.append(perm)
        elif scope == PermissionScope.TENANT:
            # Tenant-scoped permissions
            if len(parts) >= 2:
                filtered.append(perm)
        elif scope == PermissionScope.RESOURCE:
            # Resource-scoped permissions
            if len(parts) == 3:
                filtered.append(perm)
    
    return filtered

def calculate_effective_permissions(
    user_permissions: List[str],
    role_permissions: List[str],
    inherited_permissions: List[str]
) -> List[str]:
    """Calculate effective permissions from all sources"""
    all_permissions = merge_permission_sets(
        user_permissions,
        role_permissions,
        inherited_permissions
    )
    
    # Apply permission hierarchy rules
    effective = []
    for perm in all_permissions:
        if PermissionMatrix.has_implicit_permission(all_permissions, perm):
            effective.append(perm)
    
    return list(set(effective))

def get_permission_conflicts(
    current_permissions: List[str],
    new_permissions: List[str]
) -> List[str]:
    """Identify potential permission conflicts"""
    conflicts = []
    
    # This is a simplified conflict detection
    # In practice, you might have more complex rules
    for new_perm in new_permissions:
        if new_perm in current_permissions:
            conflicts.append(f"Duplicate permission: {new_perm}")
    
    return conflicts