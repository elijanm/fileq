import os
import requests
from typing import Optional, Dict, List, Any
from datetime import datetime
import uuid

# Configuration
LAGO_API_URL = os.getenv("LAGO_API_URL", "http://95.110.228.29:8724")
LAGO_API_KEY = os.getenv("LAGO_API_KEY", "d9b8238c-5e13-48fa-b92d-584573044be5")
LAGO_ADMIN_API_KEY = os.getenv("LAGO_ADMIN_API_KEY","d9b8238c-5e13-48fa-b92d-584573044be5")

HEADERS = {"Authorization": f"Bearer {LAGO_API_KEY}", "Content-Type": "application/json"}
ADMIN_HEADERS = {"Authorization": f"Bearer {LAGO_ADMIN_API_KEY}", "Content-Type": "application/json"}


def update_organization_email_settings(org_api_key, email_config):
    """Update organization email settings"""
    headers = {"Authorization": f"Bearer {org_api_key}"}
    payload = {
        "organization": {
            "email": email_config.get("from_email"),
            "webhook_url": email_config.get("webhook_url")
        }
    }
    # Organization-specific email settings
    return update_organization(**payload)

# ==============================================================================
# CUSTOMERS
# ==============================================================================

def create_customer(external_id: str, email: str, name: str, currency="USD", **kwargs):
    """Create a new customer"""
    payload = {
        "customer": {
            "external_id": external_id,
            "email": email,
            "name": name,
            "currency": currency,
            **kwargs
        }
    }
    print(payload)
    r = requests.post(f"{LAGO_API_URL}/api/v1/customers", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_customer(external_id: str):
    """Get customer by external ID"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/customers/{external_id}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def list_customers(page: int = 1, per_page: int = 20):
    """List all customers"""
    params = {"page": page, "per_page": per_page}
    r = requests.get(f"{LAGO_API_URL}/api/v1/customers", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def update_customer(external_id: str, **kwargs):
    """Update customer"""
    payload = {"customer": kwargs}
    r = requests.put(f"{LAGO_API_URL}/api/v1/customers/{external_id}", json=payload, headers=HEADERS)
    # r.raise_for_status()
    return r.json()


def delete_customer(external_id: str):
    """Delete customer"""
    r = requests.delete(f"{LAGO_API_URL}/api/v1/customers/{external_id}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# SUBSCRIPTIONS
# ==============================================================================

def create_subscription(external_customer_id: str, plan_code: str, **kwargs):
    """Create a new subscription"""
    payload = {
        "subscription": {
            "external_customer_id": external_customer_id,
            "plan_code": plan_code,
            **kwargs
        }
    }
    print(payload)
    r = requests.post(f"{LAGO_API_URL}/api/v1/subscriptions", json=payload, headers=HEADERS)
    # r.raise_for_status()
    if r.status_code != 201 and r.status_code != 200:  # Lago returns 201 on success for subscription creation
      raise Exception(f"Lago error {r.status_code}: {r.text}")
    return r.json()


def get_subscription(external_id: str):
    """Get subscription by external ID"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/subscriptions/{external_id}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def list_subscriptions(page: int = 1, per_page: int = 20, external_customer_id: str = None):
    """List subscriptions"""
    params = {"page": page, "per_page": per_page}
    if external_customer_id:
        params["external_customer_id"] = external_customer_id
    r = requests.get(f"{LAGO_API_URL}/api/v1/subscriptions", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def update_subscription(external_id: str, **kwargs):
    """Update subscription"""
    payload = {"subscription": kwargs}
    r = requests.put(f"{LAGO_API_URL}/api/v1/subscriptions/{external_id}", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def terminate_subscription(external_id: str):
    """Terminate subscription"""
    r = requests.delete(f"{LAGO_API_URL}/api/v1/subscriptions/{external_id}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# PLANS
# ==============================================================================

def create_plan(name: str, code: str, interval: str, amount_cents: int,minimum_commitment:dict, currency: str = "USD", **kwargs):
    """Create a new plan"""
    payload = {
        "plan": {
            "name": name,
            "code": code,
            "interval": interval,
            "minimum_commitment":minimum_commitment,
            "amount_cents": amount_cents,
            "currency": currency,
            **kwargs
        }
    }
    
    r = requests.post(f"{LAGO_API_URL}/api/v1/plans", json=payload, headers=HEADERS)
 
    r.raise_for_status()
    return r.json()


def get_plan(code: str):
    """Get plan by code"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/plans/{code}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def list_plans(page: int = 1, per_page: int = 20):
    """List all plans"""
    params = {"page": page, "per_page": per_page}
    r = requests.get(f"{LAGO_API_URL}/api/v1/plans", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def update_plan(code: str, **kwargs):
    """Update plan"""
    payload = {"plan": kwargs}
    r = requests.put(f"{LAGO_API_URL}/api/v1/plans/{code}", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def delete_plan(code: str):
    """Delete plan"""
    r = requests.delete(f"{LAGO_API_URL}/api/v1/plans/{code}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# BILLABLE METRICS
# ==============================================================================

def create_billable_metric(name: str, code: str, aggregation_type: str, **kwargs):
    """Create a billable metric"""
    payload = {
        "billable_metric": {
            "name": name,
            "code": code,
            "aggregation_type": aggregation_type,
            **kwargs
        }
    }
    r = requests.post(f"{LAGO_API_URL}/api/v1/billable_metrics", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_billable_metric(code: str):
    """Get billable metric by code"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/billable_metrics/{code}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def list_billable_metrics(page: int = 1, per_page: int = 20):
    """List billable metrics"""
    params = {"page": page, "per_page": per_page}
    r = requests.get(f"{LAGO_API_URL}/api/v1/billable_metrics", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def update_billable_metric(code: str, **kwargs):
    """Update billable metric"""
    payload = {"billable_metric": kwargs}
    r = requests.put(f"{LAGO_API_URL}/api/v1/billable_metrics/{code}", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def delete_billable_metric(code: str):
    """Delete billable metric"""
    r = requests.delete(f"{LAGO_API_URL}/api/v1/billable_metrics/{code}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# EVENTS
# ==============================================================================

def record_usage(external_customer_id: str, code: str, properties: dict, transaction_id: str = None, timestamp: str = None):
    """Record usage event"""
    if not transaction_id:
        transaction_id = str(uuid.uuid4())
    
    payload = {
        "event": {
            "external_subscription_id":"2cbd2635-e185-4ad7-bbde-a575b2af5cb6",
            "transaction_id": transaction_id,
            "external_customer_id": external_customer_id,
            "lago_customer_id":"b0dbc475-176f-4436-9d36-3caf63dff84b",
            "code": code,
            "properties": properties,
        }
    }
    
    if timestamp:
        payload["event"]["timestamp"] = timestamp
    print(payload,HEADERS)
    print("**"*20)
        
    r = requests.post(f"{LAGO_API_URL}/api/v1/events", json=payload, headers=HEADERS)
    # r.raise_for_status()
    if r.status_code != 201 and r.status_code != 200:  # Lago returns 201 on success for subscription creation
      raise Exception(f"Lago wallet error {r.status_code}: {r.text}")
    return r.json()


def get_event(transaction_id: str):
    """Get event by transaction ID"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/events/{transaction_id}", headers=HEADERS)
    r.raise_for_status()
    return r.json()
# ==============================================================================
# Quota
# ==============================================================================

def check_quota(customer_id: str):
    """Check if customer exceeded any plan allowances"""
    # 1. Get customer subscriptions (to know plan_code)
    resp = requests.get(f"{LAGO_API_URL}/api/v1/subscriptions?external_customer_id={customer_id}", headers=HEADERS)
    resp.raise_for_status()
    subs = resp.json()["subscriptions"]
    if not subs:
        return {"error": "No active subscriptions"}
    
    plan_code = subs[0]["plan_code"]
    plan = get_plan(plan_code)

    # 2. Get usage for this customer
    ext=subs[0]['external_id']
    print(ext)
    resp = requests.get(f"{LAGO_API_URL}/api/v1/customers/{customer_id}/current_usage?external_subscription_id={ext}", headers=HEADERS)
    resp.raise_for_status()
 
    usage = resp.json()["customer_usage"]["charges_usage"]

    # 3. Compare usage vs plan charges
    results = {}
    plan_charges = plan["plan"]["charges"]
    
    for metric in usage:
        code = metric["billable_metric"]["code"]     # e.g. "cloud_storage_bytes"
        used = float(metric["units"])                # string → float

        # Find matching plan charge
        charge = next((c for c in plan_charges if c["billable_metric_code"] == code), None)

        if charge:
            free = 0

            # Handle volume model
            if charge["charge_model"] == "volume":
                ranges = charge["properties"].get("volume_ranges", [])
                for r in ranges:
                    if float(r["per_unit_amount"]) == 0 and r["from_value"] == 0:
                        free = float(r["to_value"] or 0)

            # Handle graduated model
            elif charge["charge_model"] == "graduated":
                ranges = charge["properties"].get("graduated_ranges", [])
                for r in ranges:
                    if float(r["per_unit_amount"]) == 0 and r["from_value"] == 0:
                        free = float(r["to_value"] or 0)

            over = max(0, used - free)

            results[code] = {
                "used": used,
                "free": free,
                "over": over,
                "exceeded": used > free,
            }

        else:
            results[code] = {
                "used": used,
                "free": 0,
                "over": used,
                "exceeded": True,
            }

    return results
# ==============================================================================
# INVOICES
# ==============================================================================

def create_invoice(external_customer_id: str, **kwargs):
    """Create invoice"""
    payload = {
        "invoice": {
            "external_customer_id": external_customer_id,
            **kwargs
        }
    }
    r = requests.post(f"{LAGO_API_URL}/api/v1/invoices", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_invoice(lago_id: str):
    """Get invoice by Lago ID"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/invoices/{lago_id}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def list_invoices(page: int = 1, per_page: int = 20, external_customer_id: str = None):
    """List invoices"""
    params = {"page": page, "per_page": per_page}
    if external_customer_id:
        params["external_customer_id"] = external_customer_id
    r = requests.get(f"{LAGO_API_URL}/api/v1/invoices", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def finalize_invoice(lago_id: str):
    """Finalize invoice"""
    r = requests.put(f"{LAGO_API_URL}/api/v1/invoices/{lago_id}/finalize", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def download_invoice(lago_id: str):
    """Download invoice PDF"""
    r = requests.post(f"{LAGO_API_URL}/api/v1/invoices/{lago_id}/download", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def void_invoice(lago_id: str):
    """Void invoice"""
    r = requests.post(f"{LAGO_API_URL}/api/v1/invoices/{lago_id}/void", headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# COUPONS
# ==============================================================================

def create_coupon(name: str, code: str, coupon_type: str, **kwargs):
    """Create coupon"""
    payload = {
        "coupon": {
            "name": name,
            "code": code,
            "coupon_type": coupon_type,
            **kwargs
        }
    }
    r = requests.post(f"{LAGO_API_URL}/api/v1/coupons", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_coupon(code: str):
    """Get coupon by code"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/coupons/{code}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def list_coupons(page: int = 1, per_page: int = 20):
    """List coupons"""
    params = {"page": page, "per_page": per_page}
    r = requests.get(f"{LAGO_API_URL}/api/v1/coupons", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def update_coupon(code: str, **kwargs):
    """Update coupon"""
    payload = {"coupon": kwargs}
    r = requests.put(f"{LAGO_API_URL}/api/v1/coupons/{code}", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def delete_coupon(code: str):
    """Delete coupon"""
    r = requests.delete(f"{LAGO_API_URL}/api/v1/coupons/{code}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def apply_coupon(external_customer_id: str, coupon_code: str, **kwargs):
    """Apply coupon to customer"""
    payload = {
        "applied_coupon": {
            "external_customer_id": external_customer_id,
            "coupon_code": coupon_code,
            **kwargs
        }
    }
    r = requests.post(f"{LAGO_API_URL}/api/v1/applied_coupons", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# ADD-ONS
# ==============================================================================

def create_add_on(name: str, code: str, amount_cents: int, currency: str = "USD", **kwargs):
    """Create add-on"""
    payload = {
        "add_on": {
            "name": name,
            "code": code,
            "amount_cents": amount_cents,
            "currency": currency,
            **kwargs
        }
    }
    r = requests.post(f"{LAGO_API_URL}/api/v1/add_ons", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_add_on(code: str):
    """Get add-on by code"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/add_ons/{code}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def list_add_ons(page: int = 1, per_page: int = 20):
    """List add-ons"""
    params = {"page": page, "per_page": per_page}
    r = requests.get(f"{LAGO_API_URL}/api/v1/add_ons", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def update_add_on(code: str, **kwargs):
    """Update add-on"""
    payload = {"add_on": kwargs}
    r = requests.put(f"{LAGO_API_URL}/api/v1/add_ons/{code}", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def delete_add_on(code: str):
    """Delete add-on"""
    r = requests.delete(f"{LAGO_API_URL}/api/v1/add_ons/{code}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def apply_add_on(external_customer_id: str, add_on_code: str, **kwargs):
    """Apply add-on to customer"""
    payload = {
        "applied_add_on": {
            "external_customer_id": external_customer_id,
            "add_on_code": add_on_code,
            **kwargs
        }
    }
    r = requests.post(f"{LAGO_API_URL}/api/v1/applied_add_ons", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# CREDIT NOTES
# ==============================================================================

def create_credit_note(invoice_id: str, reason: str, **kwargs):
    """Create credit note"""
    payload = {
        "credit_note": {
            "invoice_id": invoice_id,
            "reason": reason,
            **kwargs
        }
    }
    r = requests.post(f"{LAGO_API_URL}/api/v1/credit_notes", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_credit_note(lago_id: str):
    """Get credit note by Lago ID"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/credit_notes/{lago_id}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def list_credit_notes(page: int = 1, per_page: int = 20, external_customer_id: str = None):
    """List credit notes"""
    params = {"page": page, "per_page": per_page}
    if external_customer_id:
        params["external_customer_id"] = external_customer_id
    r = requests.get(f"{LAGO_API_URL}/api/v1/credit_notes", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def void_credit_note(lago_id: str):
    """Void credit note"""
    r = requests.put(f"{LAGO_API_URL}/api/v1/credit_notes/{lago_id}/void", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def download_credit_note(lago_id: str):
    """Download credit note PDF"""
    r = requests.post(f"{LAGO_API_URL}/api/v1/credit_notes/{lago_id}/download", headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# WALLETS & WALLET TRANSACTIONS
# ==============================================================================

def create_wallet(external_customer_id: str, currency: str = "USD", **kwargs):
    """Create wallet for customer"""
    payload = {
        "wallet": {
            "external_customer_id": external_customer_id,
            "currency": currency,
            **kwargs
        }
    }
    r = requests.post(f"{LAGO_API_URL}/api/v1/wallets", json=payload, headers=HEADERS)
    # r.raise_for_status()
    if r.status_code != 201 and r.status_code != 200:  # Lago returns 201 on success for subscription creation
      raise Exception(f"Lago wallet error {r.status_code}: {r.text}")
    return r.json()


def get_wallet(lago_id: str):
    """Get wallet by Lago ID"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/wallets/{lago_id}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def list_wallets(external_customer_id: str, page: int = 1, per_page: int = 20):
    """List customer wallets"""
    params = {
        "external_customer_id": external_customer_id,
        "page": page,
        "per_page": per_page
    }
    r = requests.get(f"{LAGO_API_URL}/api/v1/wallets", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def update_wallet(lago_id: str, **kwargs):
    """Update wallet"""
    payload = {"wallet": kwargs}
    r = requests.put(f"{LAGO_API_URL}/api/v1/wallets/{lago_id}", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def terminate_wallet(lago_id: str):
    """Terminate wallet"""
    r = requests.delete(f"{LAGO_API_URL}/api/v1/wallets/{lago_id}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def create_wallet_transaction(wallet_id: str, amount: str, transaction_type: str, **kwargs):
    """Create wallet transaction"""
    payload = {
        "wallet_transaction": {
            "wallet_id": wallet_id,
            "amount": amount,
            "transaction_type": transaction_type,
            **kwargs
        }
    }
    r = requests.post(f"{LAGO_API_URL}/api/v1/wallet_transactions", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def list_wallet_transactions(wallet_id: str, page: int = 1, per_page: int = 20):
    """List wallet transactions"""
    params = {
        "wallet_id": wallet_id,
        "page": page,
        "per_page": per_page
    }
    r = requests.get(f"{LAGO_API_URL}/api/v1/wallet_transactions", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# TAXES
# ==============================================================================

def create_tax(name: str, code: str, rate: float, **kwargs):
    """Create tax"""
    payload = {
        "tax": {
            "name": name,
            "code": code,
            "rate": rate,
            **kwargs
        }
    }
    r = requests.post(f"{LAGO_API_URL}/api/v1/taxes", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_tax(code: str):
    """Get tax by code"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/taxes/{code}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def list_taxes(page: int = 1, per_page: int = 20):
    """List taxes"""
    params = {"page": page, "per_page": per_page}
    r = requests.get(f"{LAGO_API_URL}/api/v1/taxes", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def update_tax(code: str, **kwargs):
    """Update tax"""
    payload = {"tax": kwargs}
    r = requests.put(f"{LAGO_API_URL}/api/v1/taxes/{code}", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def delete_tax(code: str):
    """Delete tax"""
    r = requests.delete(f"{LAGO_API_URL}/api/v1/taxes/{code}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# ORGANIZATIONS (TENANTS)
# ==============================================================================

def create_organization_initial_setup(name: str, email: str, **kwargs):
    """Create initial organization during setup (no API key required)"""
    payload = {
        "organization": {
            "name": name,
            "email": email,
            **kwargs
        }
    }
    # No authorization header needed for initial setup
    r = requests.post(f"{LAGO_API_URL}/api/v1/organizations", json=payload)
    r.raise_for_status()
    return r.json()


def create_tenant(name: str, email: str, webhook_url: str = None, api_key_override: str = None):
    """Create additional organization/tenant (requires existing org API key)"""
    payload = {
        "organization": {
            "name": name,
            "email": email,
            "webhook_url": webhook_url
        }
    }
    
    # If specific API key provided for new org, use it
    if api_key_override:
        payload["organization"]["api_key"] = api_key_override
    
    r = requests.post(f"{LAGO_API_URL}/api/v1/organizations", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()


def get_organization():
    """Get current organization"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/organizations/current", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def update_organization(**kwargs):
    """Update organization"""
    payload = {"organization": kwargs}
    r = requests.put(f"{LAGO_API_URL}/api/v1/organizations", json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# WEBHOOKS
# ==============================================================================

def list_webhooks(page: int = 1, per_page: int = 20):
    """List webhooks"""
    params = {"page": page, "per_page": per_page}
    r = requests.get(f"{LAGO_API_URL}/api/v1/webhooks", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_webhook(lago_id: str):
    """Get webhook by Lago ID"""
    r = requests.get(f"{LAGO_API_URL}/api/v1/webhooks/{lago_id}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


# ==============================================================================
# ANALYTICS
# ==============================================================================

def get_gross_revenue(currency: str = None):
    """Get gross revenue analytics"""
    params = {}
    if currency:
        params["currency"] = currency
    r = requests.get(f"{LAGO_API_URL}/api/v1/analytics/gross_revenue", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_invoiced_usage(currency: str = None):
    """Get invoiced usage analytics"""
    params = {}
    if currency:
        params["currency"] = currency
    r = requests.get(f"{LAGO_API_URL}/api/v1/analytics/invoiced_usage", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def get_mrr(currency: str = None):
    """Get Monthly Recurring Revenue analytics"""
    params = {}
    if currency:
        params["currency"] = currency
    r = requests.get(f"{LAGO_API_URL}/api/v1/analytics/mrr", params=params, headers=HEADERS)
    r.raise_for_status()
    return r.json()




# ==============================================================================
# UTILS
# ==============================================================================

def health_check():
    """Health check endpoint"""
    r = requests.get(f"{LAGO_API_URL}/health")
    r.raise_for_status()
    return r.json()