from fastapi import APIRouter, Body, HTTPException
from typing import Dict, Any
from services import lago_billing  # wrapper around Lago API

router = APIRouter(prefix="/billing", tags=["billing"])


# --------------------------
# Customers
# --------------------------
@router.post("/customers")
def create_customer(external_id: str, email: str, name: str, currency: str = "USD"):
    return lago_billing.create_customer(external_id, email, name, currency)

@router.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    return lago_billing.get_customer(customer_id)

@router.put("/customers/{customer_id}")
def update_customer(customer_id: str, updates: Dict[str, Any] = Body(...)):
    return lago_billing.update_customer(customer_id, updates)


# --------------------------
# Subscriptions
# --------------------------
@router.post("/subscriptions")
def create_subscription(customer_id: str, plan_code: str):
    return lago_billing.create_subscription(customer_id, plan_code)

@router.get("/subscriptions/{subscription_id}")
def get_subscription(subscription_id: str):
    return lago_billing.get_subscription(subscription_id)

@router.delete("/subscriptions/{subscription_id}")
def cancel_subscription(subscription_id: str):
    return lago_billing.cancel_subscription(subscription_id)


# --------------------------
# Invoices
# --------------------------
@router.get("/customers/{customer_id}/invoices")
def get_invoices(customer_id: str):
    return lago_billing.get_invoices(customer_id)

@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str):
    return lago_billing.get_invoice(invoice_id)


# --------------------------
# Usage / Events
# --------------------------
@router.post("/events")
def record_event(customer_id: str, code: str, properties: Dict[str, Any] = Body(...)):
    return lago_billing.record_event(customer_id, code, properties)


# --------------------------
# Plans & Catalog
# --------------------------
@router.get("/plans")
def get_plans():
    return lago_billing.get_plans()

@router.get("/plans/{plan_code}")
def get_plan(plan_code: str):
    return lago_billing.get_plan(plan_code)


# --------------------------
# Wallets & Credits
# --------------------------
@router.post("/customers/{customer_id}/wallets")
def create_wallet(customer_id: str, name: str, currency: str = "USD"):
    return lago_billing.create_wallet(customer_id, name, currency)

@router.post("/wallets/{wallet_id}/transactions")
def wallet_transaction(wallet_id: str, amount: float, transaction_type: str = "credit"):
    return lago_billing.wallet_transaction(wallet_id, amount, transaction_type)


# --------------------------
# Payments (via Lago integrations)
# --------------------------
@router.get("/customers/{customer_id}/payments")
def get_payments(customer_id: str):
    return lago_billing.get_payments(customer_id)


# --------------------------
# Admin & Health
# --------------------------
@router.get("/health")
def get_health():
    return {"status": "ok", "lago": lago_billing.get_health()}
