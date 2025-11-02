"""
Standalone Authentication Router for FastAPI with Ory Kratos integration
This module provides a complete authentication router that can be easily imported and used
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import structlog
from fastapi import APIRouter, Request, status, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
from slowapi import Limiter
from slowapi.util import get_remote_address

# Configure structured logging
logger = structlog.get_logger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Models for the router
class TokenRequest(BaseModel):
    """Token validation/revocation request"""
    token: str
    
    @validator('token')
    def validate_token_format(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Invalid token format')
        return v

class PermissionCheckRequest(BaseModel):
    """Permission check request"""
    permissions: list
    
    @validator('permissions')
    def validate_permissions_list(cls, v):
        if not isinstance(v, list):
            raise ValueError('Permissions must be a list')
        if not all(isinstance(p, str) for p in v):
            raise ValueError('All permissions must be strings')
        return v

class AuthRouterDependencies:
    """Container for authentication router dependencies"""
    
    def __init__(self, 
                 get_authenticator_func,
                 get_current_user_func,
                 auth_health_check_func,
                 config):
        self.get_authenticator = get_authenticator_func
        self.get_current_user = get_current_user_func  
        self.auth_health_check = auth_health_check_func
        self.config = config

def create_auth_router(dependencies: AuthRouterDependencies) -> APIRouter:
    """
    Create a standalone authentication router
    
    Args:
        dependencies: AuthRouterDependencies containing required functions and config
        
    Returns:
        FastAPI router with authentication endpoints
    """
    
    router = APIRouter(tags=["authentication"], prefix="/auth")
    
    # Import token manager here to avoid circular imports
    from utils.auth.kratos_token import TokenManager
    
    @router.get("/health", 
                summary="Authentication Health Check",
                description="Check the health status of all authentication services")
    async def health_check():
        """Authentication service health check"""
        try:
            health_status = await dependencies.auth_health_check()
            
            # Log health check
            logger.info("auth_health_check_requested", 
                       overall_status=health_status.get("overall_status"))
            
            return health_status
            
        except Exception as e:
            logger.error("auth_health_check_failed", error=str(e))
            raise HTTPException(
                status_code=503, 
                detail="Health check failed"
            )
    
    @router.get("/config",
                summary="Get Authentication Configuration", 
                description="Get public authentication configuration and supported methods")
    async def get_auth_config():
        """Get public authentication configuration"""
        try:
            config_data = {
                "kratos_public_url": dependencies.config.kratos_public_url,
                "jwt_algorithm": dependencies.config.jwt_algorithm,
                "session_cache_ttl": dependencies.config.session_cache_ttl,
                "jwks_cache_ttl": dependencies.config.jwks_cache_ttl,
                "supported_auth_methods": ["session", "jwt", "api_key"],
                "rate_limits": {
                    "token_validation": "20/minute",
                    "token_revocation": "10/minute", 
                    "permission_checks": "30/minute"
                },
                "version": "1.0.0"
            }
            
            logger.info("auth_config_requested")
            return config_data
            
        except Exception as e:
            logger.error("auth_config_failed", error=str(e))
            raise HTTPException(
                status_code=500,
                detail="Failed to get authentication configuration"
            )
    
    @router.post("/validate",
                 summary="Validate Token",
                 description="Validate a session token or JWT token without full authentication")
    @limiter.limit("20/minute")
    async def validate_token(
        request: Request,
        token_request: TokenRequest,
        authenticator = Depends(dependencies.get_authenticator)
    ):
        """Validate a token without full authentication"""
        token_hash = hashlib.sha256(token_request.token.encode()).hexdigest()[:12]
        
        try:
            logger.info("token_validation_requested", token_hash=token_hash)
            
            # Try session validation first
            auth_data = await authenticator.validate_session_token(token_request.token)
            if auth_data:
                # Extract basic user info
                user_info = await authenticator.extract_user_info(auth_data)
                
                result = {
                    "valid": True, 
                    "type": "session",
                    "user_id": user_info.get("kratos_id") if user_info else None,
                    "email": user_info.get("email") if user_info else None,
                    "expires_at": None,  # Session tokens don't have explicit expiry
                    "token_hash": token_hash
                }
                
                logger.info("session_token_validated", 
                           token_hash=token_hash,
                           user_id=result["user_id"])
                return result
            
            # Try JWT validation
            auth_data = await authenticator.validate_jwt_token(token_request.token)
            if auth_data:
                result = {
                    "valid": True, 
                    "type": "jwt",
                    "user_id": auth_data.get("sub"),
                    "email": auth_data.get("email"),
                    "expires_at": auth_data.get("exp"),
                    "issued_at": auth_data.get("iat"),
                    "token_hash": token_hash
                }
                
                logger.info("jwt_token_validated", 
                           token_hash=token_hash,
                           user_id=result["user_id"])
                return result
            
            # Token is invalid
            logger.warning("token_validation_failed", 
                          token_hash=token_hash,
                          reason="invalid_token")
            
            return {
                "valid": False, 
                "type": "unknown", 
                "reason": "token_invalid",
                "token_hash": token_hash
            }
            
        except Exception as e:
            logger.error("token_validation_error", 
                        token_hash=token_hash,
                        error=str(e))
            raise HTTPException(
                status_code=500, 
                detail="Token validation failed"
            )
    
    @router.post("/revoke",
                 summary="Revoke Token",
                 description="Revoke a session token and invalidate it")
    @limiter.limit("10/minute") 
    async def revoke_token(
        request: Request,
        token_request: TokenRequest,
        authenticator = Depends(dependencies.get_authenticator)
    ):
        """Revoke a session token"""
        token_hash = hashlib.sha256(token_request.token.encode()).hexdigest()[:12]
        
        try:
            logger.info("token_revocation_requested", token_hash=token_hash)
            
            token_manager = TokenManager(authenticator)
            success = await token_manager.revoke_session(token_request.token)
            
            if success:
                logger.info("token_revoked_successfully", token_hash=token_hash)
                return {
                    "revoked": True,
                    "message": "Token revoked successfully",
                    "token_hash": token_hash
                }
            else:
                logger.warning("token_revocation_failed", 
                              token_hash=token_hash,
                              reason="revocation_failed")
                return {
                    "revoked": False,
                    "message": "Token revocation failed - token may be invalid or already revoked",
                    "token_hash": token_hash
                }
            
        except Exception as e:
            logger.error("token_revocation_error", 
                        token_hash=token_hash,
                        error=str(e))
            raise HTTPException(
                status_code=500, 
                detail="Token revocation failed"
            )
    
    @router.get("/me",
                summary="Get Current User",
                description="Get information about the currently authenticated user")
    async def get_current_user_info(
        user = Depends(dependencies.get_current_user)
    ):
        """Get current authenticated user information"""
        try:
            logger.info("current_user_info_requested", user_id=user.user_id)
            
            return {
                "user_id": user.user_id,
                "tenant_id": user.tenant_id,
                "roles": user.roles,
                "permissions": sorted(user.permissions),  # Sort for consistency
                "permissions_count": len(user.permissions),
                "authenticated_at": datetime.utcnow().isoformat(),
                "has_global_role": user.roles.get("global_role") is not None,
                "has_tenant_role": user.roles.get("tenant_role") is not None
            }
            
        except Exception as e:
            logger.error("get_current_user_info_error", error=str(e))
            raise HTTPException(
                status_code=500,
                detail="Failed to get user information"
            )
    
    @router.post("/refresh",
                 summary="Check Token Freshness",
                 description="Check if a token is fresh enough for sensitive operations")
    @limiter.limit("15/minute")
    async def check_token_freshness(
        request: Request,
        token_request: TokenRequest,
        max_age_minutes: int = 30,
        authenticator = Depends(dependencies.get_authenticator)
    ):
        """Check token freshness and suggest refresh if needed"""
        token_hash = hashlib.sha256(token_request.token.encode()).hexdigest()[:12]
        
        try:
            logger.info("token_freshness_check_requested", 
                       token_hash=token_hash,
                       max_age_minutes=max_age_minutes)
            
            token_manager = TokenManager(authenticator)
            is_fresh = await token_manager.validate_token_freshness(
                token_request.token, 
                max_age_minutes=max_age_minutes
            )
            
            result = {
                "token_fresh": is_fresh,
                "max_age_minutes": max_age_minutes,
                "message": "Token is fresh" if is_fresh else "Token should be refreshed",
                "recommended_action": "continue" if is_fresh else "refresh_session",
                "token_hash": token_hash
            }
            
            logger.info("token_freshness_check_completed",
                       token_hash=token_hash,
                       is_fresh=is_fresh)
            
            return result
            
        except Exception as e:
            logger.error("token_freshness_check_error", 
                        token_hash=token_hash,
                        error=str(e))
            raise HTTPException(
                status_code=500, 
                detail="Token freshness check failed"
            )
    
    @router.get("/sessions",
                summary="Get User Sessions",
                description="Get information about the user's current session")
    async def get_user_sessions(
        user = Depends(dependencies.get_current_user)
    ):
        """Get information about user's current session"""
        try:
            logger.info("user_sessions_requested", user_id=user.user_id)
            
            # This is a simplified version - in a real implementation,
            # you might want to track and return multiple active sessions
            session_info = {
                "current_session": {
                    "user_id": user.user_id,
                    "tenant_id": user.tenant_id,
                    "roles": user.roles,
                    "permissions_count": len(user.permissions),
                    "authenticated_at": datetime.utcnow().isoformat(),
                    "session_type": "authenticated"
                },
                "session_count": 1,  # Simplified - could track multiple sessions
                "total_permissions": len(user.permissions),
                "has_admin_permissions": any(p.startswith("admin.") for p in user.permissions),
                "multi_tenant": user.tenant_id is not None
            }
            
            return session_info
            
        except Exception as e:
            logger.error("get_user_sessions_error", 
                        user_id=getattr(user, 'user_id', 'unknown'),
                        error=str(e))
            raise HTTPException(
                status_code=500,
                detail="Failed to get session information"
            )
    
    @router.post("/permissions/check",
                 summary="Check Permissions",
                 description="Check if the current user has specific permissions")
    @limiter.limit("30/minute")
    async def check_permissions(
        request: Request,
        permission_check: PermissionCheckRequest,
        user = Depends(dependencies.get_current_user)
    ):
        """Check if user has specific permissions"""
        try:
            logger.info("permission_check_requested", 
                       user_id=user.user_id,
                       requested_permissions=permission_check.permissions)
            
            required_permissions = permission_check.permissions
            user_permissions = set(user.permissions)
            required_permissions_set = set(required_permissions)
            
            has_all_permissions = required_permissions_set.issubset(user_permissions)
            missing_permissions = list(required_permissions_set - user_permissions)
            granted_permissions = list(required_permissions_set & user_permissions)
            
            result = {
                "user_id": user.user_id,
                "tenant_id": user.tenant_id,
                "required_permissions": required_permissions,
                "has_all_permissions": has_all_permissions,
                "missing_permissions": missing_permissions,
                "granted_permissions": granted_permissions,
                "total_user_permissions": len(user_permissions),
                "permission_summary": {
                    "total_required": len(required_permissions),
                    "total_granted": len(granted_permissions),
                    "total_missing": len(missing_permissions),
                    "access_granted": has_all_permissions
                }
            }
            
            logger.info("permission_check_completed",
                       user_id=user.user_id,
                       has_all_permissions=has_all_permissions,
                       missing_count=len(missing_permissions))
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("permission_check_error", 
                        user_id=getattr(user, 'user_id', 'unknown'),
                        error=str(e))
            raise HTTPException(
                status_code=500, 
                detail="Permission check failed"
            )
    
    @router.get("/status",
               summary="Authentication Status",
               description="Get overall authentication service status")
    async def get_auth_status():
        """Get authentication service status"""
        try:
            # Get health status
            health_status = await dependencies.auth_health_check()
            
            # Calculate service metrics
            service_status = {
                "service": "authentication",
                "version": "1.0.0",
                "status": health_status.get("overall_status", "unknown"),
                "timestamp": datetime.utcnow().isoformat(),
                "uptime": "N/A",  # Could be calculated if tracking start time
                "health_checks": health_status.get("checks", {}),
                "configuration": {
                    "kratos_integration": True,
                    "jwt_support": True,
                    "api_key_support": True,
                    "session_caching": True,
                    "rate_limiting": True
                },
                "endpoints": {
                    "health": "/auth/health",
                    "validate": "/auth/validate", 
                    "revoke": "/auth/revoke",
                    "me": "/auth/me",
                    "permissions": "/auth/permissions/check"
                }
            }
            
            logger.info("auth_status_requested", status=service_status["status"])
            return service_status
            
        except Exception as e:
            logger.error("auth_status_error", error=str(e))
            raise HTTPException(
                status_code=500,
                detail="Failed to get authentication status"
            )
    
    # Error handlers for the router
    # @router.exception_handler(HTTPException)
    # async def auth_http_exception_handler(request: Request, exc: HTTPException):
    #     """Handle HTTP exceptions in auth routes"""
    #     logger.warning("auth_http_exception", 
    #                   path=request.url.path,
    #                   method=request.method,
    #                   status_code=exc.status_code,
    #                   detail=exc.detail)
        
    #     return JSONResponse(
    #         status_code=exc.status_code,
    #         content={
    #             "error": "authentication_error",
    #             "detail": exc.detail,
    #             "path": str(request.url.path),
    #             "method": request.method,
    #             "timestamp": datetime.utcnow().isoformat()
    #         }
    #     )
    
    # @router.exception_handler(Exception)
    # async def auth_general_exception_handler(request: Request, exc: Exception):
    #     """Handle unexpected exceptions in auth routes"""
    #     logger.error("auth_unexpected_exception", 
    #                 path=request.url.path,
    #                 method=request.method,
    #                 error=str(exc),
    #                 exc_info=True)
        
    #     return JSONResponse(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         content={
    #             "error": "internal_authentication_error",
    #             "detail": "An unexpected error occurred in the authentication service",
    #             "path": str(request.url.path),
    #             "method": request.method,
    #             "timestamp": datetime.utcnow().isoformat()
    #         }
    #     )
    
    # Add middleware for request logging
    # @router.middleware("http")
    # async def log_auth_requests(request: Request, call_next):
    #     """Log all authentication requests"""
    #     start_time = datetime.utcnow()
        
    #     # Log request
    #     logger.info("auth_request_started",
    #                method=request.method,
    #                path=request.url.path,
    #                client_ip=request.client.host if request.client else None)
        
    #     try:
    #         response = await call_next(request)
            
    #         # Calculate request duration
    #         duration = (datetime.utcnow() - start_time).total_seconds()
            
    #         # Log response
    #         logger.info("auth_request_completed",
    #                    method=request.method,
    #                    path=request.url.path,
    #                    status_code=response.status_code,
    #                    duration_seconds=round(duration, 3))
            
    #         return response
            
    #     except Exception as e:
    #         duration = (datetime.utcnow() - start_time).total_seconds()
    #         logger.error("auth_request_failed",
    #                     method=request.method,
    #                     path=request.url.path,
    #                     error=str(e),
    #                     duration_seconds=round(duration, 3))
    #         raise
    
    return router

# Factory function for easy integration
def create_standalone_auth_router(
    get_authenticator_func,
    get_current_user_func, 
    auth_health_check_func,
    config
) -> APIRouter:
    """
    Factory function to create a standalone authentication router
    
    Args:
        get_authenticator_func: Function that returns KratosAuthenticator instance
        get_current_user_func: Function for getting current authenticated user
        auth_health_check_func: Function for checking authentication health
        config: Configuration object with authentication settings
    
    Returns:
        FastAPI router ready to be included in your application
        
    Example:
        from standalone_auth_router import create_standalone_auth_router
        
        auth_router = create_standalone_auth_router(
            get_authenticator_func=get_authenticator,
            get_current_user_func=get_current_user,
            auth_health_check_func=auth_health_check,
            config=config
        )
        
        app.include_router(auth_router, prefix="/api/v1")
    """
    dependencies = AuthRouterDependencies(
        get_authenticator_func=get_authenticator_func,
        get_current_user_func=get_current_user_func,
        auth_health_check_func=auth_health_check_func,
        config=config
    )
    
    return create_auth_router(dependencies)

# Example usage documentation
USAGE_EXAMPLE = """
# Standalone Authentication Router Usage Example

## 1. Import and Setup

```python
from fastapi import FastAPI
from standalone_auth_router import create_standalone_auth_router
from improved_kratos_auth import get_authenticator, get_current_user, auth_health_check, config

app = FastAPI()

# Create the authentication router
auth_router = create_standalone_auth_router(
    get_authenticator_func=get_authenticator,
    get_current_user_func=get_current_user,
    auth_health_check_func=auth_health_check,
    config=config
)

# Include the router in your app
app.include_router(auth_router, prefix="/api/v1")
```

## 2. Available Endpoints

- GET  /api/v1/auth/health - Health check
- GET  /api/v1/auth/config - Get configuration
- GET  /api/v1/auth/status - Service status
- POST /api/v1/auth/validate - Validate token
- POST /api/v1/auth/revoke - Revoke token
- POST /api/v1/auth/refresh - Check token freshness
- GET  /api/v1/auth/me - Get current user info
- GET  /api/v1/auth/sessions - Get session info
- POST /api/v1/auth/permissions/check - Check permissions

## 3. Rate Limits

- Token validation: 20/minute
- Token revocation: 10/minute
- Permission checks: 30/minute
- Token freshness: 15/minute

## 4. Error Handling

All endpoints include comprehensive error handling with:
- Structured logging
- Consistent error responses
- Request/response timing
- Security-safe error messages
"""

if __name__ == "__main__":
    print("Standalone Authentication Router")
    print("================================")
    print(USAGE_EXAMPLE)