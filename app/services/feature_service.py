# services/feature_service.py - Feature management with Lago integration

from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import asyncio

from .lago_billing import LagoBillingService
from .tenant_service import TenantService

logger = logging.getLogger(__name__)

class SubscriptionPlan(Enum):
    TRIAL = "trial"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

class FeatureFlag(Enum):
    # Authentication features
    SSO_ENABLED = "sso_enabled"
    MFA_REQUIRED = "mfa_required"
    CUSTOM_ROLES = "custom_roles"
    
    # API features
    API_ACCESS = "api_access"
    WEBHOOK_SUPPORT = "webhook_support"
    ADVANCED_ANALYTICS = "advanced_analytics"
    
    # Integration features
    SLACK_INTEGRATION = "slack_integration"
    TEAMS_INTEGRATION = "teams_integration"
    CUSTOM_INTEGRATIONS = "custom_integrations"
    
    # Admin features
    AUDIT_LOGS = "audit_logs"
    ADVANCED_REPORTING = "advanced_reporting"
    WHITE_LABEL_BRANDING = "white_label_branding"

@dataclass
class PlanLimits:
    max_users: Optional[int]
    max_admins: Optional[int]
    storage_gb: Optional[int]
    api_calls_per_month: Optional[int]
    max_integrations: Optional[int]
    support_level: str  # "community", "email", "priority", "phone"

@dataclass
class UsageData:
    current_users: int
    current_admins: int
    storage_used_gb: float
    api_calls_this_month: int
    integrations_count: int
    last_updated: datetime

class FeatureService:
    """Service to manage subscription plans, features, and limits"""
    
    def __init__(
        self,
        tenant_service: TenantService,
        lago_service: LagoBillingService,
        tenants_collection,
        usage_collection
    ):
        self.tenant_service = tenant_service
        self.lago_service = lago_service
        self.tenants_collection = tenants_collection
        self.usage_collection = usage_collection
        
        # Define plan configurations
        self.plan_configs = {
            SubscriptionPlan.TRIAL: {
                "features": [
                    FeatureFlag.API_ACCESS,
                    FeatureFlag.AUDIT_LOGS
                ],
                "limits": PlanLimits(
                    max_users=5,
                    max_admins=2,
                    storage_gb=1,
                    api_calls_per_month=1000,
                    max_integrations=0,
                    support_level="community"
                ),
                "lago_plan_code": "trial_plan"
            },
            SubscriptionPlan.BASIC: {
                "features": [
                    FeatureFlag.API_ACCESS,
                    FeatureFlag.AUDIT_LOGS,
                    FeatureFlag.WEBHOOK_SUPPORT,
                    FeatureFlag.SLACK_INTEGRATION
                ],
                "limits": PlanLimits(
                    max_users=25,
                    max_admins=5,
                    storage_gb=10,
                    api_calls_per_month=10000,
                    max_integrations=2,
                    support_level="email"
                ),
                "lago_plan_code": "basic_plan"
            },
            SubscriptionPlan.PROFESSIONAL: {
                "features": [
                    FeatureFlag.API_ACCESS,
                    FeatureFlag.SSO_ENABLED,
                    FeatureFlag.CUSTOM_ROLES,
                    FeatureFlag.AUDIT_LOGS,
                    FeatureFlag.WEBHOOK_SUPPORT,
                    FeatureFlag.ADVANCED_ANALYTICS,
                    FeatureFlag.SLACK_INTEGRATION,
                    FeatureFlag.TEAMS_INTEGRATION,
                    FeatureFlag.ADVANCED_REPORTING
                ],
                "limits": PlanLimits(
                    max_users=100,
                    max_admins=15,
                    storage_gb=100,
                    api_calls_per_month=100000,
                    max_integrations=10,
                    support_level="priority"
                ),
                "lago_plan_code": "professional_plan"
            },
            SubscriptionPlan.ENTERPRISE: {
                "features": [
                    FeatureFlag.API_ACCESS,
                    FeatureFlag.SSO_ENABLED,
                    FeatureFlag.MFA_REQUIRED,
                    FeatureFlag.CUSTOM_ROLES,
                    FeatureFlag.AUDIT_LOGS,
                    FeatureFlag.WEBHOOK_SUPPORT,
                    FeatureFlag.ADVANCED_ANALYTICS,
                    FeatureFlag.SLACK_INTEGRATION,
                    FeatureFlag.TEAMS_INTEGRATION,
                    FeatureFlag.CUSTOM_INTEGRATIONS,
                    FeatureFlag.ADVANCED_REPORTING,
                    FeatureFlag.WHITE_LABEL_BRANDING
                ],
                "limits": PlanLimits(
                    max_users=None,  # Unlimited
                    max_admins=None,
                    storage_gb=None,
                    api_calls_per_month=None,
                    max_integrations=None,
                    support_level="phone"
                ),
                "lago_plan_code": "enterprise_plan"
            }
        }
    
    async def check_feature_access(self, tenant_id: str, feature: FeatureFlag) -> bool:
        """Check if tenant has access to a specific feature"""
        try:
            tenant = await self.tenant_service.get_tenant_by_id(tenant_id)
            if not tenant:
                return False
            
            plan = SubscriptionPlan(tenant.subscription_plan)
            plan_config = self.plan_configs[plan]
            
            return feature in plan_config["features"]
            
        except Exception as e:
            logger.error(f"Error checking feature access: {e}")
            return False
    
    async def check_usage_limit(
        self, 
        tenant_id: str, 
        limit_type: str, 
        current_usage: Optional[int] = None
    ) -> Dict[str, Any]:
        """Check if tenant has exceeded usage limits"""
        try:
            tenant = await self.tenant_service.get_tenant_by_id(tenant_id)
            if not tenant:
                raise ValueError("Tenant not found")
            
            plan = SubscriptionPlan(tenant.subscription_plan)
            limits = self.plan_configs[plan]["limits"]
            
            # Get current usage if not provided
            if current_usage is None:
                usage_data = await self._get_current_usage(tenant_id)
                current_usage = getattr(usage_data, limit_type, 0)
            
            # Get limit for this type
            limit_value = getattr(limits, limit_type)
            
            if limit_value is None:  # Unlimited
                return {
                    "within_limit": True,
                    "current_usage": current_usage,
                    "limit": None,
                    "usage_percentage": 0
                }
            
            within_limit = current_usage < limit_value
            usage_percentage = (current_usage / limit_value) * 100
            
            return {
                "within_limit": within_limit,
                "current_usage": current_usage,
                "limit": limit_value,
                "usage_percentage": usage_percentage,
                "remaining": limit_value - current_usage if within_limit else 0
            }
            
        except Exception as e:
            logger.error(f"Error checking usage limit: {e}")
            raise
    
    async def can_add_user(self, tenant_id: str) -> Dict[str, Any]:
        """Check if tenant can add more users"""
        return await self.check_usage_limit(tenant_id, "max_users")
    
    async def can_add_admin(self, tenant_id: str) -> Dict[str, Any]:
        """Check if tenant can add more admins"""
        return await self.check_usage_limit(tenant_id, "max_admins")
    
    async def can_use_storage(self, tenant_id: str, additional_gb: float) -> Dict[str, Any]:
        """Check if tenant can use additional storage"""
        usage_data = await self._get_current_usage(tenant_id)
        projected_usage = usage_data.storage_used_gb + additional_gb
        
        return await self.check_usage_limit(
            tenant_id, 
            "storage_gb", 
            int(projected_usage)
        )
    
    async def track_api_usage(self, tenant_id: str, endpoint: str) -> bool:
        """Track API usage and check limits"""
        try:
            # Check current API usage
            limit_check = await self.check_usage_limit(tenant_id, "api_calls_per_month")
            
            if not limit_check["within_limit"]:
                logger.warning(f"API limit exceeded for tenant {tenant_id}")
                return False
            
            # Send usage event to Lago
            await self._send_usage_to_lago(tenant_id, "api_call", {
                "endpoint": endpoint,
                "tenant_id": tenant_id
            })
            
            # Update local usage tracking
            await self._increment_usage_counter(tenant_id, "api_calls_this_month", 1)
            
            return True
            
        except Exception as e:
            logger.error(f"Error tracking API usage: {e}")
            return True  # Allow usage on error, log for investigation
    
    async def upgrade_tenant_plan(
        self, 
        tenant_id: str, 
        new_plan: SubscriptionPlan,
        admin_user_id: str
    ) -> Dict[str, Any]:
        """Upgrade tenant to a new subscription plan"""
        try:
            tenant = await self.tenant_service.get_tenant_by_id(tenant_id)
            if not tenant:
                raise ValueError("Tenant not found")
            
            old_plan = SubscriptionPlan(tenant.subscription_plan)
            
            # Update tenant plan in database
            result = self.tenants_collection.update_one(
                {"_id": tenant_id},
                {
                    "$set": {
                        "subscription_plan": new_plan.value,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            )
            
            if result.matched_count == 0:
                raise ValueError("Failed to update tenant plan")
            
            # Update Lago subscription
            lago_customer_id = tenant.billing_info.get("lago_customer_id")
            if lago_customer_id:
                new_plan_code = self.plan_configs[new_plan]["lago_plan_code"]
                await self.lago_service.update_subscription(
                    customer_id=lago_customer_id,
                    plan_code=new_plan_code
                )
            
            # Audit log
            await self.tenant_service.audit_service.log_event(
                "tenant_plan_upgraded",
                user_id=admin_user_id,
                tenant_id=tenant_id,
                details={
                    "old_plan": old_plan.value,
                    "new_plan": new_plan.value
                }
            )
            
            return {
                "message": f"Plan upgraded to {new_plan.value}",
                "old_plan": old_plan.value,
                "new_plan": new_plan.value,
                "new_features": [f.value for f in self.plan_configs[new_plan]["features"]],
                "new_limits": self.plan_configs[new_plan]["limits"].__dict__
            }
            
        except Exception as e:
            logger.error(f"Error upgrading tenant plan: {e}")
            raise
    
    async def get_plan_comparison(self) -> Dict[str, Any]:
        """Get comparison of all available plans"""
        comparison = {}
        
        for plan, config in self.plan_configs.items():
            comparison[plan.value] = {
                "features": [f.value for f in config["features"]],
                "limits": config["limits"].__dict__,
                "lago_plan_code": config["lago_plan_code"]
            }
        
        return comparison
    
    async def get_tenant_usage_dashboard(self, tenant_id: str) -> Dict[str, Any]:
        """Get comprehensive usage dashboard for tenant"""
        try:
            tenant = await self.tenant_service.get_tenant_by_id(tenant_id)
            if not tenant:
                raise ValueError("Tenant not found")
            
            plan = SubscriptionPlan(tenant.subscription_plan)
            limits = self.plan_configs[plan]["limits"]
            usage_data = await self._get_current_usage(tenant_id)
            
            # Calculate usage percentages
            usage_stats = {}
            
            for limit_field in ["max_users", "max_admins", "storage_gb", "api_calls_per_month"]:
                limit_value = getattr(limits, limit_field)
                current_value = getattr(usage_data, limit_field.replace("max_", "current_").replace("_per_month", "_this_month"))
                
                if limit_value is None:
                    usage_stats[limit_field] = {
                        "current": current_value,
                        "limit": "unlimited",
                        "percentage": 0,
                        "status": "unlimited"
                    }
                else:
                    percentage = (current_value / limit_value) * 100
                    status = "danger" if percentage >= 90 else ("warning" if percentage >= 75 else "good")
                    
                    usage_stats[limit_field] = {
                        "current": current_value,
                        "limit": limit_value,
                        "percentage": percentage,
                        "status": status,
                        "remaining": limit_value - current_value
                    }
            
            # Get feature status
            features_status = {}
            for feature in FeatureFlag:
                features_status[feature.value] = await self.check_feature_access(tenant_id, feature)
            
            return {
                "tenant_id": tenant_id,
                "plan": plan.value,
                "usage_stats": usage_stats,
                "features": features_status,
                "support_level": limits.support_level,
                "last_updated": usage_data.last_updated.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting usage dashboard: {e}")
            raise
    
    # Private methods
    async def _get_current_usage(self, tenant_id: str) -> UsageData:
        """Get current usage data for tenant"""
        # This would query your usage tracking collection
        # and aggregate current usage across all metrics
        
        # Get user counts from tenant_users
        tenant_users = self.tenant_service.tenant_users_collection
        current_users = tenant_users.count_documents({
            "tenant_id": tenant_id,
            "status": "active"
        })
        
        current_admins = tenant_users.count_documents({
            "tenant_id": tenant_id,
            "status": "active",
            "role": {"$in": ["admin", "owner"]}
        })
        
        # Get usage stats from usage collection
        usage_doc = self.usage_collection.find_one({"tenant_id": tenant_id}) or {}
        
        return UsageData(
            current_users=current_users,
            current_admins=current_admins,
            storage_used_gb=usage_doc.get("storage_used_gb", 0.0),
            api_calls_this_month=usage_doc.get("api_calls_this_month", 0),
            integrations_count=usage_doc.get("integrations_count", 0),
            last_updated=datetime.utcnow()
        )
    
    async def _send_usage_to_lago(self, tenant_id: str, event_code: str, properties: Dict):
        """Send usage event to Lago for billing"""
        try:
            tenant = await self.tenant_service.get_tenant_by_id(tenant_id)
            lago_customer_id = tenant.billing_info.get("lago_customer_id")
            
            if lago_customer_id:
                await self.lago_service.send_usage_event(
                    customer_external_id=tenant_id,
                    event_code=event_code,
                    properties=properties
                )
        except Exception as e:
            logger.error(f"Failed to send usage to Lago: {e}")
    
    async def _increment_usage_counter(self, tenant_id: str, counter: str, amount: int):
        """Increment usage counter in database"""
        self.usage_collection.update_one(
            {"tenant_id": tenant_id},
            {
                "$inc": {counter: amount},
                "$set": {"last_updated": datetime.utcnow()}
            },
            upsert=True
        )