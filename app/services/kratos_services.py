# kratos_service.py - Ory Kratos Identity Management Service

import os
import requests
import logging
from typing import Dict, Any, Optional,List
from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from pymongo.database import Database
from dataclasses import dataclass
from utils.db import get_database
from metrics.metrics import get_metrics
from services.audit import AuditService

logger = logging.getLogger(__name__)

@dataclass
class KratosIdentity:
    id: str
    email: str
    state: str
    created_at: str
    updated_at: str
    metadata_admin: Optional[Dict[str, Any]] = None
    metadata_public: Optional[Dict[str, Any]] = None
    traits: Optional[Dict[str, Any]] = None

@dataclass
class KratosFlow:
    id: str
    type: str
    expires_at: str
    issued_at: str
    request_url: str
    ui: Dict[str, Any]
    state: Optional[str] = None

@dataclass
class KratosSession:
    id: str
    identity_id: str
    active: bool
    expires_at: str
    issued_at: str
    authenticated_at: str
    
    @classmethod
    def from_json(cls, data: dict) -> "KratosSession":
        """
        Parse a session object from Kratos JSON response
        """
        return cls(
            id=data["id"],
            identity_id=data["identity"]["id"],
            active=data.get("active", False),
            expires_at=data["expires_at"],
            issued_at=data["issued_at"],
            authenticated_at=data.get("authenticated_at"),
        )

class KratosService:
    """Service for interacting with Ory Kratos identity management"""
    
    def __init__(self, db: Database, metrics_collector):
        self.db = db
        self.metrics = metrics_collector
        self.audit_logs = db.audit_logs
        
        # Kratos configuration
        self.admin_url = os.getenv("KRATOS_ADMIN_URL", "http://127.0.0.1:8717")
        self.public_url = os.getenv("KRATOS_PUBLIC_URL", "http://127.0.0.1:4433")
        self.webhook_secret = os.getenv("KRATOS_WEBHOOK_SECRET", "")
        
        # Headers for Kratos API calls
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.webhook_secret:
            self.headers["Authorization"] = f"Bearer {self.webhook_secret}"
    
    # =====================================
    # IDENTITY MANAGEMENT
    # =====================================
    async def create_user_flow(self,email: str, password: str, traits: Optional[Dict[str, Any]] = None,client_ip=None):
        flow_response = requests.get(f"{self.public_url}/self-service/registration/api")
        if flow_response.status_code >= 400:
            raise HTTPException(status_code=500, detail="Authentication service unavailable")
        
        flow = flow_response.json()
        flow_id = flow["id"]
        payload = {
            "method": "password",
            "password": password,
            "traits": {
                "email": email,
                **(traits or {})
            },
        }
        try:
            kratos_response = requests.post(f"{self.public_url}/self-service/registration?flow={flow_id}",
            json=payload)
            
            if kratos_response.status_code >= 400:
                   
                error_details = kratos_response.json()
            
                
                await  AuditService.log_event(
                    "registration_failed_kratos",
                    ip_address=client_ip,
                    details={"error": error_details, "email": email},
                    severity="error"
                )
                raise HTTPException(status_code=kratos_response.status_code, detail=error_details)
            
            identity_json = kratos_response.json()
            session = KratosSession.from_json(identity_json['session'])
            
            
            if "identity" in identity_json:
                identity = identity_json["identity"]
            else:
                # Admin API response is already the identity
                identity = identity_json
                
            if "verifiable_addresses" in identity and identity["verifiable_addresses"]:
                verifiable_addresses=identity["verifiable_addresses"]
            
            return KratosIdentity(
                id=identity["id"],
                email=identity["traits"].get("email"),
                state=identity.get("state", "active"),
                created_at=identity["created_at"],
                updated_at=identity["updated_at"],
                metadata_admin=identity.get("metadata_admin",{}),
                metadata_public=identity.get("metadata_public",{}),
                traits=identity.get("traits",{})
            ),session,verifiable_addresses
            
            
        except Exception as e:
            # print(e)
            raise
        
    
    async def create_identity(
        self, 
        email: str, 
        password: str,
        traits: Optional[Dict[str, Any]] = None,
        metadata_admin: Optional[Dict[str, Any]] = None,
        metadata_public: Optional[Dict[str, Any]] = None,
        schema_id: str = "default"
    ) -> KratosIdentity:
        """Create a new identity in Kratos"""
        try:
            identity_data = {
                "schema_id": schema_id,
                "traits": {
                    "email": email,
                    **(traits or {})
                },
                "credentials": {
                    "password": {
                        "config": {
                            "password": password
                        }
                    }
                }
            }
            
            if metadata_admin:
                identity_data["metadata_admin"] = metadata_admin
            if metadata_public:
                identity_data["metadata_public"] = metadata_public
            
            response = requests.post(
                f"{self.admin_url}/admin/identities",
                json=identity_data,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            identity_json = response.json()
            
            # Log creation
            await self._log_audit_event(
                "kratos_identity_created",
                identity_json["id"],
                None,
                {"email": email, "schema_id": schema_id}
            )
            
            logger.info(f"Created Kratos identity: {identity_json['id']} for {email}")
            
            return KratosIdentity(
                id=identity_json["id"],
                email=email,
                state=identity_json.get("state", "active"),
                created_at=identity_json["created_at"],
                updated_at=identity_json["updated_at"],
                metadata_admin=identity_json.get("metadata_admin"),
                metadata_public=identity_json.get("metadata_public"),
                traits=identity_json.get("traits")
            )
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error creating identity for {email}: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            raise HTTPException(status_code=500, detail="Identity creation failed")
        except Exception as e:
            logger.error(f"Unexpected error creating identity for {email}: {str(e)}")
            raise HTTPException(status_code=500, detail="Identity creation failed")
    
    async def get_identity(self, identity_id: str) -> Optional[KratosIdentity]:
        """Get identity by ID"""
        try:
            response = requests.get(
                f"{self.admin_url}/admin/identities/{identity_id}",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 404:
                return None
                
            response.raise_for_status()
            identity_json = response.json()
            
            return KratosIdentity(
                id=identity_json["id"],
                email=identity_json["traits"]["email"],
                state=identity_json.get("state", "active"),
                created_at=identity_json["created_at"],
                updated_at=identity_json["updated_at"],
                metadata_admin=identity_json.get("metadata_admin"),
                metadata_public=identity_json.get("metadata_public"),
                traits=identity_json.get("traits")
            )
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error getting identity {identity_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting identity {identity_id}: {str(e)}")
            return None
    
    async def get_identity_by_email(self, email: str) -> Optional[KratosIdentity]:
        """Get identity by email address"""
        try:
            # Search for identity by email
            response = requests.get(
                f"{self.admin_url}/admin/identities",
                params={"credentials_identifier": email},
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            identities = response.json()
            if not identities:
                return None
            
            # Return first matching identity
            identity_json = identities[0]
            return KratosIdentity(
                id=identity_json["id"],
                email=email,
                state=identity_json.get("state", "active"),
                created_at=identity_json["created_at"],
                updated_at=identity_json["updated_at"],
                metadata_admin=identity_json.get("metadata_admin"),
                metadata_public=identity_json.get("metadata_public"),
                traits=identity_json.get("traits")
            )
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error searching identity by email {email}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error searching identity by email {email}: {str(e)}")
            return None
    
    async def update_identity(
        self, 
        identity_id: str,
        traits: Optional[Dict[str, Any]] = None,
        metadata_admin: Optional[Dict[str, Any]] = None,
        metadata_public: Optional[Dict[str, Any]] = None,
        state: Optional[str] = None,
        schema_id: str = "default"
    ) -> Optional[KratosIdentity]:
        """Update an existing identity"""
        try:
            # Get current identity
            current = await self.get_identity(identity_id)
            if not current:
                return None
            
            update_data = {
                "schema_id": schema_id,
                "traits": {
                    **(current.traits or {}),
                    **(traits or {})
                }
            }
            
            if metadata_admin is not None:
                update_data["metadata_admin"] = metadata_admin
            if metadata_public is not None:
                update_data["metadata_public"] = metadata_public
            if state is not None:
                update_data["state"] = state
            
            response = requests.put(
                f"{self.admin_url}/admin/identities/{identity_id}",
                json=update_data,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            identity_json = response.json()
            
            # Log update
            await self._log_audit_event(
                "kratos_identity_updated",
                identity_id,
                None,
                {"updates": update_data}
            )
            
            logger.info(f"Updated Kratos identity: {identity_id}")
            
            return KratosIdentity(
                id=identity_json["id"],
                email=identity_json["traits"]["email"],
                state=identity_json.get("state", "active"),
                created_at=identity_json["created_at"],
                updated_at=identity_json["updated_at"],
                metadata_admin=identity_json.get("metadata_admin"),
                metadata_public=identity_json.get("metadata_public"),
                traits=identity_json.get("traits")
            )
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error updating identity {identity_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error updating identity {identity_id}: {str(e)}")
            return None
    
    async def delete_identity(self, identity_id: str) -> bool:
        """Delete an identity"""
        try:
            response = requests.delete(
                f"{self.admin_url}/admin/identities/{identity_id}",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 404:
                print("not found")
                return False
                
            response.raise_for_status()
            
            # Log deletion
            await self._log_audit_event(
                "kratos_identity_deleted",
                identity_id,
                None,
                {"deleted": True}
            )
            
            logger.info(f"Deleted Kratos identity: {identity_id}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error deleting identity {identity_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting identity {identity_id}: {str(e)}")
            return False
    
    # =====================================
    # SESSION MANAGEMENT
    # =====================================
    
    async def get_identity_sessions(self, identity_id: str) -> List[KratosSession]:
        """Get all sessions for an identity"""
        try:
            response = requests.get(
                f"{self.admin_url}/admin/identities/{identity_id}/sessions",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            sessions_data = response.json()
            sessions = []
            
            for session_data in sessions_data:
                sessions.append(KratosSession(
                    id=session_data["id"],
                    identity_id=identity_id,
                    active=session_data.get("active", False),
                    expires_at=session_data.get("expires_at", ""),
                    issued_at=session_data.get("issued_at", ""),
                    authenticated_at=session_data.get("authenticated_at", "")
                ))
            
            return sessions
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error getting sessions for identity {identity_id}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting sessions for identity {identity_id}: {str(e)}")
            return []
    
    async def invalidate_sessions(self, identity_id: str) -> bool:
        """Invalidate all sessions for an identity"""
        try:
            response = requests.delete(
                f"{self.admin_url}/admin/identities/{identity_id}/sessions",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            # Log session invalidation
            await self._log_audit_event(
                "kratos_sessions_invalidated",
                identity_id,
                None,
                {"action": "invalidate_all_sessions"}
            )
            
            logger.info(f"Invalidated sessions for identity: {identity_id}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error invalidating sessions for identity {identity_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error invalidating sessions for identity {identity_id}: {str(e)}")
            return False
    
    async def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a specific session"""
        try:
            response = requests.delete(
                f"{self.admin_url}/admin/sessions/{session_id}",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            logger.info(f"Invalidated session: {session_id}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error invalidating session {session_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error invalidating session {session_id}: {str(e)}")
            return False
    
    # =====================================
    # RECOVERY & VERIFICATION
    # =====================================
    
    async def create_recovery_link(self, identity_id: str, expires_in: str = "1h") -> Optional[str]:
        """Create a recovery link for an identity"""
        try:
            response = requests.post(
                f"{self.admin_url}/admin/recovery/link",
                json={
                    "identity_id": identity_id,
                    "expires_in": expires_in
                },
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            recovery_link = result.get("recovery_link")
            
            if recovery_link:
                # Log recovery link creation
                await self._log_audit_event(
                    "kratos_recovery_link_created",
                    identity_id,
                    None,
                    {"expires_in": expires_in}
                )
                
                logger.info(f"Created recovery link for identity: {identity_id}")
            
            return recovery_link
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error creating recovery link for identity {identity_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating recovery link for identity {identity_id}: {str(e)}")
            return None
    
    async def create_verification_link(self, identity_id: str, expires_in: str = "24h") -> Optional[str]:
        """Create a verification link for an identity"""
        try:
            response = requests.post(
                f"{self.admin_url}/admin/verification/link",
                json={
                    "identity_id": identity_id,
                    "expires_in": expires_in
                },
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            verification_link = result.get("verification_link")
            
            if verification_link:
                # Log verification link creation
                await self._log_audit_event(
                    "kratos_verification_link_created",
                    identity_id,
                    None,
                    {"expires_in": expires_in}
                )
                
                logger.info(f"Created verification link for identity: {identity_id}")
            
            return verification_link
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error creating verification link for identity {identity_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating verification link for identity {identity_id}: {str(e)}")
            return None
    
    # =====================================
    # FLOW MANAGEMENT
    # =====================================
    
    async def init_registration_flow(self, return_to: Optional[str] = None) -> Optional[KratosFlow]:
        """Initialize registration flow"""
        try:
            params = {}
            if return_to:
                params["return_to"] = return_to
            
            response = requests.get(
                f"{self.public_url}/self-service/registration/api",
                params=params,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            flow_json = response.json()
            
            return KratosFlow(
                id=flow_json["id"],
                type=flow_json["type"],
                expires_at=flow_json["expires_at"],
                issued_at=flow_json["issued_at"],
                request_url=flow_json["request_url"],
                ui=flow_json["ui"]
            )
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error initializing registration flow: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error initializing registration flow: {str(e)}")
            return None
    
    async def init_login_flow(self, return_to: Optional[str] = None) -> Optional[KratosFlow]:
        """Initialize login flow"""
        try:
            params = {}
            if return_to:
                params["return_to"] = return_to
            
            response = requests.get(
                f"{self.public_url}/self-service/login/api",
                params=params,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            flow_json = response.json()
            
            return KratosFlow(
                id=flow_json["id"],
                type=flow_json["type"],
                expires_at=flow_json["expires_at"],
                issued_at=flow_json["issued_at"],
                request_url=flow_json["request_url"],
                ui=flow_json["ui"]
            )
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error initializing login flow: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error initializing login flow: {str(e)}")
            return None
    
    async def init_recovery_flow(self, return_to: Optional[str] = None) -> Optional[KratosFlow]:
        """Initialize recovery flow"""
        try:
            params = {}
            if return_to:
                params["return_to"] = return_to
            
            response = requests.get(
                f"{self.public_url}/self-service/recovery/api",
                params=params,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            
            flow_json = response.json()
            
            return KratosFlow(
                id=flow_json["id"],
                type=flow_json["type"],
                expires_at=flow_json["expires_at"],
                issued_at=flow_json["issued_at"],
                request_url=flow_json["request_url"],
                ui=flow_json["ui"]
            )
            
        except requests.RequestException as e:
            logger.error(f"Kratos API error initializing recovery flow: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error initializing recovery flow: {str(e)}")
            return None
    
    # =====================================
    # HEALTH & MONITORING
    # =====================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Kratos service health"""
        try:
            # Check admin API
            admin_response = requests.get(
                f"{self.admin_url}/health/ready", 
                timeout=10
            )
            admin_healthy = admin_response.status_code == 200
            
            # Check public API  
            public_response = requests.get(
                f"{self.public_url}/health/ready", 
                timeout=10
            )
            public_healthy = public_response.status_code == 200
            
            return {
                "status": "healthy" if (admin_healthy and public_healthy) else "unhealthy",
                "admin_api": "healthy" if admin_healthy else "unhealthy",
                "public_api": "healthy" if public_healthy else "unhealthy",
                "admin_url": self.admin_url,
                "public_url": self.public_url,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "admin_url": self.admin_url,
                "public_url": self.public_url,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def get_version(self) -> Optional[Dict[str, Any]]:
        """Get Kratos version information"""
        try:
            response = requests.get(
                f"{self.admin_url}/version",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error getting Kratos version: {str(e)}")
            return None
    
    # =====================================
    # UTILITY METHODS
    # =====================================
    
    async def _log_audit_event(
        self,
        event_type: str,
        identity_id: Optional[str],
        tenant_id: Optional[str],
        details: Dict[str, Any]
    ):
        """Log audit event for Kratos operations"""
        if  self.audit_logs is None:
            return
            
        try:
            audit_doc = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "tenant_id": tenant_id,
                "user_id": identity_id,
                "target_user_id": None,
                "admin_user_id": None,
                "ip_address": None,
                "user_agent": None,
                "details": details,
                "severity": "info",
                "session_id": None,
                "action": event_type,
                "resource": "kratos",
                "before_state": None,
                "after_state": details,
                "correlation_id": f"kratos_{event_type}_{datetime.now().timestamp()}"
            }
            
            self.audit_logs.insert_one(audit_doc)
            
        except Exception as e:
            logger.error(f"Failed to log Kratos audit event: {str(e)}")

# =====================================
# DEPENDENCY INJECTION
# =====================================

def get_kratos_service(
    db: Database = Depends(get_database),
    metrics = Depends(get_metrics)
) -> KratosService:
    """Dependency to get Kratos service"""
    return KratosService(db, metrics)

# =====================================
# SETUP FUNCTIONS
# =====================================

def setup_kratos_service():
    """Setup function to verify Kratos connection"""
    try:
        admin_url = os.getenv("KRATOS_ADMIN_URL", "http://127.0.0.1:4434")
        public_url = os.getenv("KRATOS_PUBLIC_URL", "http://127.0.0.1:4433")
        
        # Test admin API
        admin_response = requests.get(f"{admin_url}/health/ready", timeout=5)
        admin_healthy = admin_response.status_code == 200
        
        # Test public API
        public_response = requests.get(f"{public_url}/health/ready", timeout=5)
        public_healthy = public_response.status_code == 200
        
        if admin_healthy and public_healthy:
            logger.info("Kratos service connection verified")
        else:
            logger.warning(f"Kratos health check failed - Admin: {admin_healthy}, Public: {public_healthy}")
            
    except Exception as e:
        logger.error(f"Kratos service connection failed: {str(e)}")

# =====================================
# WEBHOOK HELPERS
# =====================================

async def handle_kratos_webhook(
    webhook_data: Dict[str, Any],
    db: Database
) -> Dict[str, Any]:
    """Handle Kratos webhook events"""
    try:
        event_type = webhook_data.get("type")
        identity = webhook_data.get("identity", {})
        
        # Log webhook event
        audit_doc = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": f"kratos_webhook_{event_type}",
            "tenant_id": None,
            "user_id": identity.get("id"),
            "target_user_id": None,
            "admin_user_id": None,
            "ip_address": None,
            "user_agent": "kratos_webhook",
            "details": webhook_data,
            "severity": "info",
            "session_id": None,
            "action": f"webhook_{event_type}",
            "resource": "kratos",
            "before_state": None,
            "after_state": webhook_data,
            "correlation_id": f"kratos_webhook_{datetime.now().timestamp()}"
        }
        
        db.audit_logs.insert_one(audit_doc)
        
        logger.info(f"Processed Kratos webhook: {event_type} for identity {identity.get('id')}")
        
        return {"status": "processed", "event_type": event_type}
        
    except Exception as e:
        logger.error(f"Failed to process Kratos webhook: {str(e)}")
        return {"status": "error", "error": str(e)}

# =====================================
# EXAMPLE USAGE
# =====================================

"""
Example FastAPI routes using KratosService:

@app.post("/auth/register")
async def register(
    request: RegisterRequest,
    kratos_service: KratosService = Depends(get_kratos_service)
):
    identity = await kratos_service.create_identity(
        email=request.email,
        password=request.password,
        traits={"name": request.name}
    )
    return {"identity_id": identity.id, "email": identity.email}

@app.post("/auth/recovery")
async def recovery(
    email: str,
    kratos_service: KratosService = Depends(get_kratos_service)
):
    identity = await kratos_service.get_identity_by_email(email)
    if not identity:
        raise HTTPException(status_code=404, detail="User not found")
    
    recovery_link = await kratos_service.create_recovery_link(identity.id)
    return {"recovery_link": recovery_link}

@app.post("/webhooks/kratos")
async def kratos_webhook(
    webhook_data: dict,
    db: Database = Depends(get_database)
):
    result = await handle_kratos_webhook(webhook_data, db)
    return result
"""