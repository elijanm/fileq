import os
import requests
from typing import Dict, Any, Optional, List

# ---------------------------------------------------
# Config
# ---------------------------------------------------
KILLBILL_URL = os.getenv("KILLBILL_URL", "http://localhost:8081")
TENANT_API_KEY = os.getenv("KILLBILL_API_KEY", "admin")
TENANT_API_SECRET = os.getenv("KILLBILL_API_SECRET", "password")

DEFAULT_HEADERS = {
    "X-Killbill-ApiKey": TENANT_API_KEY,
    "X-Killbill-ApiSecret": TENANT_API_SECRET,
    "Accept": "application/json"
}

# ---------------------------------------------------
# Helpers
# ---------------------------------------------------

def _headers(created_by: Optional[str] = None,
             reason: Optional[str] = None,
             comment: Optional[str] = None,
             accept: str = "application/json",
             content_type: str = "application/json") -> Dict[str, str]:
    h = DEFAULT_HEADERS.copy()
    if created_by:
        h["X-Killbill-CreatedBy"] = created_by
    if reason:
        h["X-Killbill-Reason"] = reason
    if comment:
        h["X-Killbill-Comment"] = comment
    h["Accept"] = accept
    h["Content-Type"] = content_type
    return h

def _params(plugin_properties: Optional[Dict[str, Any]] = None,
            pagination: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = {}
    if plugin_properties:
        params.update({f"pluginProperty": [f"{k}={v}" for k, v in plugin_properties.items()]})
    if pagination:
        params.update(pagination)
    return params

# ---------------------------------------------------
# Tenants
# ---------------------------------------------------

def get_tenant(api_key: str, api_secret: str):
    r = requests.get(
        f"{KILLBILL_URL}/1.0/kb/tenants",
        headers={
            "X-Killbill-ApiKey": api_key,
            "X-Killbill-ApiSecret": api_secret,
            "Accept": "application/json"
        }
    )
    r.raise_for_status()
    return r.json()

def create_tenant(api_key: str, api_secret: str, created_by="system"):
    payload = {
        "apiKey": api_key,
        "apiSecret": api_secret
    }
    r = requests.post(
        f"{KILLBILL_URL}/1.0/kb/tenants",
        json=payload,
        headers=_headers(created_by=created_by)
    )
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------
# Accounts
# ---------------------------------------------------
def create_account(name: str, email: str, currency="USD", created_by="system",
                   tenant_api_key: Optional[str] = None,
                   tenant_api_secret: Optional[str] = None):
    payload = {"name": name, "externalKey": email, "email": email, "currency": currency}

    headers = {
        "X-Killbill-ApiKey": tenant_api_key or TENANT_API_KEY,
        "X-Killbill-ApiSecret": tenant_api_secret or TENANT_API_SECRET,
        "X-Killbill-CreatedBy": created_by,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    r = requests.post(f"{KILLBILL_URL}/1.0/kb/accounts", json=payload, headers=headers)
    r.raise_for_status()
    return r.json()

# def create_account(name: str, email: str, currency="USD", created_by="system"):
#     payload = {"name": name, "externalKey": email, "email": email, "currency": currency}
#     r = requests.post(f"{KILLBILL_URL}/1.0/kb/accounts", json=payload, headers=_headers(created_by=created_by))
#     r.raise_for_status()
#     return r.json()

def get_account(account_id: str):
    r = requests.get(f"{KILLBILL_URL}/1.0/kb/accounts/{account_id}", headers=_headers())
    r.raise_for_status()
    return r.json()

def update_account(account_id: str, updates: Dict[str, Any], created_by="system"):
    r = requests.put(f"{KILLBILL_URL}/1.0/kb/accounts/{account_id}", json=updates, headers=_headers(created_by=created_by))
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------
# Payment Methods
# ---------------------------------------------------

def add_payment_method(account_id: str, plugin_name: str, is_default=True,
                       plugin_info: Optional[Dict] = None, created_by="system"):
    payload = {
        "accountId": account_id,
        "pluginName": plugin_name,
        "isDefault": is_default,
        "pluginInfo": plugin_info or {}
    }
    r = requests.post(
        f"{KILLBILL_URL}/1.0/kb/accounts/{account_id}/paymentMethods",
        json=payload, headers=_headers(created_by=created_by)
    )
    r.raise_for_status()
    return r.json()

def list_payment_methods(account_id: str, pagination: Dict[str, Any] = None):
    r = requests.get(
        f"{KILLBILL_URL}/1.0/kb/accounts/{account_id}/paymentMethods",
        headers=_headers(),
        params=_params(pagination=pagination)
    )
    r.raise_for_status()
    return {"items": r.json(), "pagination": _extract_pagination(r)}

def delete_payment_method(account_id: str, payment_method_id: str, created_by="system"):
    r = requests.delete(
        f"{KILLBILL_URL}/1.0/kb/accounts/{account_id}/paymentMethods/{payment_method_id}",
        headers=_headers(created_by=created_by)
    )
    r.raise_for_status()
    return {"deleted": True}

# ---------------------------------------------------
# Subscriptions / Bundles
# ---------------------------------------------------

def create_subscription(account_id: str, plan_name: str,
                        product_category="BASE", created_by="system"):
    payload = {"accountId": account_id, "planName": plan_name, "productCategory": product_category}
    r = requests.post(f"{KILLBILL_URL}/1.0/kb/subscriptions", json=payload, headers=_headers(created_by=created_by))
    r.raise_for_status()
    return r.json()

def get_subscription(subscription_id: str):
    r = requests.get(f"{KILLBILL_URL}/1.0/kb/subscriptions/{subscription_id}", headers=_headers())
    r.raise_for_status()
    return r.json()

def cancel_subscription(subscription_id: str, requested_date="IMMEDIATE", created_by="system"):
    r = requests.delete(
        f"{KILLBILL_URL}/1.0/kb/subscriptions/{subscription_id}?requestedDate={requested_date}",
        headers=_headers(created_by=created_by)
    )
    r.raise_for_status()
    return {"canceled": True}

# ---------------------------------------------------
# Invoices & Credits
# ---------------------------------------------------

def get_invoices(account_id: str, pagination: Dict[str, Any] = None):
    r = requests.get(f"{KILLBILL_URL}/1.0/kb/accounts/{account_id}/invoices",
                     headers=_headers(), params=_params(pagination=pagination))
    r.raise_for_status()
    return {"items": r.json(), "pagination": _extract_pagination(r)}

def get_invoice(invoice_id: str):
    r = requests.get(f"{KILLBILL_URL}/1.0/kb/invoices/{invoice_id}", headers=_headers())
    r.raise_for_status()
    return r.json()

def create_credit(account_id: str, amount: float, currency="USD", created_by="system"):
    payload = {"accountId": account_id, "creditAmount": amount, "currency": currency}
    r = requests.post(f"{KILLBILL_URL}/1.0/kb/credits", json=payload, headers=_headers(created_by=created_by))
    r.raise_for_status()
    return r.json()

def adjust_invoice_item(invoice_id: str, item_id: str, amount: float, created_by="system"):
    payload = {"invoiceId": invoice_id, "invoiceItemId": item_id, "amount": amount}
    r = requests.post(f"{KILLBILL_URL}/1.0/kb/invoices/{invoice_id}/adjustments",
                      json=payload, headers=_headers(created_by=created_by))
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------
# Payments
# ---------------------------------------------------

def get_payments(account_id: str, pagination: Dict[str, Any] = None):
    r = requests.get(
        f"{KILLBILL_URL}/1.0/kb/accounts/{account_id}/payments",
        headers=_headers(), params=_params(pagination=pagination)
    )
    r.raise_for_status()
    return {"items": r.json(), "pagination": _extract_pagination(r)}

def refund_payment(payment_id: str, amount: float, created_by="system"):
    payload = {"amount": amount}
    r = requests.post(f"{KILLBILL_URL}/1.0/kb/payments/{payment_id}/refunds",
                      json=payload, headers=_headers(created_by=created_by))
    r.raise_for_status()
    return r.json()

def capture_payment(payment_id: str, amount: Optional[float] = None, created_by="system"):
    payload = {"amount": amount} if amount else {}
    r = requests.post(f"{KILLBILL_URL}/1.0/kb/payments/{payment_id}/captures",
                      json=payload, headers=_headers(created_by=created_by))
    r.raise_for_status()
    return r.json()

def void_payment(payment_id: str, created_by="system"):
    r = requests.post(f"{KILLBILL_URL}/1.0/kb/payments/{payment_id}/voids",
                      headers=_headers(created_by=created_by))
    r.raise_for_status()
    return {"voided": True}

def chargeback_payment(payment_id: str, amount: float, created_by="system"):
    payload = {"amount": amount}
    r = requests.post(f"{KILLBILL_URL}/1.0/kb/payments/{payment_id}/chargebacks",
                      json=payload, headers=_headers(created_by=created_by))
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------
# Catalog (XML)
# ---------------------------------------------------

def get_catalog():
    r = requests.get(f"{KILLBILL_URL}/1.0/kb/catalog", headers=_headers(accept="application/xml"))
    r.raise_for_status()
    return r.text  # XML

def upload_catalog(catalog_xml: str, created_by="system"):
    r = requests.post(f"{KILLBILL_URL}/1.0/kb/catalog/xml",
                      data=catalog_xml, headers=_headers(created_by=created_by, content_type="application/xml"))
    r.raise_for_status()
    return {"uploaded": True}

# ---------------------------------------------------
# Tags & Custom Fields
# ---------------------------------------------------

def add_tag(resource: str, resource_id: str, tag_definition_id: str, created_by="system"):
    r = requests.post(
        f"{KILLBILL_URL}/1.0/kb/{resource}/{resource_id}/tags?tagDef={tag_definition_id}",
        headers=_headers(created_by=created_by)
    )
    r.raise_for_status()
    return {"tagged": True}

def get_tags(resource: str, resource_id: str):
    r = requests.get(f"{KILLBILL_URL}/1.0/kb/{resource}/{resource_id}/tags", headers=_headers())
    r.raise_for_status()
    return r.json()

def add_custom_field(resource: str, resource_id: str, field_name: str, field_value: str, created_by="system"):
    payload = [{"name": field_name, "value": field_value}]
    r = requests.post(f"{KILLBILL_URL}/1.0/kb/{resource}/{resource_id}/customFields",
                      json=payload, headers=_headers(created_by=created_by))
    r.raise_for_status()
    return r.json()

def get_custom_fields(resource: str, resource_id: str):
    r = requests.get(f"{KILLBILL_URL}/1.0/kb/{resource}/{resource_id}/customFields", headers=_headers())
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------
# Overdue
# ---------------------------------------------------

def get_overdue_config():
    r = requests.get(f"{KILLBILL_URL}/1.0/kb/overdue", headers=_headers(accept="application/xml"))
    r.raise_for_status()
    return r.text

# ---------------------------------------------------
# Admin / Diagnostics
# ---------------------------------------------------

def get_nodes_info():
    r = requests.get(f"{KILLBILL_URL}/1.0/kb/nodesInfo", headers=_headers())
    r.raise_for_status()
    return r.json()

def get_health():
    r = requests.get(f"{KILLBILL_URL}/1.0/kb/healthcheck", headers=_headers())
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------
# Helpers
# ---------------------------------------------------

def _extract_pagination(resp: requests.Response) -> Dict[str, Any]:
    return {
        "current_offset": resp.headers.get("X-Killbill-Pagination-CurrentOffset"),
        "max_nb_records": resp.headers.get("X-Killbill-Pagination-MaxNbRecords"),
        "next_offset": resp.headers.get("X-Killbill-Pagination-NextOffset"),
    }
