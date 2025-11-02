"""
RBAC (Role-Based Access Control) FastAPI Endpoint
Complete implementation for multi-tenant authentication system
"""


from pydantic import BaseModel, EmailStr, Field
from typing import List, Dict, Optional, Any, Union
from pymongo import MongoClient
from datetime import datetime
import logging
import os
from enum import Enum

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