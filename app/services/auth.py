"""
Multi-tenant Authentication System Utilities
Python implementation of all utility functions for MongoDB-based auth system
"""

from datetime import datetime, timedelta,timezone
from typing import List, Dict, Optional, Union, Any
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from bson import ObjectId
import re
import secrets
import logging

logger = logging.getLogger(__name__)


class AuthUtilities:
    """Complete utility class for multi-tenant authentication system"""
    
    def __init__(self, db_client: Database):
        self.db = db_client
        self.users = self.db.users
        self.tenants = self.db.tenants
        self.tenant_users = self.db.tenant_users
        self.tenant_invitations = self.db.tenant_invitations
        self.roles = self.db.roles
        self.permissions = self.db.permissions
        self.audit_logs = self.db.audit_logs
        self.sessions = self.db.sessions
        self.webhooks = self.db.webhooks
        self.integrations = self.db.integrations
        self.system_config = self.db.system_config

    # =====================================
    # USER PERMISSION FUNCTIONS
    # =====================================

    def get_user_effective_permissions(self, user_id: str, tenant_id: Optional[str] = None) -> List[str]:
        """Get all effective permissions for a user in a specific tenant or globally"""
        try:
            user = self.users.find_one({"kratos_id": user_id})
            if not user:
                return []
            
            # Superadmin gets all permissions
            if user.get("global_role") == "superadmin":
                all_permissions = self.permissions.find({}, {"name": 1})
                return [p["name"] for p in all_permissions]
            
            permissions = set()
            
            # Add global permissions
            global_permissions = user.get("global_permissions", [])
            permissions.update(global_permissions)
            
            # Add global role permissions
            if user.get("global_role"):
                global_role = self.roles.find_one({
                    "name": user["global_role"],
                    "tenant_id": None
                })
                if global_role and global_role.get("permissions"):
                    permissions.update(global_role["permissions"])
            
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
                    if tenant_user.get("role"):
                        tenant_role = self.roles.find_one({
                            "name": tenant_user["role"],
                            "$or": [
                                {"tenant_id": ObjectId(tenant_id)},
                                {"tenant_id": None}
                            ]
                        })
                        if tenant_role and tenant_role.get("permissions"):
                            permissions.update(tenant_role["permissions"])
            
            return list(permissions)
            
        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return []

    def user_has_permission(self, user_id: str, permission: str, tenant_id: Optional[str] = None) -> bool:
        """Check if user has a specific permission"""
        try:
            user = self.users.find_one({"kratos_id": user_id})
            if not user:
                return False
            
            if user.get("global_role") == "superadmin":
                return True
            
            user_permissions = self.get_user_effective_permissions(user_id, tenant_id)
            return permission in user_permissions
            
        except Exception as e:
            logger.error(f"Error checking user permission: {e}")
            return False

    # =====================================
    # TENANT MANAGEMENT FUNCTIONS
    # =====================================

    def get_user_tenants(self, user_id: str) -> List[Dict]:
        """Get all tenants a user belongs to"""
        try:
            tenant_users = list(self.tenant_users.find({
                "user_id": user_id,
                "status": "active"
            }))
            
            if not tenant_users:
                return []
            
            tenant_ids = [tu["tenant_id"] for tu in tenant_users]
            
            tenants = list(self.tenants.find({
                "_id": {"$in": tenant_ids},
                "status": {"$in": ["active", "trial"]}
            }))
            
            # Add user role info to each tenant
            for tenant in tenants:
                tenant_user = next((tu for tu in tenant_users if tu["tenant_id"] == tenant["_id"]), None)
                if tenant_user:
                    tenant["user_role"] = tenant_user["role"]
                    tenant["joined_at"] = tenant_user.get("joined_at")
                    tenant["last_accessed"] = tenant_user.get("last_accessed")
            
            return tenants
            
        except Exception as e:
            logger.error(f"Error getting user tenants: {e}")
            return []

    def get_tenant_users(self, tenant_id: str, role: Optional[str] = None) -> List[Dict]:
        """Get all users in a tenant, optionally filtered by role"""
        try:
            query = {"tenant_id": ObjectId(tenant_id), "status": "active"}
            if role:
                query["role"] = role
            
            tenant_users = list(self.tenant_users.find(query))
            if not tenant_users:
                return []
            
            user_ids = [tu["user_id"] for tu in tenant_users]
            users = list(self.users.find({"kratos_id": {"$in": user_ids}}))
            
            # Merge tenant user info with user info
            result = []
            for user in users:
                tenant_user = next((tu for tu in tenant_users if tu["user_id"] == user["kratos_id"]), None)
                if tenant_user:
                    result.append({
                        "user_id": user["kratos_id"],
                        "email": user["email"],
                        "name": user.get("name"),
                        "role": tenant_user["role"],
                        "status": tenant_user["status"],
                        "joined_at": tenant_user.get("joined_at"),
                        "last_accessed": tenant_user.get("last_accessed"),
                        "permissions": tenant_user.get("permissions", [])
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting tenant users: {e}")
            return []

    def is_tenant_admin(self, user_id: str, tenant_id: str) -> bool:
        """Check if user is admin/owner of a tenant"""
        try:
            tenant_user = self.tenant_users.find_one({
                "user_id": user_id,
                "tenant_id": ObjectId(tenant_id),
                "status": "active",
                "role": {"$in": ["owner", "admin"]}
            })
            return tenant_user is not None
            
        except Exception as e:
            logger.error(f"Error checking tenant admin: {e}")
            return False

    def add_user_to_tenant(self, user_id: str, tenant_id: str, role: str = "user", 
                          permissions: Optional[List[str]] = None, invited_by: Optional[str] = None) -> bool:
        """Add a user to a tenant with specified role and permissions"""
        try:
            # Check if user already exists in tenant
            existing = self.tenant_users.find_one({
                "user_id": user_id,
                "tenant_id": ObjectId(tenant_id)
            })
            
            if existing:
                # Update existing record
                self.tenant_users.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {
                            "role": role,
                            "status": "active",
                            "permissions": permissions or [],
                            "updated_at": datetime.utcnow().isoformat(),
                            "joined_at": datetime.utcnow().isoformat()
                        }
                    }
                )
            else:
                # Create new record
                tenant_user_doc = {
                    "tenant_id": ObjectId(tenant_id),
                    "user_id": user_id,
                    "role": role,
                    "status": "active",
                    "permissions": permissions or [],
                    "invited_by": invited_by,
                    "joined_at": datetime.utcnow().isoformat(),
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": None
                }
                self.tenant_users.insert_one(tenant_user_doc)
            
            # Log audit event
            self.log_audit_event("user_added_to_tenant", user_id, {
                "tenant_id": tenant_id,
                "role": role,
                "permissions": permissions
            }, tenant_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding user to tenant: {e}")
            return False

    def remove_user_from_tenant(self, user_id: str, tenant_id: str, removed_by: Optional[str] = None) -> bool:
        """Remove a user from a tenant"""
        try:
            result = self.tenant_users.update_one(
                {
                    "user_id": user_id,
                    "tenant_id": ObjectId(tenant_id)
                },
                {
                    "$set": {
                        "status": "inactive",
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            )
            
            if result.modified_count > 0:
                self.log_audit_event("user_removed_from_tenant", user_id, {
                    "tenant_id": tenant_id,
                    "removed_by": removed_by
                }, tenant_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removing user from tenant: {e}")
            return False

    # =====================================
    # ROLE MANAGEMENT FUNCTIONS
    # =====================================

    def get_role_permissions(self, role_name: str, tenant_id: Optional[str] = None) -> List[str]:
        """Get all permissions for a role, including inherited permissions"""
        try:
            query = {"name": role_name}
            if tenant_id:
                query["tenant_id"] = ObjectId(tenant_id)
            else:
                query["tenant_id"] = None
            
            role = self.roles.find_one(query)
            if not role:
                return []
            
            permissions = set(role.get("permissions", []))
            
            # Add inherited permissions
            if role.get("inherits_from"):
                for parent_role_id in role["inherits_from"]:
                    parent_role = self.roles.find_one({"_id": ObjectId(parent_role_id)})
                    if parent_role and parent_role.get("permissions"):
                        permissions.update(parent_role["permissions"])
            
            return list(permissions)
            
        except Exception as e:
            logger.error(f"Error getting role permissions: {e}")
            return []

    def get_users_with_role(self, role_name: str, tenant_id: Optional[str] = None) -> List[Dict]:
        """Get all users with a specific role"""
        try:
            if tenant_id:
                return self.get_tenant_users(tenant_id, role_name)
            else:
                users = list(self.users.find({"global_role": role_name}))
                return users
                
        except Exception as e:
            logger.error(f"Error getting users with role: {e}")
            return []

    def create_custom_role(self, name: str, display_name: str, description: str,
                          permissions: List[str], tenant_id: Optional[str] = None,
                          created_by: Optional[str] = None) -> Optional[str]:
        """Create a custom role"""
        try:
            role_doc = {
                "name": name,
                "display_name": display_name,
                "description": description,
                "type": "tenant_specific" if tenant_id else "custom",
                "tenant_id": ObjectId(tenant_id) if tenant_id else None,
                "permissions": permissions,
                "inherits_from": None,
                "is_system_role": False,
                "is_default": False,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": None,
                "created_by": created_by,
                "metadata": {}
            }
            
            result = self.roles.insert_one(role_doc)
            
            self.log_audit_event("role_created", created_by, {
                "role_name": name,
                "permissions": permissions
            }, tenant_id)
            
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating custom role: {e}")
            return None

    # =====================================
    # AUDIT AND LOGGING FUNCTIONS
    # =====================================

    def log_audit_event(self, event_type: str, user_id: Optional[str], details: Dict,
                       tenant_id: Optional[str] = None, severity: str = "info",
                       target_user_id: Optional[str] = None, admin_user_id: Optional[str] = None,
                       ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
        """Log an audit event"""
        try:
            audit_doc = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type,
                "tenant_id": ObjectId(tenant_id) if tenant_id else None,
                "user_id": user_id,
                "target_user_id": target_user_id,
                "admin_user_id": admin_user_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "details": details,
                "severity": severity,
                "session_id": None,
                "action": event_type,
                "resource": "system",
                "before_state": None,
                "after_state": details,
                "correlation_id": f"{event_type}_{int(datetime.utcnow().timestamp() * 1000)}"
            }
            
            self.audit_logs.insert_one(audit_doc)
            return True
            
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
            return False

    def get_recent_activity(self, tenant_id: Optional[str] = None, hours: int = 24) -> List[Dict]:
        """Get recent audit logs"""
        try:
            from_date = datetime.utcnow() - timedelta(hours=hours)
            
            query = {"timestamp": {"$gte": from_date.isoformat()}}
            if tenant_id:
                query["tenant_id"] = ObjectId(tenant_id)
            
            logs = list(self.audit_logs.find(query).sort("timestamp", -1))
            return logs
            
        except Exception as e:
            logger.error(f"Error getting recent activity: {e}")
            return []

    def get_audit_trail(self, user_id: Optional[str] = None, tenant_id: Optional[str] = None,
                       limit: int = 100) -> List[Dict]:
        """Get audit trail for a user or tenant"""
        try:
            query = {}
            
            if user_id:
                query["$or"] = [
                    {"user_id": user_id},
                    {"target_user_id": user_id}
                ]
            
            if tenant_id:
                query["tenant_id"] = ObjectId(tenant_id)
            
            logs = list(self.audit_logs.find(query).sort("timestamp", -1).limit(limit))
            return logs
            
        except Exception as e:
            logger.error(f"Error getting audit trail: {e}")
            return []

    # =====================================
    # SESSION MANAGEMENT FUNCTIONS
    # =====================================

    def create_user_session(self, user_id: str, tenant_id: Optional[str] = None,
                           ip_address: Optional[str] = None, user_agent: Optional[str] = None,
                           remember_me: bool = False) -> Optional[str]:
        """Create a new user session"""
        try:
            session_id = secrets.token_urlsafe(32)
            now = datetime.utcnow()
            
            # Set expiry based on remember me
            if remember_me:
                expires_at = now + timedelta(days=30)  # 30 days
            else:
                expires_at = now + timedelta(hours=8)  # 8 hours
            
            session_doc = {
                "session_id": session_id,
                "user_id": user_id,
                "tenant_id": ObjectId(tenant_id) if tenant_id else None,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "device_fingerprint": None,
                "created_at": now.isoformat(),
                "last_activity": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                "is_active": True,
                "remember_me": remember_me,
                "metadata": {}
            }
            
            self.sessions.insert_one(session_doc)
            
            # Update user last login
            self.users.update_one(
                {"kratos_id": user_id},
                {
                    "$set": {
                        "last_login": now.isoformat(),
                        "last_login_ip": ip_address,
                        "failed_login_attempts": 0
                    }
                }
            )
            
            # Log audit event
            self.log_audit_event("user_login", user_id, {
                "session_id": session_id,
                "ip_address": ip_address,
                "remember_me": remember_me
            }, tenant_id)
            
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating user session: {e}")
            return None

    def get_active_sessions(self, user_id: str) -> List[Dict]:
        """Get all active sessions for a user"""
        try:
            sessions = list(self.sessions.find({
                "user_id": user_id,
                "is_active": True,
                "expires_at": {"$gt": datetime.utcnow().isoformat()}
            }).sort("last_activity", -1))
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a specific session"""
        try:
            result = self.sessions.update_one(
                {"session_id": session_id},
                {"$set": {"is_active": False}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error invalidating session: {e}")
            return False

    def invalidate_all_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user"""
        try:
            result = self.sessions.update_many(
                {"user_id": user_id, "is_active": True},
                {"$set": {"is_active": False}}
            )
            
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Error invalidating user sessions: {e}")
            return 0

    # =====================================
    # INVITATION MANAGEMENT FUNCTIONS
    # =====================================

    def create_tenant_invitation(self, tenant_id: str, email: str, role: str,
                                invited_by: str, expiry_hours: int = 72,
                                permissions: Optional[List[str]] = None,
                                message: Optional[str] = None) -> Optional[Dict]:
        """Create a tenant invitation"""
        try:
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)
            
            invitation_doc = {
                "tenant_id": ObjectId(tenant_id),
                "email": email,
                "role": role,
                "permissions": permissions or [],
                "custom_role_id": None,
                "token": token,
                "invited_by": invited_by,
                "message": message,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at.isoformat(),
                "accepted_at": None,
                "rejected_at": None,
                "cancelled_at": None,
                "cancelled_by": None
            }
            
            result = self.tenant_invitations.insert_one(invitation_doc)
            
            # Log audit event
            self.log_audit_event("invitation_sent", invited_by, {
                "email": email,
                "role": role,
                "token": token
            }, tenant_id)
            
            return {
                "invitation_id": str(result.inserted_id),
                "token": token,
                "expires_at": expires_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error creating tenant invitation: {e}")
            return None

    def accept_invitation(self, token: str, user_id: str) -> Optional[Dict]:
        """Accept a tenant invitation"""
        try:
            invitation = self.tenant_invitations.find_one({
                "token": token,
                "status": "pending",
                "expires_at": {"$gt": datetime.utcnow().isoformat()}
            })
            
            if not invitation:
                return None
            
            # Update invitation status
            self.tenant_invitations.update_one(
                {"_id": invitation["_id"]},
                {
                    "$set": {
                        "status": "accepted",
                        "accepted_at": datetime.utcnow().isoformat()
                    }
                }
            )
            
            # Add user to tenant
            tenant_id = str(invitation["tenant_id"])
            self.add_user_to_tenant(
                user_id=user_id,
                tenant_id=tenant_id,
                role=invitation["role"],
                permissions=invitation.get("permissions", []),
                invited_by=invitation["invited_by"]
            )
            
            return {
                "tenant_id": tenant_id,
                "role": invitation["role"],
                "permissions": invitation.get("permissions", [])
            }
            
        except Exception as e:
            logger.error(f"Error accepting invitation: {e}")
            return None

    def get_pending_invitations(self, tenant_id: str) -> List[Dict]:
        """Get all pending invitations for a tenant"""
        try:
            invitations = list(self.tenant_invitations.find({
                "tenant_id": ObjectId(tenant_id),
                "status": "pending",
                "expires_at": {"$gt": datetime.utcnow().isoformat()}
            }).sort("created_at", -1))
            
            return invitations
            
        except Exception as e:
            logger.error(f"Error getting pending invitations: {e}")
            return []

    # =====================================
    # SYSTEM UTILITIES
    # =====================================

    def cleanup_expired_tokens(self) -> Dict[str, int]:
        """Clean up expired tokens and sessions"""
        try:
            now = datetime.utcnow().isoformat()
            results = {}
            
            # Clean expired invitations
            expired_invitations = self.tenant_invitations.delete_many({
                "expires_at": {"$lt": now},
                "status": "pending"
            })
            results["expired_invitations"] = expired_invitations.deleted_count
            
            # Clean expired sessions
            expired_sessions = self.sessions.delete_many({
                "expires_at": {"$lt": now}
            })
            results["expired_sessions"] = expired_sessions.deleted_count
            
            # Clean old password reset tokens
            expired_reset_tokens = self.users.update_many(
                {"password_reset_expires": {"$lt": now}},
                {"$unset": {"password_reset_token": "", "password_reset_expires": ""}}
            )
            results["expired_reset_tokens"] = expired_reset_tokens.modified_count
            
            return results
            
        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}")
            return {}

    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        try:
            now = datetime.utcnow()
            last_24h = (now - timedelta(hours=24)).isoformat()
            
            stats = {
                "users": {
                    "total": self.users.count_documents({}),
                    "active": self.users.count_documents({"status": "active"}),
                    "verified": self.users.count_documents({"is_verified": True}),
                    "superadmins": self.users.count_documents({"global_role": "superadmin"})
                },
                "tenants": {
                    "total": self.tenants.count_documents({}),
                    "active": self.tenants.count_documents({"status": "active"}),
                    "trial": self.tenants.count_documents({"status": "trial"}),
                    "suspended": self.tenants.count_documents({"status": "suspended"})
                },
                "roles": {
                    "total": self.roles.count_documents({}),
                    "system": self.roles.count_documents({"is_system_role": True}),
                    "custom": self.roles.count_documents({"is_system_role": False})
                },
                "permissions": {
                    "total": self.permissions.count_documents({}),
                    "system": self.permissions.count_documents({"is_system_permission": True})
                },
                "audit_logs": {
                    "total": self.audit_logs.count_documents({}),
                    "last_24h": self.audit_logs.count_documents({
                        "timestamp": {"$gte": last_24h}
                    })
                },
                "sessions": {
                    "total": self.sessions.count_documents({}),
                    "active": self.sessions.count_documents({"is_active": True})
                },
                "invitations": {
                    "pending": self.tenant_invitations.count_documents({"status": "pending"}),
                    "total": self.tenant_invitations.count_documents({})
                },
                "generated_at": now.isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}

    # =====================================
    # VALIDATION FUNCTIONS
    # =====================================

    def validate_tenant_subdomain(self, subdomain: str) -> Dict[str, Union[bool, str]]:
        """Validate tenant subdomain format and availability"""
        try:
            # Check format
            pattern = r'^[a-z0-9][a-z0-9-]*[a-z0-9]$'
            if not re.match(pattern, subdomain):
                return {"valid": False, "reason": "Invalid format"}
            
            # Check length
            if len(subdomain) < 3 or len(subdomain) > 63:
                return {"valid": False, "reason": "Invalid length (3-63 characters)"}
            
            # Check availability
            existing = self.tenants.find_one({"subdomain": subdomain})
            if existing:
                return {"valid": False, "reason": "Subdomain already taken"}
            
            # Check reserved words
            reserved = ["api", "www", "admin", "app", "mail", "ftp", "blog", "shop", "support"]
            if subdomain in reserved:
                return {"valid": False, "reason": "Reserved subdomain"}
            
            return {"valid": True}
            
        except Exception as e:
            logger.error(f"Error validating subdomain: {e}")
            return {"valid": False, "reason": "Validation error"}

    def validate_permission_format(self, permission: str) -> Dict[str, Union[bool, str]]:
        """Validate permission string format"""
        try:
            # Check basic format: resource:action or resource:action:scope
            pattern = r'^[a-z_]+:[a-z_]+(?::[a-z_]+)?$'
            if not re.match(pattern, permission):
                return {"valid": False, "reason": "Invalid format. Use 'resource:action' or 'resource:action:scope'"}
            
            parts = permission.split(":")
            
            # Validate resource part
            if len(parts[0]) < 2:
                return {"valid": False, "reason": "Resource name too short"}
            
            # Validate action part
            if len(parts[1]) < 2:
                return {"valid": False, "reason": "Action name too short"}
            
            # Check if permission already exists
            existing = self.permissions.find_one({"name": permission})
            if existing:
                return {"valid": False, "reason": "Permission already exists"}
            
            return {"valid": True}
            
        except Exception as e:
            logger.error(f"Error validating permission: {e}")
            return {"valid": False, "reason": "Validation error"}

    # =====================================
    # BULK OPERATIONS
    # =====================================

    def bulk_assign_role(self, user_ids: List[str], role: str, tenant_id: Optional[str] = None,
                        assigned_by: Optional[str] = None) -> Dict[str, Union[int, List[str]]]:
        """Bulk assign role to multiple users"""
        try:
            results = {"success": 0, "failed": 0, "errors": []}
            
            for user_id in user_ids:
                try:
                    if tenant_id:
                        # Tenant role assignment
                        result = self.tenant_users.update_one(
                            {"user_id": user_id, "tenant_id": ObjectId(tenant_id)},
                            {
                                "$set": {
                                    "role": role,
                                    "updated_at": datetime.utcnow().isoformat()
                                }
                            }
                        )
                        
                        if result.modified_count > 0:
                            results["success"] += 1
                            self.log_audit_event("role_assigned", user_id, {"role": role}, tenant_id)
                        else:
                            results["failed"] += 1
                            results["errors"].append(f"User {user_id} not found in tenant")
                    else:
                        # Global role assignment
                        result = self.users.update_one(
                            {"kratos_id": user_id},
                            {
                                "$set": {
                                    "global_role": role,
                                    "updated_at": datetime.utcnow().isoformat()
                                }
                            }
                        )
                        
                        if result.modified_count > 0:
                            results["success"] += 1
                            self.log_audit_event("global_role_assigned", user_id, {"role": role})
                        else:
                            results["failed"] += 1
                            results["errors"].append(f"User {user_id} not found")
                            
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"Error for user {user_id}: {str(e)}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in bulk role assignment: {e}")
            return {"success": 0, "failed": len(user_ids), "errors": [str(e)]}

    def bulk_remove_users_from_tenant(self, user_ids: List[str], tenant_id: str,
                                     removed_by: Optional[str] = None) -> Dict[str, Union[int, List[str]]]:
        """Bulk remove users from a tenant"""
        try:
            results = {"success": 0, "failed": 0, "errors": []}
            
            for user_id in user_ids:
                try:
                    if self.remove_user_from_tenant(user_id, tenant_id, removed_by):
                        results["success"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Failed to remove user {user_id}")
                        
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"Error removing user {user_id}: {str(e)}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in bulk user removal: {e}")
            return {"success": 0, "failed": len(user_ids), "errors": [str(e)]}

    # =====================================
    # TENANT MANAGEMENT OPERATIONS
    # =====================================

    def create_tenant(self, name: str, subdomain: str, created_by: Optional[str] = None,
                     subscription_plan: str = "trial", settings: Optional[Dict] = None) -> Optional[str]:
        """Create a new tenant"""
        try:
            # Validate subdomain
            validation = self.validate_tenant_subdomain(subdomain)
            if not validation["valid"]:
                logger.error(f"Invalid subdomain: {validation['reason']}")
                return None
            
            # Get trial configuration
            trial_config = self.system_config.find_one({"key": "trial_duration_days"})
            trial_days = trial_config.get("value", 14) if trial_config else 14
            
            now = datetime.utcnow()
            tenant_doc = {
                "name": name,
                "subdomain": subdomain,
                "domain": None,
                "status": "trial" if subscription_plan == "trial" else "active",
                "subscription_plan": subscription_plan,
                "settings": settings or self._get_default_tenant_settings(),
                "billing_info": {},
                "created_at": now.isoformat(),
                "updated_at": None,
                "created_by": created_by,
                "trial_starts_at": now.isoformat() if subscription_plan == "trial" else None,
                "trial_ends_at": (now + timedelta(days=trial_days)).isoformat() if subscription_plan == "trial" else None,
                "suspended_at": None,
                "suspended_by": None,
                "suspension_reason": None,
                "last_activity": now.isoformat(),
                "metadata": {}
            }
            
            result = self.tenants.insert_one(tenant_doc)
            tenant_id = str(result.inserted_id)
            
            # Add creator as owner if specified
            if created_by:
                self.add_user_to_tenant(created_by, tenant_id, "owner")
            
            # Log audit event
            self.log_audit_event("tenant_created", created_by, {
                "tenant_name": name,
                "subdomain": subdomain,
                "subscription_plan": subscription_plan
            })
            
            return tenant_id
            
        except Exception as e:
            logger.error(f"Error creating tenant: {e}")
            return None

    def update_tenant_settings(self, tenant_id: str, settings: Dict, updated_by: Optional[str] = None) -> bool:
        """Update tenant settings"""
        try:
            result = self.tenants.update_one(
                {"_id": ObjectId(tenant_id)},
                {
                    "$set": {
                        "settings": settings,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            )
            
            if result.modified_count > 0:
                self.log_audit_event("tenant_settings_updated", updated_by, {
                    "tenant_id": tenant_id,
                    "settings": settings
                }, tenant_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating tenant settings: {e}")
            return False

    def suspend_tenant(self, tenant_id: str, reason: str, suspended_by: str) -> bool:
        """Suspend a tenant"""
        try:
            now = datetime.utcnow()
            result = self.tenants.update_one(
                {"_id": ObjectId(tenant_id)},
                {
                    "$set": {
                        "status": "suspended",
                        "suspended_at": now.isoformat(),
                        "suspended_by": suspended_by,
                        "suspension_reason": reason,
                        "updated_at": now.isoformat()
                    }
                }
            )
            
            if result.modified_count > 0:
                # Invalidate all sessions for this tenant
                self.sessions.update_many(
                    {"tenant_id": ObjectId(tenant_id)},
                    {"$set": {"is_active": False}}
                )
                
                self.log_audit_event("tenant_suspended", suspended_by, {
                    "tenant_id": tenant_id,
                    "reason": reason
                }, tenant_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error suspending tenant: {e}")
            return False

    def reactivate_tenant(self, tenant_id: str, reactivated_by: str) -> bool:
        """Reactivate a suspended tenant"""
        try:
            result = self.tenants.update_one(
                {"_id": ObjectId(tenant_id)},
                {
                    "$set": {
                        "status": "active",
                        "updated_at": datetime.utcnow().isoformat()
                    },
                    "$unset": {
                        "suspended_at": "",
                        "suspended_by": "",
                        "suspension_reason": ""
                    }
                }
            )
            
            if result.modified_count > 0:
                self.log_audit_event("tenant_reactivated", reactivated_by, {
                    "tenant_id": tenant_id
                }, tenant_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error reactivating tenant: {e}")
            return False

    # =====================================
    # USER MANAGEMENT OPERATIONS
    # =====================================

    def lock_user_account(self, user_id: str, reason: str, locked_by: str) -> bool:
        """Lock a user account"""
        try:
            now = datetime.utcnow()
            result = self.users.update_one(
                {"kratos_id": user_id},
                {
                    "$set": {
                        "account_locked": True,
                        "status": "locked",
                        "locked_at": now.isoformat(),
                        "locked_by": locked_by,
                        "lock_reason": reason,
                        "updated_at": now.isoformat()
                    }
                }
            )
            
            if result.modified_count > 0:
                # Invalidate all user sessions
                self.invalidate_all_user_sessions(user_id)
                
                self.log_audit_event("user_account_locked", locked_by, {
                    "target_user_id": user_id,
                    "reason": reason
                }, admin_user_id=locked_by, target_user_id=user_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error locking user account: {e}")
            return False

    def unlock_user_account(self, user_id: str, unlocked_by: str) -> bool:
        """Unlock a user account"""
        try:
            result = self.users.update_one(
                {"kratos_id": user_id},
                {
                    "$set": {
                        "account_locked": False,
                        "status": "active",
                        "failed_login_attempts": 0,
                        "updated_at": datetime.utcnow().isoformat()
                    },
                    "$unset": {
                        "locked_at": "",
                        "locked_by": "",
                        "lock_reason": ""
                    }
                }
            )
            
            if result.modified_count > 0:
                self.log_audit_event("user_account_unlocked", unlocked_by, {
                    "target_user_id": user_id
                }, admin_user_id=unlocked_by, target_user_id=user_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error unlocking user account: {e}")
            return False

    def update_user_global_role(self, user_id: str, new_role: str, updated_by: str) -> bool:
        """Update a user's global role"""
        try:
            # Get current user data for audit trail
            current_user = self.users.find_one({"kratos_id": user_id})
            if not current_user:
                return False
            
            old_role = current_user.get("global_role")
            
            result = self.users.update_one(
                {"kratos_id": user_id},
                {
                    "$set": {
                        "global_role": new_role,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            )
            
            if result.modified_count > 0:
                self.log_audit_event("global_role_changed", updated_by, {
                    "target_user_id": user_id,
                    "old_role": old_role,
                    "new_role": new_role
                }, admin_user_id=updated_by, target_user_id=user_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating user global role: {e}")
            return False

    # =====================================
    # WEBHOOK MANAGEMENT
    # =====================================

    def create_webhook(self, tenant_id: str, name: str, url: str, events: List[str],
                      secret: Optional[str] = None, created_by: Optional[str] = None) -> Optional[str]:
        """Create a new webhook"""
        try:
            if not secret:
                secret = secrets.token_urlsafe(32)
            
            webhook_doc = {
                "tenant_id": ObjectId(tenant_id),
                "name": name,
                "url": url,
                "secret": secret,
                "events": events,
                "status": "active",
                "last_triggered": None,
                "failure_count": 0,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": None,
                "created_by": created_by
            }
            
            result = self.webhooks.insert_one(webhook_doc)
            
            self.log_audit_event("webhook_created", created_by, {
                "webhook_name": name,
                "url": url,
                "events": events
            }, tenant_id)
            
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating webhook: {e}")
            return None

    def get_tenant_webhooks(self, tenant_id: str, status: Optional[str] = None) -> List[Dict]:
        """Get webhooks for a tenant"""
        try:
            query = {"tenant_id": ObjectId(tenant_id)}
            if status:
                query["status"] = status
            
            webhooks = list(self.webhooks.find(query).sort("created_at", -1))
            return webhooks
            
        except Exception as e:
            logger.error(f"Error getting tenant webhooks: {e}")
            return []

    # =====================================
    # INTEGRATION MANAGEMENT
    # =====================================

    def create_integration(self, tenant_id: str, integration_type: str, name: str,
                          config: Dict, credentials: Dict, created_by: Optional[str] = None) -> Optional[str]:
        """Create a new integration"""
        try:
            integration_doc = {
                "tenant_id": ObjectId(tenant_id),
                "type": integration_type,
                "name": name,
                "description": None,
                "config": config,
                "credentials": credentials,  # Should be encrypted in production
                "status": "setup",
                "last_sync": None,
                "error_message": None,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": None,
                "created_by": created_by
            }
            
            result = self.integrations.insert_one(integration_doc)
            
            self.log_audit_event("integration_created", created_by, {
                "integration_name": name,
                "type": integration_type
            }, tenant_id)
            
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating integration: {e}")
            return None

    def get_tenant_integrations(self, tenant_id: str, integration_type: Optional[str] = None) -> List[Dict]:
        """Get integrations for a tenant"""
        try:
            query = {"tenant_id": ObjectId(tenant_id)}
            if integration_type:
                query["type"] = integration_type
            
            integrations = list(self.integrations.find(query).sort("created_at", -1))
            
            # Remove sensitive credentials from response
            for integration in integrations:
                if "credentials" in integration:
                    integration["credentials"] = {"configured": bool(integration["credentials"])}
            
            return integrations
            
        except Exception as e:
            logger.error(f"Error getting tenant integrations: {e}")
            return []

    # =====================================
    # SYSTEM CONFIGURATION
    # =====================================

    def get_system_config(self, key: str) -> Optional[Any]:
        """Get a system configuration value"""
        try:
            config = self.system_config.find_one({"key": key})
            return config.get("value") if config else None
            
        except Exception as e:
            logger.error(f"Error getting system config: {e}")
            return None

    def set_system_config(self, key: str, value: Any, description: str = "",
                         category: str = "general", is_sensitive: bool = False,
                         updated_by: Optional[str] = None) -> bool:
        """Set a system configuration value"""
        try:
            result = self.system_config.update_one(
                {"key": key},
                {
                    "$set": {
                        "value": value,
                        "description": description,
                        "category": category,
                        "is_sensitive": is_sensitive,
                        "updated_at": datetime.utcnow().isoformat(),
                        "updated_by": updated_by
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )
            
            self.log_audit_event("system_config_updated", updated_by, {
                "key": key,
                "category": category,
                "is_sensitive": is_sensitive
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting system config: {e}")
            return False

    # =====================================
    # HELPER METHODS
    # =====================================

    def _get_default_tenant_settings(self) -> Dict:
        """Get default settings for new tenants"""
        return {
            "branding": {
                "logo_url": None,
                "favicon_url": None,
                "primary_color": "#007bff",
                "secondary_color": "#6c757d",
                "accent_color": "#28a745",
                "custom_css": None,
                "company_name": None
            },
            "features": {
                "sso_enabled": False,
                "mfa_required": False,
                "api_access": True,
                "audit_logs": True,
                "custom_roles": False,
                "white_label": False,
                "advanced_analytics": False,
                "webhook_support": True,
                "integrations": []
            },
            "limits": {
                "max_users": 10,
                "max_admins": 3,
                "storage_gb": 1,
                "api_calls_per_month": 10000,
                "max_integrations": 3,
                "max_webhooks": 5
            },
            "security": {
                "password_policy": {},
                "session_timeout": 480,  # 8 hours in minutes
                "ip_whitelist": None,
                "allowed_domains": None,
                "require_mfa": False,
                "login_attempts_limit": 5
            },
            "notifications": {
                "email_notifications": True,
                "slack_webhook": None,
                "teams_webhook": None
            }
        }

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on all database connections and collections"""
        try:
            health_status = {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "collections": {},
                "indexes": {},
                "errors": []
            }
            
            # Check each collection
            collections_to_check = [
                "users", "tenants", "tenant_users", "tenant_invitations",
                "roles", "permissions", "audit_logs", "sessions",
                "webhooks", "integrations", "system_config"
            ]
            
            for collection_name in collections_to_check:
                try:
                    collection = getattr(self, collection_name)
                    count = collection.count_documents({})
                    health_status["collections"][collection_name] = {
                        "status": "ok",
                        "document_count": count
                    }
                except Exception as e:
                    health_status["collections"][collection_name] = {
                        "status": "error",
                        "error": str(e)
                    }
                    health_status["errors"].append(f"Collection {collection_name}: {e}")
            
            # Check critical indexes
            try:
                user_indexes = list(self.users.list_indexes())
                health_status["indexes"]["users"] = len(user_indexes)
            except Exception as e:
                health_status["errors"].append(f"Index check failed: {e}")
            
            if health_status["errors"]:
                health_status["status"] = "degraded"
            
            return health_status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }


# =====================================
# EXAMPLE USAGE AND TESTING
# =====================================

def example_usage():
    """Example of how to use the AuthUtilities class"""
    
    # Initialize MongoDB client
    client = MongoClient("mongodb://localhost:27017/")
    auth_utils = AuthUtilities(client)
    
    # Example: Check user permissions
    permissions = auth_utils.get_user_effective_permissions("user123", "tenant456")
    has_permission = auth_utils.user_has_permission("user123", "users:read", "tenant456")
    
    # Example: Create tenant invitation
    invitation = auth_utils.create_tenant_invitation(
        tenant_id="tenant456",
        email="newuser@example.com",
        role="user",
        invited_by="admin123"
    )
    
    # Example: Get system statistics
    stats = auth_utils.get_system_stats()
    print(f"Total users: {stats.get('users', {}).get('total', 0)}")
    
    # Example: Cleanup expired tokens
    cleanup_results = auth_utils.cleanup_expired_tokens()
    print(f"Cleaned up {cleanup_results.get('expired_sessions', 0)} expired sessions")

def seed_initial_data(auth_utils: AuthUtilities):
    """Seed initial data for testing"""
    try:
        # Create some initial roles and permissions
        logger.info("Seeding initial data...")
        
        # You could add initial tenants, roles, etc. here
        # This is just an example structure
        
        # Create a sample tenant if none exists
        if auth_utils.tenants.count_documents({}) == 0:
            tenant_doc = {
                "name": "Nexidra Technologies LLC",
                "status": "active",
                "created_at": datetime.now(timezone.utc)
            }
            result = auth_utils.tenants.insert_one(tenant_doc)
            logger.info(f"Created default tenant: {result.inserted_id}")
        
        logger.info("Initial data seeding completed")
        
    except Exception as e:
        logger.error(f"Error seeding initial data: {e}")
if __name__ == "__main__":
    # Run example usage
    example_usage()