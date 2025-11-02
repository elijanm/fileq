# Enhanced main.py with multi-tenant API endpoints

from fastapi import FastAPI, APIRouter,HTTPException, Request, Depends, status, Header
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict, Any
import logging
from bson import ObjectId
from metrics.metrics import MetricsCollector,get_metrics
from utils.user import get_client_info,ClientInfo

# Import tenant services
from services.tenant_service import TenantService, TenantStatus, SubscriptionPlan
from services.user_service import UserService,RegistrationRequest,RegisterRequestModel,get_user_service,get_current_user
router = APIRouter(prefix="/uploads", tags=["uploads"])
logger = logging.getLogger(__name__)


# In your FastAPI route
# @router.post("/billing/setup")
# async def setup_billing(
#     tenant_id: str,
#     billing_service: LagoBillingService = Depends(get_lago_billing_service)
# ):
#     result = await billing_service.setup_tenant_billing(
#         tenant_id=tenant_id,
#         organization_name="Acme Corp",
#         admin_email="admin@acme.com"
#     )
#     return result

# @router.post("/users/{user_id}/subscription")
# async def create_subscription(
#     user_id: str,
#     plan_code: str,
#     tenant_context: str = Depends(get_tenant_context),
#     billing_service: LagoBillingService = Depends(get_lago_billing_service)
# ):
#     return await billing_service.create_user_subscription(
#         user_id=user_id,
#         plan_code=plan_code,
#         tenant_id=tenant_context
#     )

# @router.post("/usage/track")
# async def track_usage(
#     user_id: str,
#     metric_code: str,
#     properties: dict,
#     tenant_context: str = Depends(get_tenant_context),
#     billing_service: LagoBillingService = Depends(get_lago_billing_service)
# ):
#     return await billing_service.track_usage(
#         user_id=user_id,
#         metric_code=metric_code,
#         properties=properties,
#         tenant_id=tenant_context
#     )
    
    
# Multi-tenant models
class CreateTenantModel(BaseModel):
    name: str
    subdomain: str
    domain: Optional[str] = None
    subscription_plan: str = "trial"
    
    @validator('subdomain')
    def validate_subdomain(cls, v):
        if len(v) < 3 or len(v) > 63:
            raise ValueError('Subdomain must be 3-63 characters long')
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Subdomain can only contain letters, numbers, hyphens, and underscores')
        return v.lower()

class InviteUserModel(BaseModel):
    email: EmailStr
    role: str = "user"
    message: Optional[str] = None
    
    @validator('role')
    def validate_role(cls, v):
        valid_roles = ["admin", "user", "guest", "billing_admin"]
        if v not in valid_roles:
            raise ValueError(f'Role must be one of: {valid_roles}')
        return v

class AcceptInvitationModel(BaseModel):
    invitation_token: str

class SwitchTenantModel(BaseModel):
    tenant_id: str

# Tenant context dependency
async def get_tenant_context(
    request: Request,
    x_tenant_id: Optional[str] = Header(None),
    tenant_subdomain: Optional[str] = Header(None)
) -> Optional[str]:
    """Extract tenant context from headers or subdomain"""
    
    # Priority: X-Tenant-ID header, then subdomain header, then from URL
    if x_tenant_id:
        return x_tenant_id
    
    if tenant_subdomain:
        tenant_service = request.app.state.tenant_service
        tenant = await tenant_service.get_tenant_by_subdomain(tenant_subdomain)
        return tenant.id if tenant else None
    
    # Could also extract from hostname/subdomain
    # host = request.headers.get("host", "")
    # if "." in host:
    #     subdomain = host.split(".")[0]
    #     # ... resolve tenant
    
    return None

async def get_tenant_service(request: Request) -> TenantService:
    """Get tenant service from app state"""
    return request.app.state.tenant_service

# Enhanced registration with tenant assignment
@router.post("/auth/register", response_model=Dict[str, Any])
async def register_user(
    request_data: RegisterRequestModel,
    request: Request,
    tenant_context: Optional[str] = Depends(get_tenant_context),
    user_service: UserService = Depends(get_user_service),
    tenant_service: TenantService = Depends(get_tenant_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Register a new user with tenant assignment"""
    client_info = get_client_info(request)
    
    try:
        with metrics.auth_request_duration.labels(endpoint='register').time():
            # Standard registration
            registration_request = RegistrationRequest(
                email=request_data.email,
                password=request_data.password,
                name=request_data.name,
                terms_accepted=request_data.terms_accepted,
                marketing_consent=request_data.marketing_consent,
                referral_code=request_data.referral_code
            )
            
            result = await user_service.register_user(
                registration_request,
                ip_address=client_info["ip_address"]
            )
            
            # Multi-tenant handling
            if tenant_context:
                # Add user to specific tenant
                await tenant_service._add_user_to_tenant(
                    tenant_id=tenant_context,
                    user_id=result["user_id"],
                    role="user"
                )
            else:
                # Add to default tenant
                default_tenant_id = await user_service._get_default_tenant_id()
                if default_tenant_id:
                    await tenant_service._add_user_to_tenant(
                        tenant_id=default_tenant_id,
                        user_id=result["user_id"],
                        role="user"
                    )
            
            metrics.auth_requests_total.labels(
                method='register', 
                status='success', 
                endpoint='register'
            ).inc()
            
            return result
            
    except Exception as e:
        metrics.auth_requests_total.labels(
            method='register', 
            status='error', 
            endpoint='register'
        ).inc()
        raise

# Tenant management endpoints
@router.post("/auth/tenants", response_model=Dict[str, Any])
async def create_tenant(
    request_data: CreateTenantModel,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Create a new tenant"""
    try:
        result = await tenant_service.create_tenant(
            creator_user_id=current_user["user_id"],
            name=request_data.name,
            subdomain=request_data.subdomain,
            domain=request_data.domain,
            subscription_plan=request_data.subscription_plan
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Tenant creation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create tenant")

@router.get("/auth/tenants/me", response_model=Dict[str, Any])
async def get_my_tenants(
    current_user: Dict[str, Any] = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Get all tenants for current user"""
    try:
        tenants = await tenant_service.get_user_tenants(current_user["user_id"])
        
        return {
            "tenants": [
                {
                    "id": t["tenant"].id,
                    "name": t["tenant"].name,
                    "subdomain": t["tenant"].subdomain,
                    "status": t["tenant"].status.value,
                    "role": t["role"],
                    "permissions": t["permissions"],
                    "user_count": t["tenant"].user_count
                }
                for t in tenants
            ],
            "total": len(tenants)
        }
        
    except Exception as e:
        logger.error(f"Failed to get user tenants: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tenants")

@router.get("/auth/tenants/{tenant_id}", response_model=Dict[str, Any])
async def get_tenant_details(
    tenant_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Get tenant details"""
    try:
        # Check if user has access to tenant
        if not await tenant_service._user_has_tenant_access(current_user["user_id"], tenant_id):
            raise HTTPException(status_code=403, detail="Access denied to tenant")
        
        tenant = await tenant_service.get_tenant_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        return {
            "id": tenant.id,
            "name": tenant.name,
            "subdomain": tenant.subdomain,
            "domain": tenant.domain,
            "status": tenant.status.value,
            "subscription_plan": tenant.subscription_plan.value,
            "settings": tenant.settings,
            "created_at": tenant.created_at.isoformat(),
            "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
            "user_count": tenant.user_count,
            "admin_count": tenant.admin_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tenant details: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tenant details")

@router.put("/auth/tenants/{tenant_id}/settings", response_model=Dict[str, str])
async def update_tenant_settings(
    tenant_id: str,
    settings: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Update tenant settings"""
    try:
        result = await tenant_service.update_tenant_settings(
            admin_user_id=current_user["user_id"],
            tenant_id=tenant_id,
            settings=settings
        )
        
        return result
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update tenant settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update tenant settings")

# Tenant user management
@router.post("/auth/tenants/{tenant_id}/invitations", response_model=Dict[str, str])
async def invite_user_to_tenant(
    tenant_id: str,
    request_data: InviteUserModel,
    current_user: Dict[str, Any] = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Invite user to tenant"""
    try:
        result = await tenant_service.invite_user_to_tenant(
            inviter_user_id=current_user["user_id"],
            tenant_id=tenant_id,
            email=request_data.email,
            role=request_data.role,
            message=request_data.message
        )
        
        return result
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to invite user: {e}")
        raise HTTPException(status_code=500, detail="Failed to send invitation")

@router.post("/auth/invitations/accept", response_model=Dict[str, Any])
async def accept_tenant_invitation(
    request_data: AcceptInvitationModel,
    current_user: Dict[str, Any] = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Accept tenant invitation"""
    try:
        result = await tenant_service.accept_tenant_invitation(
            user_id=current_user["user_id"],
            invitation_token=request_data.invitation_token
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to accept invitation: {e}")
        raise HTTPException(status_code=500, detail="Failed to accept invitation")

@router.get("/auth/tenants/{tenant_id}/users", response_model=Dict[str, Any])
async def get_tenant_users(
    tenant_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service),
    page: int = 1,
    limit: int = 50
):
    """Get all users in a tenant"""
    try:
        result = await tenant_service.get_tenant_users(
            admin_user_id=current_user["user_id"],
            tenant_id=tenant_id,
            page=page,
            limit=limit
        )
        
        # Convert dataclasses to dicts
        users_data = []
        for user in result["users"]:
            users_data.append({
                "user_id": user.user_id,
                "email": user.email,
                "name": user.name,
                "role": user.role.value,
                "status": user.status,
                "permissions": user.permissions,
                "joined_at": user.joined_at.isoformat() if user.joined_at else None,
                "last_accessed": user.last_accessed.isoformat() if user.last_accessed else None
            })
        
        return {
            "users": users_data,
            "total": result["total"],
            "page": result["page"],
            "pages": result["pages"]
        }
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get tenant users: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tenant users")

@router.delete("/auth/tenants/{tenant_id}/users/{user_id}", response_model=Dict[str, str])
async def remove_user_from_tenant(
    tenant_id: str,
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Remove user from tenant"""
    try:
        result = await tenant_service.remove_user_from_tenant(
            admin_user_id=current_user["user_id"],
            tenant_id=tenant_id,
            target_user_id=user_id
        )
        
        return result
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to remove user from tenant: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove user")

@router.post("/auth/switch-tenant", response_model=Dict[str, Any])
async def switch_tenant(
    request_data: SwitchTenantModel,
    current_user: Dict[str, Any] = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Switch user's active tenant"""
    try:
        result = await tenant_service.switch_user_tenant(
            user_id=current_user["user_id"],
            tenant_id=request_data.tenant_id
        )
        
        return result
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to switch tenant: {e}")
        raise HTTPException(status_code=500, detail="Failed to switch tenant")

# Enhanced user profile with tenant context
@router.get("/auth/me", response_model=Dict[str, Any])
async def get_current_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    tenant_service: TenantService = Depends(get_tenant_service),
    tenant_context: Optional[str] = Depends(get_tenant_context),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Get current user profile with tenant context"""
    try:
        with metrics.auth_request_duration.labels(endpoint='whoami').time():
            # Get base user profile
            profile = await user_service.get_user_profile(current_user["user_id"])
            
            # Get user's tenants
            user_tenants = await tenant_service.get_user_tenants(current_user["user_id"])
            
            # Get current tenant info
            current_tenant = None
            current_tenant_role = None
            current_tenant_permissions = []
            
            if tenant_context:
                for tenant_info in user_tenants:
                    if tenant_info["tenant"].id == tenant_context:
                        current_tenant = {
                            "id": tenant_info["tenant"].id,
                            "name": tenant_info["tenant"].name,
                            "subdomain": tenant_info["tenant"].subdomain
                        }
                        current_tenant_role = tenant_info["role"]
                        current_tenant_permissions = tenant_info["permissions"]
                        break
            
            # Get primary tenant if no context
            if not current_tenant and profile.primary_tenant_id:
                primary_tenant = await tenant_service.get_tenant_by_id(str(profile.primary_tenant_id))
                if primary_tenant:
                    # Find role in this tenant
                    for tenant_info in user_tenants:
                        if tenant_info["tenant"].id == primary_tenant.id:
                            current_tenant = {
                                "id": primary_tenant.id,
                                "name": primary_tenant.name,
                                "subdomain": primary_tenant.subdomain
                            }
                            current_tenant_role = tenant_info["role"]
                            current_tenant_permissions = tenant_info["permissions"]
                            break
            
            metrics.auth_requests_total.labels(
                method='whoami', 
                status='success', 
                endpoint='whoami'
            ).inc()
            
            return {
                "user_id": profile.user_id,
                "email": profile.email,
                "name": profile.name,
                "global_role": profile.global_role.value if hasattr(profile, 'global_role') else "user",
                "status": profile.status.value,
                "created_at": profile.created_at.isoformat(),
                "last_login": profile.last_login.isoformat() if profile.last_login else None,
                "is_verified": profile.is_verified,
                "preferences": profile.preferences,
                "current_tenant": current_tenant,
                "current_tenant_role": current_tenant_role,
                "current_tenant_permissions": current_tenant_permissions,
                "tenant_count": len(user_tenants)
            }
            
    except Exception as e:
        metrics.auth_requests_total.labels(
            method='whoami', 
            status='error', 
            endpoint='whoami'
        ).inc()
        logger.error(f"Failed to get user profile: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to retrieve user information"
        )

# Subdomain-based tenant resolution
@router.get("/auth/resolve-tenant/{subdomain}", response_model=Dict[str, Any])
async def resolve_tenant_by_subdomain(
    subdomain: str,
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Resolve tenant by subdomain (public endpoint)"""
    try:
        tenant = await tenant_service.get_tenant_by_subdomain(subdomain)
        
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        if tenant.status not in [TenantStatus.ACTIVE, TenantStatus.TRIAL]:
            raise HTTPException(status_code=403, detail="Tenant is not active")
        
        return {
            "tenant_id": tenant.id,
            "name": tenant.name,
            "subdomain": tenant.subdomain,
            "status": tenant.status.value,
            "branding": tenant.settings.get("branding", {}),
            "features": {
                "sso_enabled": tenant.settings.get("features", {}).get("sso_enabled", False),
                "mfa_required": tenant.settings.get("features", {}).get("mfa_required", False)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve tenant: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve tenant")

# Admin endpoints for tenant management
@router.get("/auth/admin/tenants", response_model=Dict[str, Any])
async def list_all_tenants(
    current_user: Dict[str, Any] = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service),
    page: int = 1,
    limit: int = 50,
    status_filter: Optional[str] = None
):
    """List all tenants (superadmin only)"""
    
    # Check superadmin permission
    user = tenant_service.users_collection.find_one({"kratos_id": current_user["user_id"]})
    if not user or user.get("global_role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    
    try:
        # Build query
        query = {}
        if status_filter:
            query["status"] = status_filter
        
        # Get paginated results
        skip = (page - 1) * limit
        tenants_cursor = tenant_service.tenants_collection.find(query).skip(skip).limit(limit)
        total_count = tenant_service.tenants_collection.count_documents(query)
        
        tenants = []
        for tenant_doc in tenants_cursor:
            tenant = tenant_service._doc_to_tenant(tenant_doc)
            tenants.append({
                "id": tenant.id,
                "name": tenant.name,
                "subdomain": tenant.subdomain,
                "status": tenant.status.value,
                "subscription_plan": tenant.subscription_plan.value,
                "user_count": tenant.user_count,
                "created_at": tenant.created_at.isoformat(),
                "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None
            })
        
        return {
            "tenants": tenants,
            "total": total_count,
            "page": page,
            "pages": (total_count + limit - 1) // limit
        }
        
    except Exception as e:
        logger.error(f"Failed to list tenants: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve tenants")

@router.put("/auth/admin/tenants/{tenant_id}/status", response_model=Dict[str, str])
async def update_tenant_status(
    tenant_id: str,
    status: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    tenant_service: TenantService = Depends(get_tenant_service)
):
    """Update tenant status (superadmin only)"""
    
    # Check superadmin permission
    user = tenant_service.users_collection.find_one({"kratos_id": current_user["user_id"]})
    if not user or user.get("global_role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superladmin access required")
    
    # Validate status
    try:
        TenantStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    try:
        result = tenant_service.tenants_collection.update_one(
            {"_id": ObjectId(tenant_id)},
            {
                "$set": {
                    "status": status,
                    "updated_at": datetime.utcnow().isoformat()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Audit log
        await tenant_service.audit_service.log_event(
            "tenant_status_updated",
            user_id=current_user["user_id"],
            tenant_id=ObjectId(tenant_id),
            details={"new_status": status},
            severity="warning"
        )
        
        return {"message": f"Tenant status updated to {status}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update tenant status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update tenant status")

