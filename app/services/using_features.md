# Enhanced API with feature management

from services.feature_service import FeatureService, FeatureFlag, SubscriptionPlan

# Dependency to check feature access

async def require_feature(
feature: FeatureFlag,
tenant_context: str = Depends(get_tenant_context),
feature_service: FeatureService = Depends(get_feature_service)
):
"""Dependency to require specific feature access"""
if not tenant_context:
raise HTTPException(status_code=400, detail="Tenant context required")

    has_access = await feature_service.check_feature_access(tenant_context, feature)
    if not has_access:
        raise HTTPException(
            status_code=403,
            detail=f"Feature '{feature.value}' not available in your subscription plan"
        )

    return True

# Middleware to track API usage

@app.middleware("http")
async def api_usage_middleware(request: Request, call_next):
"""Track API usage for billing and limits"""

    # Skip for health checks and public endpoints
    if request.url.path in ["/health", "/docs", "/openapi.json"]:
        return await call_next(request)

    tenant_id = getattr(request.state, 'tenant_id', None)

    if tenant_id:
        feature_service = request.app.state.feature_service

        # Check API rate limits
        can_use_api = await feature_service.track_api_usage(
            tenant_id,
            request.url.path
        )

        if not can_use_api:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "API usage limit exceeded for your subscription plan",
                    "upgrade_url": "/pricing"
                }
            )

    return await call_next(request)

# Feature-gated endpoints

@app.post("/auth/sso/configure")
async def configure*sso(
sso_config: Dict[str, Any],
current_user: Dict = Depends(get_current_user),
tenant_context: str = Depends(get_tenant_context),
*: bool = Depends(lambda: require_feature(FeatureFlag.SSO_ENABLED)),
feature_service: FeatureService = Depends(get_feature_service)
):
"""Configure SSO (Professional+ only)""" # SSO configuration logic here
return {"message": "SSO configured successfully"}

@app.post("/auth/tenants/{tenant_id}/users")
async def add_user_to_tenant(
tenant_id: str,
user_data: Dict[str, Any],
current_user: Dict = Depends(get_current_user),
feature_service: FeatureService = Depends(get_feature_service)
):
"""Add user to tenant with limit checking"""

    # Check if tenant can add more users
    limit_check = await feature_service.can_add_user(tenant_id)

    if not limit_check["within_limit"]:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "User limit exceeded",
                "current_users": limit_check["current_usage"],
                "max_users": limit_check["limit"],
                "upgrade_required": True
            }
        )

    # Proceed with adding user
    # ... user creation logic

    return {"message": "User added successfully"}

@app.get("/auth/usage-dashboard")
async def get_usage_dashboard(
current_user: Dict = Depends(get_current_user),
tenant_context: str = Depends(get_tenant_context),
feature_service: FeatureService = Depends(get_feature_service)
):
"""Get tenant usage dashboard"""
if not tenant_context:
raise HTTPException(status_code=400, detail="Tenant context required")

    dashboard = await feature_service.get_tenant_usage_dashboard(tenant_context)
    return dashboard

@app.post("/auth/upgrade-plan")
async def upgrade_subscription_plan(
new_plan: str,
current_user: Dict = Depends(get_current_user),
tenant_context: str = Depends(get_tenant_context),
feature_service: FeatureService = Depends(get_feature_service)
):
"""Upgrade tenant subscription plan"""
if not tenant_context:
raise HTTPException(status_code=400, detail="Tenant context required")

    try:
        plan_enum = SubscriptionPlan(new_plan)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid subscription plan")

    result = await feature_service.upgrade_tenant_plan(
        tenant_id=tenant_context,
        new_plan=plan_enum,
        admin_user_id=current_user["user_id"]
    )

    return result

@app.get("/pricing/plans")
async def get_pricing_plans(
feature_service: FeatureService = Depends(get_feature_service)
):
"""Get all available subscription plans (public endpoint)"""
plans = await feature_service.get_plan_comparison()
return {"plans": plans}

# Webhook from Lago for subscription updates

@app.post("/webhooks/lago/subscription-updated")
async def lago_subscription_webhook(
request: Request,
feature_service: FeatureService = Depends(get_feature_service)
):
"""Handle Lago subscription update webhooks"""
try:
payload = await request.json()

        # Verify webhook signature (implement based on Lago docs)
        # ...

        # Extract subscription data
        customer_id = payload.get("customer", {}).get("external_id")
        new_plan_code = payload.get("plan", {}).get("code")

        # Map Lago plan code to our subscription plan
        plan_mapping = {
            "trial_plan": SubscriptionPlan.TRIAL,
            "basic_plan": SubscriptionPlan.BASIC,
            "professional_plan": SubscriptionPlan.PROFESSIONAL,
            "enterprise_plan": SubscriptionPlan.ENTERPRISE
        }

        if customer_id and new_plan_code in plan_mapping:
            # Update tenant subscription plan
            new_plan = plan_mapping[new_plan_code]

            # Update in database
            tenants_collection = feature_service.tenants_collection
            result = tenants_collection.update_one(
                {"_id": customer_id},
                {
                    "$set": {
                        "subscription_plan": new_plan.value,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                }
            )

            if result.matched_count > 0:
                logger.info(f"Updated tenant {customer_id} to plan {new_plan.value}")

        return {"status": "processed"}

    except Exception as e:
        logger.error(f"Error processing Lago webhook: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

# Usage example in frontend

@app.get("/auth/features")
async def get_available_features(
current_user: Dict = Depends(get_current_user),
tenant_context: str = Depends(get_tenant_context),
feature_service: FeatureService = Depends(get_feature_service)
):
"""Get available features for current tenant (for frontend)"""
if not tenant_context:
raise HTTPException(status_code=400, detail="Tenant context required")

    features = {}
    for feature in FeatureFlag:
        features[feature.value] = await feature_service.check_feature_access(
            tenant_context,
            feature
        )

    return {"features": features}
