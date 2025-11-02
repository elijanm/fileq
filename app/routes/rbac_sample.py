"""
RBAC (Role-Based Access Control) FastAPI Endpoint
Complete implementation for multi-tenant authentication system
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Path, Query, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Optional, Any, Union
from pymongo import MongoClient
from datetime import datetime
import logging
import os
from enum import Enum

# Import our auth utilities
from auth_utilities import AuthUtilities

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Multi-tenant RBAC API",
    description="Role-Based Access Control system for multi-tenant authentication",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security scheme
security = HTTPBearer()

# Database connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
client = MongoClient(MONGODB_URL)
auth_utils = AuthUtilities(client)

# =====================================
# PYDANTIC MODELS
# =====================================

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    OWNER = "owner"
    BILLING_ADMIN = "billing_admin"
    SUPPORT = "support"
    GUEST = "guest"

class GlobalRole(str, Enum):
    USER = "user"
    ADMIN = "admin" 
    SUPERADMIN = "superadmin"
    SUPPORT = "support"
    SYSTEM = "system"

class PermissionRequest(BaseModel):
    user_id: str = Field(..., description="User ID to check")
    permission: str = Field(..., description="Permission to check (e.g., 'users:read')")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for tenant-specific permissions")

class BulkPermissionRequest(BaseModel):
    user_ids: List[str] = Field(..., description="List of user IDs")
    permissions: List[str] = Field(..., description="List of permissions to check")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for tenant-specific permissions")

class RoleAssignmentRequest(BaseModel):
    user_id: str = Field(..., description="User ID to assign role to")
    role: str = Field(..., description="Role to assign")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for tenant-specific role")

class BulkRoleAssignmentRequest(BaseModel):
    user_ids: List[str] = Field(..., description="List of user IDs")
    role: str = Field(..., description="Role to assign")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for tenant-specific roles")

class TenantInvitationRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address to invite")
    role: UserRole = Field(..., description="Role to assign")
    permissions: Optional[List[str]] = Field(default=[], description="Additional permissions")
    message: Optional[str] = Field(None, description="Optional invitation message")
    expiry_hours: int = Field(72, ge=1, le=168, description="Invitation expiry in hours")

class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50, description="Role name")
    display_name: str = Field(..., min_length=2, max_length=100, description="Display name")
    description: str = Field(..., max_length=500, description="Role description")
    permissions: List[str] = Field(..., description="List of permissions")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for tenant-specific role")

class UpdateUserRequest(BaseModel):
    global_role: Optional[GlobalRole] = Field(None, description="New global role")
    is_locked: Optional[bool] = Field(None, description="Lock/unlock account")
    lock_reason: Optional[str] = Field(None, description="Reason for locking account")

class SessionInfo(BaseModel):
    user_id: str
    tenant_id: Optional[str]
    permissions: List[str]
    roles: Dict[str, Any]

# =====================================
# AUTHENTICATION AND AUTHORIZATION
# =====================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_tenant_id: Optional[str] = Header(None)
) -> SessionInfo:
    """
    Extract user information from JWT token and validate session
    This is a simplified version - implement proper JWT validation in production
    """
    try:
        token = credentials.credentials
        # TODO: Implement proper JWT validation with Kratos
        # For now, we'll use a simplified approach
        
        # In production, validate JWT with Kratos and extract user_id
        user_id = "extracted_from_jwt"  # Replace with actual JWT validation
        
        # Get user permissions
        permissions = auth_utils.get_user_effective_permissions(user_id, x_tenant_id)
        
        # Get user roles
        user_tenants = auth_utils.get_user_tenants(user_id) if x_tenant_id else []
        current_tenant_role = None
        if x_tenant_id:
            for tenant in user_tenants:
                if str(tenant["_id"]) == x_tenant_id:
                    current_tenant_role = tenant.get("user_role")
                    break
        
        roles = {
            "global_role": "user",  # Get from user document
            "tenant_role": current_tenant_role
        }
        
        return SessionInfo(
            user_id=user_id,
            tenant_id=x_tenant_id,
            permissions=permissions,
            roles=roles
        )
        
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication")

def require_permission(permission: str):
    """Decorator to require specific permission"""
    def permission_check(user: SessionInfo = Depends(get_current_user)):
        if permission not in user.permissions:
            raise HTTPException(
                status_code=403, 
                detail=f"Permission '{permission}' required"
            )
        return user
    return permission_check

def require_tenant_admin():
    """Decorator to require tenant admin role"""
    def admin_check(user: SessionInfo = Depends(get_current_user)):
        if not user.tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context required")
        
        if not auth_utils.is_tenant_admin(user.user_id, user.tenant_id):
            raise HTTPException(status_code=403, detail="Tenant admin role required")
        
        return user
    return admin_check

def require_superadmin():
    """Decorator to require superadmin role"""
    def superadmin_check(user: SessionInfo = Depends(get_current_user)):
        if user.roles.get("global_role") != "superadmin":
            raise HTTPException(status_code=403, detail="Superadmin role required")
        return user
    return superadmin_check

# =====================================
# PERMISSION CHECKING ENDPOINTS
# =====================================

@app.post("/api/rbac/check-permission", 
         summary="Check if user has specific permission",
         response_model=dict)
async def check_permission(
    request: PermissionRequest,
    current_user: SessionInfo = Depends(get_current_user)
):
    """Check if a user has a specific permission"""
    try:
        has_permission = auth_utils.user_has_permission(
            request.user_id, 
            request.permission, 
            request.tenant_id
        )
        
        # Log audit event
        auth_utils.log_audit_event(
            "permission_checked",
            current_user.user_id,
            {
                "target_user_id": request.user_id,
                "permission": request.permission,
                "result": has_permission
            },
            current_user.tenant_id
        )
        
        return {
            "user_id": request.user_id,
            "permission": request.permission,
            "tenant_id": request.tenant_id,
            "has_permission": has_permission
        }
        
    except Exception as e:
        logger.error(f"Error checking permission: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/rbac/check-permissions-bulk",
         summary="Check multiple permissions for multiple users",
         response_model=dict)
async def check_permissions_bulk(
    request: BulkPermissionRequest,
    current_user: SessionInfo = Depends(require_permission("users:read"))
):
    """Bulk check permissions for multiple users"""
    try:
        results = {}
        
        for user_id in request.user_ids:
            user_results = {}
            for permission in request.permissions:
                has_permission = auth_utils.user_has_permission(
                    user_id, 
                    permission, 
                    request.tenant_id
                )
                user_results[permission] = has_permission
            
            results[user_id] = user_results
        
        return {
            "tenant_id": request.tenant_id,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in bulk permission check: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/rbac/user/{user_id}/permissions",
        summary="Get all effective permissions for a user",
        response_model=dict)
async def get_user_permissions(
    user_id: str = Path(..., description="User ID"),
    tenant_id: Optional[str] = Query(None, description="Tenant ID"),
    current_user: SessionInfo = Depends(require_permission("users:read"))
):
    """Get all effective permissions for a user"""
    try:
        permissions = auth_utils.get_user_effective_permissions(user_id, tenant_id)
        
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "permissions": permissions,
            "permission_count": len(permissions)
        }
        
    except Exception as e:
        logger.error(f"Error getting user permissions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# =====================================
# ROLE MANAGEMENT ENDPOINTS
# =====================================

@app.post("/api/rbac/assign-role",
         summary="Assign role to user",
         response_model=dict)
async def assign_role(
    request: RoleAssignmentRequest,
    current_user: SessionInfo = Depends(require_permission("roles:assign"))
):
    """Assign a role to a user"""
    try:
        if request.tenant_id:
            # Tenant role assignment
            success = auth_utils.add_user_to_tenant(
                request.user_id,
                request.tenant_id,
                request.role,
                invited_by=current_user.user_id
            )
        else:
            # Global role assignment - requires superadmin
            if current_user.roles.get("global_role") != "superadmin":
                raise HTTPException(status_code=403, detail="Superadmin required for global role assignment")
            
            success = auth_utils.update_user_global_role(
                request.user_id,
                request.role,
                current_user.user_id
            )
        
        if not success:
            raise HTTPException(status_code=400, detail="Role assignment failed")
        
        return {
            "user_id": request.user_id,
            "role": request.role,
            "tenant_id": request.tenant_id,
            "assigned_by": current_user.user_id,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning role: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/rbac/assign-roles-bulk",
         summary="Bulk assign roles to multiple users", 
         response_model=dict)
async def assign_roles_bulk(
    request: BulkRoleAssignmentRequest,
    current_user: SessionInfo = Depends(require_permission("roles:assign"))
):
    """Bulk assign role to multiple users"""
    try:
        results = auth_utils.bulk_assign_role(
            request.user_ids,
            request.role,
            request.tenant_id,
            current_user.user_id
        )
        
        return {
            "role": request.role,
            "tenant_id": request.tenant_id,
            "assigned_by": current_user.user_id,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in bulk role assignment: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/rbac/roles",
         summary="Create custom role",
         response_model=dict)
async def create_role(
    request: CreateRoleRequest,
    current_user: SessionInfo = Depends(require_permission("roles:write"))
):
    """Create a custom role"""
    try:
        # Validate permissions exist
        for permission in request.permissions:
            validation = auth_utils.validate_permission_format(permission)
            if not validation["valid"]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid permission '{permission}': {validation['reason']}"
                )
        
        role_id = auth_utils.create_custom_role(
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            permissions=request.permissions,
            tenant_id=request.tenant_id,
            created_by=current_user.user_id
        )
        
        if not role_id:
            raise HTTPException(status_code=400, detail="Role creation failed")
        
        return {
            "role_id": role_id,
            "name": request.name,
            "display_name": request.display_name,
            "permissions": request.permissions,
            "tenant_id": request.tenant_id,
            "created_by": current_user.user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating role: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/rbac/roles/{role_name}/permissions",
        summary="Get permissions for a role",
        response_model=dict)
async def get_role_permissions(
    role_name: str = Path(..., description="Role name"),
    tenant_id: Optional[str] = Query(None, description="Tenant ID"),
    current_user: SessionInfo = Depends(require_permission("roles:read"))
):
    """Get all permissions for a role"""
    try:
        permissions = auth_utils.get_role_permissions(role_name, tenant_id)
        
        return {
            "role_name": role_name,
            "tenant_id": tenant_id,
            "permissions": permissions,
            "permission_count": len(permissions)
        }
        
    except Exception as e:
        logger.error(f"Error getting role permissions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# =====================================
# TENANT MANAGEMENT ENDPOINTS
# =====================================

@app.get("/api/rbac/tenants/{tenant_id}/users",
        summary="Get all users in a tenant",
        response_model=dict)
async def get_tenant_users(
    tenant_id: str = Path(..., description="Tenant ID"),
    role: Optional[str] = Query(None, description="Filter by role"),
    current_user: SessionInfo = Depends(require_permission("tenants:manage_users"))
):
    """Get all users in a tenant"""
    try:
        users = auth_utils.get_tenant_users(tenant_id, role)
        
        return {
            "tenant_id": tenant_id,
            "role_filter": role,
            "users": users,
            "user_count": len(users)
        }
        
    except Exception as e:
        logger.error(f"Error getting tenant users: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/rbac/tenants/{tenant_id}/invite",
         summary="Invite user to tenant",
         response_model=dict)
async def invite_user_to_tenant(
    tenant_id: str = Path(..., description="Tenant ID"),
    request: TenantInvitationRequest = Body(...),
    current_user: SessionInfo = Depends(require_permission("tenants:invite_users"))
):
    """Send an invitation to join a tenant"""
    try:
        invitation = auth_utils.create_tenant_invitation(
            tenant_id=tenant_id,
            email=request.email,
            role=request.role.value,
            invited_by=current_user.user_id,
            expiry_hours=request.expiry_hours,
            permissions=request.permissions,
            message=request.message
        )
        
        if not invitation:
            raise HTTPException(status_code=400, detail="Invitation creation failed")
        
        return {
            "tenant_id": tenant_id,
            "email": request.email,
            "role": request.role.value,
            "invitation_token": invitation["token"],
            "expires_at": invitation["expires_at"],
            "invited_by": current_user.user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating tenant invitation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/rbac/tenants/{tenant_id}/invitations",
        summary="Get pending invitations for tenant",
        response_model=dict)
async def get_tenant_invitations(
    tenant_id: str = Path(..., description="Tenant ID"),
    current_user: SessionInfo = Depends(require_tenant_admin())
):
    """Get all pending invitations for a tenant"""
    try:
        invitations = auth_utils.get_pending_invitations(tenant_id)
        
        # Remove sensitive tokens from response
        for invitation in invitations:
            invitation.pop("token", None)
        
        return {
            "tenant_id": tenant_id,
            "invitations": invitations,
            "invitation_count": len(invitations)
        }
        
    except Exception as e:
        logger.error(f"Error getting tenant invitations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/rbac/tenants/{tenant_id}/users/{user_id}",
           summary="Remove user from tenant",
           response_model=dict)
async def remove_user_from_tenant(
    tenant_id: str = Path(..., description="Tenant ID"),
    user_id: str = Path(..., description="User ID to remove"),
    current_user: SessionInfo = Depends(require_tenant_admin())
):
    """Remove a user from a tenant"""
    try:
        success = auth_utils.remove_user_from_tenant(
            user_id=user_id,
            tenant_id=tenant_id,
            removed_by=current_user.user_id
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="User removal failed")
        
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "removed_by": current_user.user_id,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing user from tenant: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# =====================================
# USER MANAGEMENT ENDPOINTS
# =====================================

@app.get("/api/rbac/users/{user_id}/tenants",
        summary="Get user's tenants",
        response_model=dict)
async def get_user_tenants(
    user_id: str = Path(..., description="User ID"),
    current_user: SessionInfo = Depends(require_permission("users:read"))
):
    """Get all tenants a user belongs to"""
    try:
        tenants = auth_utils.get_user_tenants(user_id)
        
        return {
            "user_id": user_id,
            "tenants": tenants,
            "tenant_count": len(tenants)
        }
        
    except Exception as e:
        logger.error(f"Error getting user tenants: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.patch("/api/rbac/users/{user_id}",
          summary="Update user account",
          response_model=dict)
async def update_user(
    user_id: str = Path(..., description="User ID"),
    request: UpdateUserRequest = Body(...),
    current_user: SessionInfo = Depends(require_permission("users:write"))
):
    """Update user account (role, lock status, etc.)"""
    try:
        updates = {}
        
        # Handle global role change
        if request.global_role:
            if current_user.roles.get("global_role") != "superadmin":
                raise HTTPException(status_code=403, detail="Superadmin required for global role changes")
            
            success = auth_utils.update_user_global_role(
                user_id, 
                request.global_role.value, 
                current_user.user_id
            )
            if success:
                updates["global_role"] = request.global_role.value
        
        # Handle account lock/unlock
        if request.is_locked is not None:
            if request.is_locked:
                reason = request.lock_reason or "Account locked by admin"
                success = auth_utils.lock_user_account(user_id, reason, current_user.user_id)
            else:
                success = auth_utils.unlock_user_account(user_id, current_user.user_id)
            
            if success:
                updates["is_locked"] = request.is_locked
        
        return {
            "user_id": user_id,
            "updates": updates,
            "updated_by": current_user.user_id,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# =====================================
# AUDIT AND MONITORING ENDPOINTS  
# =====================================

@app.get("/api/rbac/audit/recent",
        summary="Get recent audit activity",
        response_model=dict)
async def get_recent_activity(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
    current_user: SessionInfo = Depends(require_permission("audit:read"))
):
    """Get recent audit activity"""
    try:
        activity = auth_utils.get_recent_activity(tenant_id, hours)
        
        return {
            "hours": hours,
            "tenant_id": tenant_id,
            "activity": activity,
            "activity_count": len(activity)
        }
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/rbac/audit/user/{user_id}",
        summary="Get user audit trail",
        response_model=dict)
async def get_user_audit_trail(
    user_id: str = Path(..., description="User ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant"),
    current_user: SessionInfo = Depends(require_permission("audit:read"))
):
    """Get audit trail for a specific user"""
    try:
        audit_trail = auth_utils.get_audit_trail(user_id, tenant_id, limit)
        
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "limit": limit,
            "audit_trail": audit_trail,
            "record_count": len(audit_trail)
        }
        
    except Exception as e:
        logger.error(f"Error getting user audit trail: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# =====================================
# SYSTEM ADMINISTRATION ENDPOINTS
# =====================================

@app.get("/api/rbac/system/stats",
        summary="Get system statistics",
        response_model=dict)
async def get_system_statistics(
    current_user: SessionInfo = Depends(require_permission("system:read"))
):
    """Get comprehensive system statistics"""
    try:
        stats = auth_utils.get_system_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/rbac/system/cleanup",
         summary="Clean up expired tokens and sessions",
         response_model=dict)
async def cleanup_system(
    current_user: SessionInfo = Depends(require_superadmin())
):
    """Clean up expired tokens, sessions, and invitations"""
    try:
        results = auth_utils.cleanup_expired_tokens()
        
        return {
            "cleanup_results": results,
            "performed_by": current_user.user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during system cleanup: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/rbac/system/health",
        summary="System health check",
        response_model=dict)
async def health_check():
    """Perform system health check"""
    try:
        health_status = auth_utils.health_check()
        
        # Return appropriate HTTP status based on health
        if health_status["status"] == "unhealthy":
            raise HTTPException(status_code=503, detail=health_status)
        elif health_status["status"] == "degraded":
            # Return 200 but with warning information
            pass
        
        return health_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Health check failed")

# =====================================
# INVITATION ACCEPTANCE ENDPOINT
# =====================================

@app.post("/api/rbac/invitations/accept/{token}",
         summary="Accept tenant invitation",
         response_model=dict)
async def accept_invitation(
    token: str = Path(..., description="Invitation token"),
    current_user: SessionInfo = Depends(get_current_user)
):
    """Accept a tenant invitation"""
    try:
        result = auth_utils.accept_invitation(token, current_user.user_id)
        
        if not result:
            raise HTTPException(status_code=400, detail="Invalid or expired invitation token")
        
        return {
            "tenant_id": result["tenant_id"],
            "role": result["role"],
            "permissions": result["permissions"],
            "accepted_by": current_user.user_id,
            "accepted_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting invitation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# =====================================
# ROOT ENDPOINTS
# =====================================

@app.get("/", summary="API Information")
async def root():
    """API information and status"""
    return {
        "name": "Multi-tenant RBAC API",
        "version": "1.0.0",
        "description": "Role-Based Access Control system for multi-tenant authentication",
        "status": "active",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/rbac/info", summary="RBAC API Information")
async def rbac_info():
    """RBAC API specific information"""
    return {
        "features": [
            "Permission checking",
            "Role management", 
            "Tenant administration",
            "User management",
            "Audit logging",
            "Bulk operations",
            "System monitoring"
        ],
        "authentication": "JWT Bearer token",
        "authorization": "Role-Based Access Control (RBAC)",
        "multi_tenant": True,
        "api_version": "v1"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)