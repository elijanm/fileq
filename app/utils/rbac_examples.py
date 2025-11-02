# rbac_examples.py - Usage examples and integration patterns

from typing import Optional, List, Dict, Any
from pymongo import MongoClient
from bson import ObjectId
import logging
from datetime import datetime, timezone

# Import our RBAC services
from rbac_services import (
    PermissionService, RoleService, UserPermissionService,
    Permission, Role, RoleType, PermissionCategory,
    PermissionDenied, RoleNotFound, require_permission
)
from rbac_utilities import (
    PermissionMatrix, RBACCache, PermissionBuilder, AuditLogger,
    RoleTemplates, PermissionValidator, RBACMetrics,
    check_tenant_access, get_user_tenants, is_tenant_admin, can_manage_user
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RBACManager:
    """Main manager class that orchestrates all RBAC operations"""
    
    def __init__(self, mongo_uri: str, database_name: str = "auth_db"):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[database_name]
        
        # Initialize services
        self.permission_service = PermissionService(self.db)
        self.role_service = RoleService(self.db)
        self.user_permission_service = UserPermissionService(self.db)
        
        # Initialize utilities
        self.cache = RBACCache()
        self.audit_logger = AuditLogger(self.db)
        self.metrics = RBACMetrics(self.db)
        
        # Current user context (would typically come from JWT/session)
        self.current_user_id: Optional[str] = None
        self.current_tenant_id: Optional[str] = None
    
    def set_context(self, user_id: str, tenant_id: Optional[str] = None):
        """Set the current user and tenant context"""
        self.current_user_id = user_id
        self.current_tenant_id = tenant_id
        self.user_permission_service.set_current_user(user_id)
    
    # === PERMISSION MANAGEMENT ===
    
    def create_custom_permission(
        self, 
        name: str, 
        resource: str, 
        action: str, 
        description: str,
        category: PermissionCategory = PermissionCategory.SYSTEM
    ) -> str:
        """Create a custom permission"""
        permission = Permission(
            name=name,
            resource=resource,
            action=action,
            description=description,
            category=category,
            is_system_permission=False
        )
        
        return self.permission_service.create_permission(
            permission, 
            created_by=self.current_user_id
        )
    
    def list_available_permissions(self, category: Optional[PermissionCategory] = None) -> List[Dict[str, Any]]:
        """List all available permissions"""
        return self.permission_service.list_permissions(category=category)
    
    # === ROLE MANAGEMENT ===
    
    def create_tenant_role(
        self, 
        name: str, 
        display_name: str, 
        description: str,
        permissions: List[str],
        tenant_id: str
    ) -> str:
        """Create a tenant-specific role"""
        # Validate permissions exist
        available_perms = [p["name"] for p in self.list_available_permissions()]
        is_valid, errors = PermissionValidator.validate_role_permissions(permissions, available_perms)
        
        if not is_valid:
            raise ValueError(f"Invalid permissions: {', '.join(errors)}")
        
        role = Role(
            name=name,
            display_name=display_name,
            description=description,
            type=RoleType.TENANT_SPECIFIC,
            permissions=permissions,
            tenant_id=ObjectId(tenant_id),
            created_by=self.current_user_id
        )
        
        role_id = self.role_service.create_role(role, created_by=self.current_user_id)
        
        # Log the creation
        self.audit_logger.log_role_change(
            target_user_id="",  # Not user-specific
            old_role=None,
            new_role=name,
            admin_user_id=self.current_user_id,
            tenant_id=tenant_id
        )
        
        return role_id
    
    def create_role_from_template(self, template_name: str, tenant_id: Optional[str] = None) -> str:
        """Create a role from a predefined template"""
        templates = {
            "basic_user": RoleTemplates.get_basic_user_role,
            "content_manager": RoleTemplates.get_content_manager_role,
            "tenant_admin": RoleTemplates.get_tenant_admin_role,
            "billing_admin": RoleTemplates.get_billing_admin_role,
            "support": RoleTemplates.get_support_role
        }
        
        if template_name not in templates:
            raise ValueError(f"Unknown template: {template_name}")
        
        role_data = templates[template_name]()
        
        role = Role(
            name=role_data["name"],
            display_name=role_data["display_name"],
            description=role_data["description"],
            type=RoleType.TENANT_SPECIFIC if tenant_id else RoleType.SYSTEM,
            permissions=role_data["permissions"],
            tenant_id=ObjectId(tenant_id) if tenant_id else None,
            created_by=self.current_user_id
        )
        
        return self.role_service.create_role(role, created_by=self.current_user_id)
    
    # === USER PERMISSION MANAGEMENT ===
    
    def assign_user_to_tenant(
        self, 
        user_id: str, 
        tenant_id: str, 
        role: str = "user",
        permissions: Optional[List[str]] = None
    ) -> bool:
        """Assign a user to a tenant with specified role and permissions"""
        # Check if current user can manage this tenant
        if not is_tenant_admin(self.current_user_id, tenant_id, self.db):
            if not self.has_permission("tenants:manage_users", tenant_id):
                raise PermissionDenied("Cannot manage users in this tenant")
        
        # Create tenant_user record
        tenant_user_doc = {
            "tenant_id": ObjectId(tenant_id),
            "user_id": user_id,
            "role": role,
            "status": "active",
            "permissions": permissions or [],
            "custom_role_id": None,
            "invited_by": self.current_user_id,
            "invited_at": datetime.now(timezone.utc).isoformat(),
            "joined_at": datetime.now(timezone.utc).isoformat(),
            "last_accessed": None,
            "access_granted_by": self.current_user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None
        }
        
        result = self.db.tenant_users.insert_one(tenant_user_doc)
        
        if result.inserted_id:
            # Clear user's permission cache
            self.cache.invalidate_user_cache(user_id, tenant_id)
            
            # Log the assignment
            self.audit_logger.log_role_change(
                target_user_id=user_id,
                old_role=None,
                new_role=role,
                admin_user_id=self.current_user_id,
                tenant_id=tenant_id
            )
            
            return True
        
        return False
    
    def change_user_role(
        self, 
        user_id: str, 
        new_role: str, 
        tenant_id: Optional[str] = None
    ) -> bool:
        """Change a user's role"""
        # Check permissions
        if not can_manage_user(self.current_user_id, user_id, tenant_id, self.db):
            raise PermissionDenied("Cannot manage this user")
        
        if tenant_id:
            # Get current role
            tenant_user = self.db.tenant_users.find_one({
                "user_id": user_id,
                "tenant_id": ObjectId(tenant_id)
            })
            
            if not tenant_user:
                raise ValueError("User not found in tenant")
            
            old_role = tenant_user.get("role")
            
            # Update role
            result = self.db.tenant_users.update_one(
                {"user_id": user_id, "tenant_id": ObjectId(tenant_id)},
                {
                    "$set": {
                        "role": new_role,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
        else:
            # Global role change
            user = self.db.users.find_one({"kratos_id": user_id})
            if not user:
                raise ValueError("User not found")
            
            old_role = user.get("global_role")
            
            result = self.db.users.update_one(
                {"kratos_id": user_id},
                {
                    "$set": {
                        "global_role": new_role,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
        
        if result.modified_count > 0:
            # Clear cache
            self.cache.invalidate_user_cache(user_id, tenant_id)
            
            # Log the change
            self.audit_logger.log_role_change(
                target_user_id=user_id,
                old_role=old_role,
                new_role=new_role,
                admin_user_id=self.current_user_id,
                tenant_id=tenant_id
            )
            
            return True
        
        return False
    
    def grant_permission(
        self, 
        user_id: str, 
        permission: str, 
        tenant_id: Optional[str] = None,
        temporary: bool = False,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """Grant a specific permission to a user"""
        success = self.user_permission_service.add_permission_to_user(
            user_id, 
            permission, 
            tenant_id, 
            granted_by=self.current_user_id
        )
        
        if success:
            # Clear cache
            self.cache.invalidate_user_cache(user_id, tenant_id)
            
            # Log the grant
            self.audit_logger.log_permission_grant(
                target_user_id=user_id,
                permission=permission,
                admin_user_id=self.current_user_id,
                tenant_id=tenant_id,
                temporary=temporary,
                expires_at=expires_at
            )
        
        return success
    
    def revoke_permission(
        self, 
        user_id: str, 
        permission: str, 
        tenant_id: Optional[str] = None
    ) -> bool:
        """Revoke a specific permission from a user"""
        success = self.user_permission_service.remove_permission_from_user(
            user_id, 
            permission, 
            tenant_id, 
            removed_by=self.current_user_id
        )
        
        if success:
            # Clear cache
            self.cache.invalidate_user_cache(user_id, tenant_id)
        
        return success
    
    # === PERMISSION CHECKING ===
    
    def has_permission(
        self, 
        permission: str, 
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Check if user has permission (uses current user if not specified)"""
        check_user_id = user_id or self.current_user_id
        if not check_user_id:
            return False
        
        # Try cache first
        cached_permissions = self.cache.get_user_permissions(check_user_id, tenant_id)
        if cached_permissions is not None:
            has_perm = permission in cached_permissions or \
                      PermissionMatrix.has_implicit_permission(cached_permissions, permission)
        else:
            # Get from database
            user_permissions = self.user_permission_service.get_user_permissions(check_user_id, tenant_id)
            self.cache.set_user_permissions(check_user_id, user_permissions, tenant_id)
            
            has_perm = self.user_permission_service.has_permission(check_user_id, permission, tenant_id)
        
        # Log permission check for audit
        self.audit_logger.log_permission_check(
            user_id=check_user_id,
            permission=permission,
            granted=has_perm,
            tenant_id=tenant_id
        )
        
        return has_perm
    
    def check_multiple_permissions(
        self, 
        permissions: List[str], 
        require_all: bool = True,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Check multiple permissions at once"""
        if require_all:
            return self.user_permission_service.has_all_permissions(
                self.current_user_id, permissions, tenant_id
            )
        else:
            return self.user_permission_service.has_any_permission(
                self.current_user_id, permissions, tenant_id
            )
    
    # === TENANT OPERATIONS ===
    
    def get_user_accessible_tenants(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all tenants accessible to a user"""
        check_user_id = user_id or self.current_user_id
        return get_user_tenants(check_user_id, self.db)
    
    def check_tenant_access(self, tenant_id: str, user_id: Optional[str] = None) -> bool:
        """Check if user can access a tenant"""
        check_user_id = user_id or self.current_user_id
        return check_tenant_access(check_user_id, tenant_id, self.db)
    
    def switch_tenant_context(self, tenant_id: str) -> bool:
        """Switch current tenant context"""
        if not self.check_tenant_access(tenant_id):
            raise PermissionDenied(f"No access to tenant {tenant_id}")
        
        self.current_tenant_id = tenant_id
        return True
    
    # === ANALYTICS AND REPORTING ===
    
    def get_permission_analytics(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get permission usage analytics"""
        return self.metrics.get_permission_usage_stats(tenant_id)
    
    def get_role_distribution(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get role distribution statistics"""
        return self.metrics.get_role_distribution(tenant_id)
    
    def get_user_access_report(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get detailed access report for a user"""
        return self.metrics.get_access_patterns(user_id, days)
    
    def audit_user_permissions(self, user_id: str) -> Dict[str, Any]:
        """Comprehensive audit of user permissions"""
        tenants = self.get_user_accessible_tenants(user_id)
        
        audit_report = {
            "user_id": user_id,
            "global_permissions": self.user_permission_service.get_user_permissions(user_id),
            "tenant_access": [],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        for tenant in tenants:
            tenant_id = str(tenant["_id"])
            tenant_permissions = self.user_permission_service.get_user_permissions(user_id, tenant_id)
            
            audit_report["tenant_access"].append({
                "tenant_id": tenant_id,
                "tenant_name": tenant["name"],
                "permissions": tenant_permissions,
                "is_admin": is_tenant_admin(user_id, tenant_id, self.db)
            })
        
        return audit_report


# === USAGE EXAMPLES ===

def example_basic_setup():
    """Example: Basic RBAC setup and usage"""
    # Initialize RBAC manager
    rbac = RBACManager("mongodb://localhost:27017")
    
    # Set user context (usually from JWT/session)
    rbac.set_context("superadmin_kratos_id")
    
    # Create a custom permission
    perm_id = rbac.create_custom_permission(
        name="reports:generate",
        resource="reports",
        action="generate",
        description="Generate custom reports",
        category=PermissionCategory.SYSTEM
    )
    print(f"Created permission: {perm_id}")
    
    # Create a tenant-specific role
    role_id = rbac.create_tenant_role(
        name="report_manager",
        display_name="Report Manager",
        description="Can generate and view reports",
        permissions=["reports:generate", "reports:read"],
        tenant_id="60f1b2c3d4e5f6789abc123"
    )
    print(f"Created role: {role_id}")
    
    # Assign user to tenant with role
    success = rbac.assign_user_to_tenant(
        user_id="user_kratos_id",
        tenant_id="60f1b2c3d4e5f6789abc123",
        role="report_manager"
    )
    print(f"User assigned: {success}")
    
    # Check permission
    has_perm = rbac.has_permission("reports:generate", "60f1b2c3d4e5f6789abc123")
    print(f"Has permission: {has_perm}")

def example_advanced_permission_management():
    """Example: Advanced permission management scenarios"""
    rbac = RBACManager("mongodb://localhost:27017")
    rbac.set_context("admin_user_id")
    
    # Build complex permission set
    builder = PermissionBuilder()
    permissions = (builder
                  .add_resource_permissions("users", ["read", "write"])
                  .add_resource_permissions("reports", ["read", "generate"])
                  .add_scoped_permission("data", "export", "own")
                  .build())
    
    print(f"Built permissions: {permissions}")
    
    # Create role from template
    role_id = rbac.create_role_from_template(
        "content_manager", 
        tenant_id="60f1b2c3d4e5f6789abc123"
    )
    
    # Grant temporary permission
    rbac.grant_permission(
        user_id="temp_user_id",
        permission="system:backup",
        temporary=True,
        expires_at=datetime.now(timezone.utc) + timezone.timedelta(hours=1)
    )
    
    # Check multiple permissions
    required_perms = ["users:read", "users:write", "reports:generate"]
    has_all = rbac.check_multiple_permissions(required_perms, require_all=True)
    print(f"Has all required permissions: {has_all}")

def example_tenant_management():
    """Example: Multi-tenant permission management"""
    rbac = RBACManager("mongodb://localhost:27017")
    rbac.set_context("tenant_admin_id")
    
    # Get user's accessible tenants
    tenants = rbac.get_user_accessible_tenants()
    print(f"Accessible tenants: {len(tenants)}")
    
    # Switch tenant context
    if tenants:
        tenant_id = str(tenants[0]["_id"])
        rbac.switch_tenant_context(tenant_id)
        print(f"Switched to tenant: {tenant_id}")
        
        # Check permission in new context
        can_manage_users = rbac.has_permission("users:write")
        print(f"Can manage users in this tenant: {can_manage_users}")
        
        # Change user role within tenant
        rbac.change_user_role(
            user_id="some_user_id",
            new_role="admin",
            tenant_id=tenant_id
        )

def example_audit_and_analytics():
    """Example: Audit and analytics functionality"""
    rbac = RBACManager("mongodb://localhost:27017")
    rbac.set_context("admin_user_id")
    
    # Get permission analytics
    analytics = rbac.get_permission_analytics("60f1b2c3d4e5f6789abc123")
    print("Permission Usage Analytics:")
    for stat in analytics["permission_stats"][:5]:  # Top 5
        print(f"  {stat['_id']}: {stat['total_checks']} checks")
    
    # Get role distribution
    distribution = rbac.get_role_distribution("60f1b2c3d4e5f6789abc123")
    print("\nRole Distribution:")
    for role_stat in distribution["role_distribution"]:
        print(f"  {role_stat['_id']}: {role_stat['count']} users")
    
    # Audit specific user
    audit_report = rbac.audit_user_permissions("user_to_audit")
    print(f"\nUser Audit Report:")
    print(f"  Global permissions: {len(audit_report['global_permissions'])}")
    print(f"  Tenant access: {len(audit_report['tenant_access'])}")

if __name__ == "__main__":
    # Run examples
    print("=== Basic Setup Example ===")
    example_basic_setup()
    
    print("\n=== Advanced Permission Management ===")
    example_advanced_permission_management()
    
    print("\n=== Tenant Management ===")
    example_tenant_management()
    
    print("\n=== Audit and Analytics ===")
    example_audit_and_analytics()