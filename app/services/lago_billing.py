from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import time
from pymongo.database import Database
from fastapi import Depends, HTTPException
from bson import ObjectId
from utils.db import get_database
from metrics.metrics import get_metrics
import logging
import uuid

# Import your existing Lago API functions
from services.lago_api import *  # Import all your Lago functions
from services import lago_api
logger = logging.getLogger(__name__)

class LagoBillingService:
    """Enhanced Lago billing service integrated with multi-tenant auth system"""
    
    def __init__(self, db: Database, metrics_collector):
        self.db = db
        self.metrics = metrics_collector
        self.tenants = db.tenants
        self.users = db.users
        self.audit_logs = db.audit_logs
        
        # Cache for tenant API keys
        self._api_key_cache = {}
    def __getattr__(self, name):
        """
        Called only if the attribute `name` is not found normally.
        Priority:
        1. Real attribute/method on the instance (handled by Python before this is called).
        2. If not found, check `utils` module.
        """
        if hasattr(lago_api, name):
            func = getattr(lago_api, name)
            if callable(func):
                # Return bound function that injects self.value
                return lambda *args, **kwargs: func(*args, **kwargs)
            return func

        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    async def health_check_billing(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Check billing system health"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                health = self.health_check()
                return {
                    "status": "healthy",
                    "tenant_id": tenant_id,
                    "lago_status": health
                }
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                    
        except Exception as e:
            return {
                "status": "unhealthy",
                "tenant_id": tenant_id,
                "error": str(e)
            }
    
    # =====================================
    # WEBHOOK MANAGEMENT
    # =====================================
    
    async def list_webhooks(self, tenant_id: str, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """List webhooks for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return list_webhooks(page=page, per_page=per_page)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to list webhooks for tenant {tenant_id}: {str(e)}")
            return {"webhooks": []}
    
    async def get_webhook(self, tenant_id: str, lago_id: str) -> Dict[str, Any]:
        """Get webhook by Lago ID"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_webhook(lago_id)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get webhook {lago_id}: {str(e)}")
            raise HTTPException(status_code=404, detail="Webhook not found")
    
    # =====================================
    # ADD-ON MANAGEMENT
    # =====================================
    
    async def create_add_on(
        self,
        tenant_id: str,
        name: str,
        code: str,
        amount_cents: int,
        currency: str = "USD",
        created_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create add-on for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                add_on = create_add_on(
                    name=name,
                    code=code,
                    amount_cents=amount_cents,
                    currency=currency,
                    **kwargs
                )
                
                await self._log_audit_event(
                    "add_on_created",
                    created_by,
                    tenant_id,
                    {"add_on_code": code, "name": name, "amount_cents": amount_cents}
                )
                
                return add_on
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to create add-on for tenant {tenant_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Add-on creation failed")
    
    async def get_add_on(self, tenant_id: str, code: str) -> Dict[str, Any]:
        """Get add-on by code"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_add_on(code)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get add-on {code}: {str(e)}")
            raise HTTPException(status_code=404, detail="Add-on not found")
    
    async def list_add_ons(self, tenant_id: str, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """List add-ons for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return list_add_ons(page=page, per_page=per_page)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to list add-ons for tenant {tenant_id}: {str(e)}")
            return {"add_ons": []}
    
    async def update_add_on(
        self, 
        tenant_id: str, 
        code: str,
        updated_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Update add-on"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                add_on = update_add_on(code, **kwargs)
                
                await self._log_audit_event(
                    "add_on_updated",
                    updated_by,
                    tenant_id,
                    {"add_on_code": code, "updates": kwargs}
                )
                
                return add_on
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to update add-on {code}: {str(e)}")
            raise HTTPException(status_code=500, detail="Add-on update failed")
    
    async def delete_add_on(
        self, 
        tenant_id: str, 
        code: str,
        deleted_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete add-on"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = delete_add_on(code)
                
                await self._log_audit_event(
                    "add_on_deleted",
                    deleted_by,
                    tenant_id,
                    {"add_on_code": code}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to delete add-on {code}: {str(e)}")
            raise HTTPException(status_code=500, detail="Add-on deletion failed")
    
    async def apply_add_on_to_user(
        self,
        user_id: str,
        add_on_code: str,
        tenant_id: Optional[str] = None,
        applied_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Apply add-on to user"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = apply_add_on(
                    external_customer_id=user_id,
                    add_on_code=add_on_code,
                    **kwargs
                )
                
                await self._log_audit_event(
                    "add_on_applied",
                    applied_by or user_id,
                    tenant_id,
                    {
                        "target_user_id": user_id,
                        "add_on_code": add_on_code
                    }
                )
                
                return result
                
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                    
        except Exception as e:
            logger.error(f"Failed to apply add-on {add_on_code} to user {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Add-on application failed")
    
    # =====================================
    # COUPON MANAGEMENT (EXTENDED)
    # =====================================
    
    async def create_coupon(
        self,
        tenant_id: str,
        name: str,
        code: str,
        coupon_type: str,
        created_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create coupon for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                coupon = create_coupon(
                    name=name,
                    code=code,
                    coupon_type=coupon_type,
                    **kwargs
                )
                
                await self._log_audit_event(
                    "coupon_created",
                    created_by,
                    tenant_id,
                    {"coupon_code": code, "name": name, "type": coupon_type}
                )
                
                return coupon
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to create coupon for tenant {tenant_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Coupon creation failed")
    
    async def get_coupon(self, tenant_id: str, code: str) -> Dict[str, Any]:
        """Get coupon by code"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_coupon(code)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get coupon {code}: {str(e)}")
            raise HTTPException(status_code=404, detail="Coupon not found")
    
    async def list_coupons(self, tenant_id: str, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """List coupons for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return list_coupons(page=page, per_page=per_page)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to list coupons for tenant {tenant_id}: {str(e)}")
            return {"coupons": []}
    
    async def update_coupon(
        self, 
        tenant_id: str, 
        code: str,
        updated_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Update coupon"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                coupon = update_coupon(code, **kwargs)
                
                await self._log_audit_event(
                    "coupon_updated",
                    updated_by,
                    tenant_id,
                    {"coupon_code": code, "updates": kwargs}
                )
                
                return coupon
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to update coupon {code}: {str(e)}")
            raise HTTPException(status_code=500, detail="Coupon update failed")
    
    async def delete_coupon(
        self, 
        tenant_id: str, 
        code: str,
        deleted_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete coupon"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = delete_coupon(code)
                
                await self._log_audit_event(
                    "coupon_deleted",
                    deleted_by,
                    tenant_id,
                    {"coupon_code": code}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to delete coupon {code}: {str(e)}")
            raise HTTPException(status_code=500, detail="Coupon deletion failed")
    
    # =====================================
    # CREDIT NOTES MANAGEMENT
    # =====================================
    
    async def create_credit_note(
        self,
        tenant_id: str,
        invoice_id: str,
        reason: str,
        created_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create credit note"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                credit_note = create_credit_note(
                    invoice_id=invoice_id,
                    reason=reason,
                    **kwargs
                )
                
                await self._log_audit_event(
                    "credit_note_created",
                    created_by,
                    tenant_id,
                    {"invoice_id": invoice_id, "reason": reason}
                )
                
                return credit_note
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to create credit note for invoice {invoice_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Credit note creation failed")
    
    async def get_credit_note(self, tenant_id: str, lago_id: str) -> Dict[str, Any]:
        """Get credit note by Lago ID"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_credit_note(lago_id)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get credit note {lago_id}: {str(e)}")
            raise HTTPException(status_code=404, detail="Credit note not found")
    
    async def list_credit_notes(
        self, 
        tenant_id: str, 
        page: int = 1, 
        per_page: int = 20,
        external_customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List credit notes for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return list_credit_notes(
                    page=page, 
                    per_page=per_page,
                    external_customer_id=external_customer_id
                )
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to list credit notes for tenant {tenant_id}: {str(e)}")
            return {"credit_notes": []}
    
    async def void_credit_note(
        self, 
        tenant_id: str, 
        lago_id: str,
        voided_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Void credit note"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = void_credit_note(lago_id)
                
                await self._log_audit_event(
                    "credit_note_voided",
                    voided_by,
                    tenant_id,
                    {"credit_note_id": lago_id}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to void credit note {lago_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Credit note void failed")
    
    async def download_credit_note(
        self, 
        tenant_id: str, 
        lago_id: str,
        downloaded_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Download credit note PDF"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = download_credit_note(lago_id)
                
                await self._log_audit_event(
                    "credit_note_downloaded",
                    downloaded_by,
                    tenant_id,
                    {"credit_note_id": lago_id}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to download credit note {lago_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Credit note download failed")
    
    # =====================================
    # TAX MANAGEMENT
    # =====================================
    
    async def create_tax(
        self,
        tenant_id: str,
        name: str,
        code: str,
        rate: float,
        created_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create tax for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                tax = create_tax(
                    name=name,
                    code=code,
                    rate=rate,
                    **kwargs
                )
                
                await self._log_audit_event(
                    "tax_created",
                    created_by,
                    tenant_id,
                    {"tax_code": code, "name": name, "rate": rate}
                )
                
                return tax
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to create tax for tenant {tenant_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Tax creation failed")
    
    async def get_tax(self, tenant_id: str, code: str) -> Dict[str, Any]:
        """Get tax by code"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_tax(code)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get tax {code}: {str(e)}")
            raise HTTPException(status_code=404, detail="Tax not found")
    
    async def list_taxes(self, tenant_id: str, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """List taxes for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return list_taxes(page=page, per_page=per_page)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to list taxes for tenant {tenant_id}: {str(e)}")
            return {"taxes": []}
    
    async def update_tax(
        self, 
        tenant_id: str, 
        code: str,
        updated_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Update tax"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                tax = update_tax(code, **kwargs)
                
                await self._log_audit_event(
                    "tax_updated",
                    updated_by,
                    tenant_id,
                    {"tax_code": code, "updates": kwargs}
                )
                
                return tax
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to update tax {code}: {str(e)}")
            raise HTTPException(status_code=500, detail="Tax update failed")
    
    async def delete_tax(
        self, 
        tenant_id: str, 
        code: str,
        deleted_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete tax"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = delete_tax(code)
                
                await self._log_audit_event(
                    "tax_deleted",
                    deleted_by,
                    tenant_id,
                    {"tax_code": code}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to delete tax {code}: {str(e)}")
            raise HTTPException(status_code=500, detail="Tax deletion failed")
    
    # =====================================
    # ADVANCED INVOICE MANAGEMENT
    # =====================================
    
    async def create_invoice(
        self,
        tenant_id: str,
        external_customer_id: str,
        created_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create invoice"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                invoice = create_invoice(
                    external_customer_id=external_customer_id,
                    **kwargs
                )
                
                await self._log_audit_event(
                    "invoice_created",
                    created_by,
                    tenant_id,
                    {"customer_id": external_customer_id}
                )
                
                return invoice
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to create invoice for customer {external_customer_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Invoice creation failed")
    
    async def get_invoice(self, tenant_id: str, lago_id: str) -> Dict[str, Any]:
        """Get invoice by Lago ID"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_invoice(lago_id)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get invoice {lago_id}: {str(e)}")
            raise HTTPException(status_code=404, detail="Invoice not found")
    
    async def list_invoices(
        self, 
        tenant_id: str, 
        page: int = 1, 
        per_page: int = 20,
        external_customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List invoices for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return list_invoices(
                    page=page, 
                    per_page=per_page,
                    external_customer_id=external_customer_id
                )
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to list invoices for tenant {tenant_id}: {str(e)}")
            return {"invoices": []}
    
    async def finalize_invoice(
        self, 
        tenant_id: str, 
        lago_id: str,
        finalized_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Finalize invoice"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = finalize_invoice(lago_id)
                
                await self._log_audit_event(
                    "invoice_finalized",
                    finalized_by,
                    tenant_id,
                    {"invoice_id": lago_id}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to finalize invoice {lago_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Invoice finalization failed")
    
    async def void_invoice(
        self, 
        tenant_id: str, 
        lago_id: str,
        voided_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Void invoice"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = void_invoice(lago_id)
                
                await self._log_audit_event(
                    "invoice_voided",
                    voided_by,
                    tenant_id,
                    {"invoice_id": lago_id}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to void invoice {lago_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Invoice void failed")
    
    # =====================================
    # WALLET TRANSACTIONS
    # =====================================
    
    async def create_wallet_transaction(
        self,
        tenant_id: str,
        wallet_id: str,
        amount: str,
        transaction_type: str,
        created_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create wallet transaction"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                transaction = create_wallet_transaction(
                    wallet_id=wallet_id,
                    amount=amount,
                    transaction_type=transaction_type,
                    **kwargs
                )
                
                await self._log_audit_event(
                    "wallet_transaction_created",
                    created_by,
                    tenant_id,
                    {
                        "wallet_id": wallet_id,
                        "amount": amount,
                        "transaction_type": transaction_type
                    }
                )
                
                return transaction
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to create wallet transaction: {str(e)}")
            raise HTTPException(status_code=500, detail="Wallet transaction creation failed")
    
    async def list_wallet_transactions(
        self, 
        tenant_id: str, 
        wallet_id: str, 
        page: int = 1, 
        per_page: int = 20
    ) -> Dict[str, Any]:
        """List wallet transactions"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return list_wallet_transactions(
                    wallet_id=wallet_id,
                    page=page,
                    per_page=per_page
                )
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to list wallet transactions for wallet {wallet_id}: {str(e)}")
            return {"wallet_transactions": []}
    
    async def update_wallet(
        self, 
        tenant_id: str, 
        lago_id: str,
        updated_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Update wallet"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                wallet = update_wallet(lago_id, **kwargs)
                
                await self._log_audit_event(
                    "wallet_updated",
                    updated_by,
                    tenant_id,
                    {"wallet_id": lago_id, "updates": kwargs}
                )
                
                return wallet
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to update wallet {lago_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Wallet update failed")
    
    async def terminate_wallet(
        self, 
        tenant_id: str, 
        lago_id: str,
        terminated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Terminate wallet"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = terminate_wallet(lago_id)
                
                await self._log_audit_event(
                    "wallet_terminated",
                    terminated_by,
                    tenant_id,
                    {"wallet_id": lago_id}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to terminate wallet {lago_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Wallet termination failed")
    
    # =====================================
    # ORGANIZATION MANAGEMENT
    # =====================================
    
    async def get_organization(self, tenant_id: str) -> Dict[str, Any]:
        """Get current organization for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_organization()
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get organization for tenant {tenant_id}: {str(e)}")
            raise HTTPException(status_code=404, detail="Organization not found")
    
    async def update_organization(
        self, 
        tenant_id: str,
        updated_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Update organization"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                org = update_organization(**kwargs)
                
                await self._log_audit_event(
                    "organization_updated",
                    updated_by,
                    tenant_id,
                    {"updates": kwargs}
                )
                
                return org
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to update organization for tenant {tenant_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Organization update failed")# lago_billing_service.py - Integrated Lago billing service with multi-tenant support


    
    # =====================================
    # TENANT & ORGANIZATION MANAGEMENT
    # =====================================
    
    async def setup_tenant_billing(
        self, 
        tenant_id: str, 
        organization_name: str,
        admin_email: str,
        webhook_url: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set up billing for a new tenant"""
        try:
            # Get tenant info
            tenant = self.tenants.find_one({"_id": ObjectId(tenant_id)})
            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")
            
            # Check if billing already set up
            if tenant.get("billing_info", {}).get("lago_customer_id"):
                raise HTTPException(status_code=400, detail="Billing already configured")
            
            # Create organization in Lago
            lago_org = create_tenant(
                name=organization_name,
                email=admin_email,
                webhook_url=webhook_url
            )
            
            # Store Lago organization info in tenant
            billing_info = {
                "lago_customer_id": lago_org.get("organization", {}).get("lago_id"),
                "lago_api_key": lago_org.get("organization", {}).get("api_key"),
                "billing_email": admin_email,
                "webhook_url": webhook_url,
                "setup_date": datetime.now(timezone.utc).isoformat(),
                "setup_by": created_by
            }
            
            # Update tenant with billing info
            self.tenants.update_one(
                {"_id": ObjectId(tenant_id)},
                {
                    "$set": {
                        "billing_info": billing_info,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            
            # Cache the API key
            self._api_key_cache[tenant_id] = billing_info["lago_api_key"]
            
            # Log audit event
            await self._log_audit_event(
                "billing_setup",
                created_by,
                tenant_id,
                {
                    "organization_name": organization_name,
                    "lago_customer_id": billing_info["lago_customer_id"]
                }
            )
            
            return {
                "tenant_id": tenant_id,
                "lago_customer_id": billing_info["lago_customer_id"],
                "status": "billing_configured"
            }
            
        except Exception as e:
            logger.error(f"Failed to setup billing for tenant {tenant_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Billing setup failed")
    
    def _get_tenant_api_key(self, tenant_id: str) -> str:
        """Get API key for tenant (with caching)"""
        # Check cache first
        if tenant_id in self._api_key_cache:
            return self._api_key_cache[tenant_id]
        
        # Get from database
        tenant = self.tenants.find_one({"_id": ObjectId(tenant_id)})
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        api_key = tenant.get("billing_info", {}).get("lago_api_key")
        if not api_key:
            raise HTTPException(status_code=400, detail="Billing not configured for tenant")
        
        # Cache it
        self._api_key_cache[tenant_id] = api_key
        return api_key
    
    # =====================================
    # CUSTOMER MANAGEMENT
    # =====================================
    
    async def create_customer_for_user(
        self, 
        user_id: str, 
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a Lago customer for a user"""
        try:
            # Get user info
            user = self.users.find_one({"kratos_id": user_id})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Use tenant-specific API key if provided
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                # Temporarily override global API key
                global LAGO_API_KEY
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                global HEADERS
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                # Create customer in Lago
                lago_customer = create_customer(
                    external_id=user_id,
                    email=user["email"],
                    name=user.get("name", ""),
                    currency="USD"
                )
                
                # Update user with Lago customer ID
                self.users.update_one(
                    {"kratos_id": user_id},
                    {
                        "$set": {
                            "lago_customer_id": lago_customer["customer"]["lago_id"],
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
                
                # Log audit event
                await self._log_audit_event(
                    "customer_created",
                    user_id,
                    tenant_id,
                    {
                        "lago_customer_id": lago_customer["customer"]["lago_id"],
                        "email": user["email"]
                    }
                )
                
                return lago_customer
                
            finally:
                # Restore original API key
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
            
        except Exception as e:
            logger.error(f"Failed to create customer for user {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Customer creation failed")
    
    async def get_customer_info(
        self, 
        user_id: str, 
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get customer information from Lago"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                customer = get_customer(user_id)
                return customer
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                    
        except Exception as e:
            logger.error(f"Failed to get customer info for user {user_id}: {str(e)}")
            raise HTTPException(status_code=404, detail="Customer not found")
    
    # =====================================
    # SUBSCRIPTION MANAGEMENT
    # =====================================
    
    async def create_user_subscription(
        self,
        user_id: str,
        plan_code: str,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create subscription for user"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                # Ensure customer exists
                try:
                    await self.get_customer_info(user_id, tenant_id)
                except HTTPException:
                    # Create customer if doesn't exist
                    await self.create_customer_for_user(user_id, tenant_id)
                
                # Create subscription
                subscription = create_subscription(
                    external_customer_id=user_id,
                    plan_code=plan_code,
                    **kwargs
                )
                
                # Log audit event
                await self._log_audit_event(
                    "subscription_created",
                    user_id,
                    tenant_id,
                    {
                        "plan_code": plan_code,
                        "subscription_id": subscription.get("subscription", {}).get("lago_id")
                    }
                )
                
                return subscription
                
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                    
        except Exception as e:
            logger.error(f"Failed to create subscription for user {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Subscription creation failed")
    
    async def get_user_subscriptions(
        self, 
        user_id: str, 
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get all subscriptions for a user"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                subscriptions = list_subscriptions(external_customer_id=user_id)
                return subscriptions
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                    
        except Exception as e:
            logger.error(f"Failed to get subscriptions for user {user_id}: {str(e)}")
            return {"subscriptions": []}
    
    # =====================================
    # USAGE TRACKING
    # =====================================
    
    async def track_usage(
        self,
        user_id: str,
        metric_code: str,
        properties: Dict[str, Any],
        tenant_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """Track usage event for billing"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                if not transaction_id:
                    transaction_id = str(uuid.uuid4())
                
                if not timestamp:
                    timestamp =int(time.time())
                
                # Record usage event
                event = record_usage(
                    external_customer_id=user_id,
                    code=metric_code,
                    properties=properties,
                    transaction_id=transaction_id,
                    timestamp=timestamp
                )
                
                # Log for audit
                await self._log_audit_event(
                    "usage_tracked",
                    user_id,
                    tenant_id,
                    {
                        "metric_code": metric_code,
                        "transaction_id": transaction_id,
                        "properties": properties
                    }
                )
                
                return event
                
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                    
        except Exception as e:
            logger.error(f"Failed to track usage for user {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Usage tracking failed")
    
    # =====================================
    # PLAN MANAGEMENT
    # =====================================
    
    async def create_tenant_plan(
        self,
        tenant_id: str,
        name: str,
        code: str,
        interval: str,
        amount_cents: int,
        currency: str = "USD",
        created_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a plan for a specific tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                plan = create_plan(
                    name=name,
                    code=code,
                    interval=interval,
                    amount_cents=amount_cents,
                    currency=currency,
                    minimum_commitment={},  # Add based on your needs
                    **kwargs
                )
                
                # Log audit event
                await self._log_audit_event(
                    "plan_created",
                    created_by,
                    tenant_id,
                    {
                        "plan_code": code,
                        "plan_name": name,
                        "amount_cents": amount_cents
                    }
                )
                
                return plan
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to create plan for tenant {tenant_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Plan creation failed")
    
    async def get_tenant_plans(self, tenant_id: str) -> Dict[str, Any]:
        """Get all plans for a tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                plans = list_plans()
                return plans
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get plans for tenant {tenant_id}: {str(e)}")
            return {"plans": []}
    
    # =====================================
    # INVOICE MANAGEMENT
    # =====================================
    
    async def get_user_invoices(
        self, 
        user_id: str, 
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get invoices for a user"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                invoices = list_invoices(external_customer_id=user_id)
                return invoices
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                    
        except Exception as e:
            logger.error(f"Failed to get invoices for user {user_id}: {str(e)}")
            return {"invoices": []}
    
    async def download_user_invoice(
        self, 
        invoice_id: str, 
        user_id: str,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Download invoice for user"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                download_result = download_invoice(invoice_id)
                
                # Log audit event
                await self._log_audit_event(
                    "invoice_downloaded",
                    user_id,
                    tenant_id,
                    {"invoice_id": invoice_id}
                )
                
                return download_result
                
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                    
        except Exception as e:
            logger.error(f"Failed to download invoice {invoice_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Invoice download failed")
    
    # =====================================
    # ANALYTICS & REPORTING
    # =====================================
    
    async def get_tenant_revenue_analytics(
        self, 
        tenant_id: str, 
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """Get revenue analytics for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                analytics = {
                    "gross_revenue": get_gross_revenue(currency),
                    "mrr": get_mrr(currency),
                    "invoiced_usage": get_invoiced_usage(currency)
                }
                return analytics
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get analytics for tenant {tenant_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Analytics retrieval failed")
    
    # =====================================
    # COUPON & ADD-ON MANAGEMENT
    # =====================================
    
    async def apply_coupon_to_user(
        self,
        user_id: str,
        coupon_code: str,
        tenant_id: Optional[str] = None,
        applied_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Apply coupon to user"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = apply_coupon(
                    external_customer_id=user_id,
                    coupon_code=coupon_code
                )
                
                # Log audit event
                await self._log_audit_event(
                    "coupon_applied",
                    applied_by or user_id,
                    tenant_id,
                    {
                        "target_user_id": user_id,
                        "coupon_code": coupon_code
                    }
                )
                
                return result
                
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                    
        except Exception as e:
            logger.error(f"Failed to apply coupon {coupon_code} to user {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Coupon application failed")
    
    # =====================================
    # BILLABLE METRICS
    # =====================================
    
    async def create_billable_metric(
        self,
        name: str,
        code: str,
        aggregation_type: str,
        tenant_id: str=None,
        created_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a billable metric for tenant"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                metric = create_billable_metric(
                    name=name,
                    code=code,
                    aggregation_type=aggregation_type,
                    **kwargs
                )
                
                await self._log_audit_event(
                    "billable_metric_created",
                    created_by,
                    tenant_id,
                    {"metric_code": code, "name": name, "aggregation_type": aggregation_type}
                )
                
                return metric
                
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to create billable metric for tenant {tenant_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Billable metric creation failed")
    
    async def get_billable_metric(self, tenant_id: str, code: str) -> Dict[str, Any]:
        """Get billable metric by code"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_billable_metric(code)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get billable metric {code}: {str(e)}")
            raise HTTPException(status_code=404, detail="Billable metric not found")
    
    async def list_billable_metrics(self, tenant_id: str, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """List billable metrics for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return list_billable_metrics(page=page, per_page=per_page)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to list billable metrics for tenant {tenant_id}: {str(e)}")
            return {"billable_metrics": []}
    
    async def update_billable_metric(
        self, 
        tenant_id: str, 
        code: str, 
        updated_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Update billable metric"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                metric = update_billable_metric(code, **kwargs)
                
                await self._log_audit_event(
                    "billable_metric_updated",
                    updated_by,
                    tenant_id,
                    {"metric_code": code, "updates": kwargs}
                )
                
                return metric
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to update billable metric {code}: {str(e)}")
            raise HTTPException(status_code=500, detail="Billable metric update failed")
    
    async def delete_billable_metric(
        self, 
        tenant_id: str, 
        code: str, 
        deleted_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete billable metric"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = delete_billable_metric(code)
                
                await self._log_audit_event(
                    "billable_metric_deleted",
                    deleted_by,
                    tenant_id,
                    {"metric_code": code}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to delete billable metric {code}: {str(e)}")
            raise HTTPException(status_code=500, detail="Billable metric deletion failed")
    
    # =====================================
    # ADVANCED SUBSCRIPTION MANAGEMENT
    # =====================================
    
    async def list_subscriptions(
        self, 
        tenant_id: str, 
        page: int = 1, 
        per_page: int = 20,
        external_customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all subscriptions for tenant"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return list_subscriptions(
                    page=page, 
                    per_page=per_page,
                    external_customer_id=external_customer_id
                )
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                    
        except Exception as e:
            logger.error(f"Failed to list subscriptions for tenant {tenant_id}: {str(e)}")
            return {"subscriptions": []}
    
    async def get_subscription(self, tenant_id: str, external_id: str) -> Dict[str, Any]:
        """Get subscription by external ID"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_subscription(external_id)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get subscription {external_id}: {str(e)}")
            raise HTTPException(status_code=404, detail="Subscription not found")
    
    async def update_subscription(
        self, 
        tenant_id: str, 
        external_id: str,
        updated_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Update subscription"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                subscription = update_subscription(external_id, **kwargs)
                
                await self._log_audit_event(
                    "subscription_updated",
                    updated_by,
                    tenant_id,
                    {"subscription_id": external_id, "updates": kwargs}
                )
                
                return subscription
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to update subscription {external_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Subscription update failed")
    
    async def terminate_subscription(
        self, 
        tenant_id: str, 
        external_id: str,
        terminated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Terminate subscription"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = terminate_subscription(external_id)
                
                await self._log_audit_event(
                    "subscription_terminated",
                    terminated_by,
                    tenant_id,
                    {"subscription_id": external_id}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to terminate subscription {external_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Subscription termination failed")
    
    # =====================================
    # ADVANCED CUSTOMER MANAGEMENT
    # =====================================
    
    async def list_customers(self, tenant_id: str, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """List all customers for tenant"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return list_customers(page=page, per_page=per_page)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to list customers for tenant {tenant_id}: {str(e)}")
            return {"customers": []}
    
    async def update_customer(
        self, 
        tenant_id: str, 
        external_id: str,
        updated_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Update customer"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                customer = update_customer(external_id, **kwargs)
                
                await self._log_audit_event(
                    "customer_updated",
                    updated_by,
                    tenant_id,
                    {"customer_id": external_id, "updates": kwargs}
                )
                
                return customer
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to update customer {external_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Customer update failed")
    
    async def delete_customer(
        self, 
        tenant_id: str, 
        external_id: str,
        deleted_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete customer"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = delete_customer(external_id)
                
                await self._log_audit_event(
                    "customer_deleted",
                    deleted_by,
                    tenant_id,
                    {"customer_id": external_id}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to delete customer {external_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Customer deletion failed")
    
    # =====================================
    # PLAN MANAGEMENT (EXTENDED)
    # =====================================
    
    async def get_plan(self, tenant_id: str, code: str) -> Dict[str, Any]:
        """Get plan by code"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_plan(code)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get plan {code}: {str(e)}")
            raise HTTPException(status_code=404, detail="Plan not found")
    
    async def update_plan(
        self, 
        tenant_id: str, 
        code: str,
        updated_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Update plan"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                plan = update_plan(code, **kwargs)
                
                await self._log_audit_event(
                    "plan_updated",
                    updated_by,
                    tenant_id,
                    {"plan_code": code, "updates": kwargs}
                )
                
                return plan
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to update plan {code}: {str(e)}")
            raise HTTPException(status_code=500, detail="Plan update failed")
    
    async def delete_plan(
        self, 
        tenant_id: str, 
        code: str,
        deleted_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete plan"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                result = delete_plan(code)
                
                await self._log_audit_event(
                    "plan_deleted",
                    deleted_by,
                    tenant_id,
                    {"plan_code": code}
                )
                
                return result
                
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to delete plan {code}: {str(e)}")
            raise HTTPException(status_code=500, detail="Plan deletion failed")
    
    # =====================================
    # EVENTS & USAGE
    # =====================================
    
    async def get_event(self, tenant_id: str, transaction_id: str) -> Dict[str, Any]:
        """Get event by transaction ID"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_event(transaction_id)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get event {transaction_id}: {str(e)}")
            raise HTTPException(status_code=404, detail="Event not found")
    
    # =====================================
    # WALLET MANAGEMENT
    # =====================================
    
    async def create_wallet(
        self, 
        
        external_customer_id: str, 
        currency: str = "USD",
        tenant_id:Optional[str] = None,
        created_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create wallet for customer"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                wallet = create_wallet(
                    external_customer_id=external_customer_id,
                    currency=currency,
                    **kwargs
                )
                
                await self._log_audit_event(
                    "wallet_created",
                    created_by,
                    tenant_id,
                    {"customer_id": external_customer_id, "currency": currency}
                )
                
                return wallet
                
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to create wallet for customer {external_customer_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Wallet creation failed")
    
    async def get_wallet(self, tenant_id: str, lago_id: str) -> Dict[str, Any]:
        """Get wallet by Lago ID"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return get_wallet(lago_id)
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to get wallet {lago_id}: {str(e)}")
            raise HTTPException(status_code=404, detail="Wallet not found")
    
    async def list_wallets(
        self, 
        tenant_id: str, 
        external_customer_id: str, 
        page: int = 1, 
        per_page: int = 20
    ) -> Dict[str, Any]:
        """List customer wallets"""
        try:
            api_key = self._get_tenant_api_key(tenant_id)
            global LAGO_API_KEY, HEADERS
            original_key = LAGO_API_KEY
            LAGO_API_KEY = api_key
            HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                return list_wallets(
                    external_customer_id=external_customer_id,
                    page=page,
                    per_page=per_page
                )
            finally:
                LAGO_API_KEY = original_key
                HEADERS["Authorization"] = f"Bearer {original_key}"
                
        except Exception as e:
            logger.error(f"Failed to list wallets for customer {external_customer_id}: {str(e)}")
            return {"wallets": []}
    
    # =====================================
    # UTILITY METHODS
    # =====================================
    def  health_check(self):
        return health_check()
    async def health_check_billing(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Check billing system health"""
        try:
            if tenant_id:
                api_key = self._get_tenant_api_key(tenant_id)
                global LAGO_API_KEY, HEADERS
                original_key = LAGO_API_KEY
                LAGO_API_KEY = api_key
                HEADERS["Authorization"] = f"Bearer {api_key}"
            
            try:
                health = health_check()
                return {
                    "status": "healthy",
                    "tenant_id": tenant_id,
                    "lago_status": health
                }
            finally:
                if tenant_id:
                    LAGO_API_KEY = original_key
                    HEADERS["Authorization"] = f"Bearer {original_key}"
                    
        except Exception as e:
            return {
                "status": "unhealthy",
                "tenant_id": tenant_id,
                "error": str(e)
            }
    
    async def sync_tenant_billing_data(self, tenant_id: str) -> Dict[str, Any]:
        """Sync billing data for tenant"""
        try:
            # Get tenant info
            tenant = self.tenants.find_one({"_id": ObjectId(tenant_id)})
            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")
            
            # Get all tenant users
            tenant_users = self.db.tenant_users.find({
                "tenant_id": ObjectId(tenant_id),
                "status": "active"
            })
            
            sync_results = []
            
            for tenant_user in tenant_users:
                user_id = tenant_user["user_id"]
                try:
                    # Sync customer data
                    customer_info = await self.get_customer_info(user_id, tenant_id)
                    subscriptions = await self.get_user_subscriptions(user_id, tenant_id)
                    
                    sync_results.append({
                        "user_id": user_id,
                        "status": "synced",
                        "customer_id": customer_info.get("customer", {}).get("lago_id"),
                        "subscriptions_count": len(subscriptions.get("subscriptions", []))
                    })
                    
                except Exception as e:
                    sync_results.append({
                        "user_id": user_id,
                        "status": "error",
                        "error": str(e)
                    })
            
            return {
                "tenant_id": tenant_id,
                "sync_results": sync_results,
                "total_users": len(sync_results),
                "successful_syncs": len([r for r in sync_results if r["status"] == "synced"])
            }
            
        except Exception as e:
            logger.error(f"Failed to sync billing data for tenant {tenant_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Billing sync failed")
    
    async def _log_audit_event(
        self,
        event_type: str,
        user_id: Optional[str],
        tenant_id: Optional[str],
        details: Dict[str, Any]
    ):
        """Log audit event for billing operations"""
        audit_doc = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "tenant_id": ObjectId(tenant_id) if tenant_id else None,
            "user_id": user_id,
            "target_user_id": details.get("target_user_id"),
            "admin_user_id": None,
            "ip_address": None,
            "user_agent": None,
            "details": details,
            "severity": "info",
            "session_id": None,
            "action": event_type,
            "resource": "billing",
            "before_state": None,
            "after_state": details,
            "correlation_id": f"billing_{event_type}_{datetime.now().timestamp()}"
        }
        
        self.audit_logs.insert_one(audit_doc)

# =====================================
# DEPENDENCY INJECTION
# =====================================

def get_lago_billing_service(
    db: Database = Depends(get_database),
    metrics = Depends(get_metrics)
) -> LagoBillingService:
    """Dependency to get Lago billing service"""
    return LagoBillingService(db, metrics)

# =====================================
# CONVENIENCE FUNCTIONS FOR COMMON OPERATIONS
# =====================================

async def setup_new_tenant_billing(
    tenant_id: str,
    organization_name: str,
    admin_email: str,
    billing_service: LagoBillingService
) -> Dict[str, Any]:
    """Complete billing setup for new tenant"""
    try:
        # Setup billing
        billing_result = await billing_service.setup_tenant_billing(
            tenant_id=tenant_id,
            organization_name=organization_name,
            admin_email=admin_email
        )
        
        # Create default plans (you can customize these)
        default_plans = [
            {
                "name": "Basic Plan",
                "code": "basic",
                "interval": "monthly",
                "amount_cents": 999,  # $9.99
                "currency": "USD"
            },
            {
                "name": "Pro Plan", 
                "code": "pro",
                "interval": "monthly",
                "amount_cents": 2999,  # $29.99
                "currency": "USD"
            }
        ]
        
        created_plans = []
        for plan_config in default_plans:
            try:
                plan = await billing_service.create_tenant_plan(
                    tenant_id=tenant_id,
                    **plan_config
                )
                created_plans.append(plan)
            except Exception as e:
                logger.warning(f"Failed to create plan {plan_config['code']}: {str(e)}")
        
        return {
            "billing_setup": billing_result,
            "plans_created": len(created_plans),
            "status": "complete"
        }
        
    except Exception as e:
        logger.error(f"Failed complete billing setup for tenant {tenant_id}: {str(e)}")
        raise

async def setup_user_subscription(
    user_id: str,
    plan_code: str,
    tenant_id: Optional[str],
    billing_service: LagoBillingService
) -> Dict[str, Any]:
    """Complete user subscription setup"""
    try:
        # Ensure customer exists
        try:
            customer = await billing_service.get_customer_info(user_id, tenant_id)
        except HTTPException:
            # Create customer if doesn't exist
            customer = await billing_service.create_customer_for_user(user_id, tenant_id)
        
        # Create subscription
        subscription = await billing_service.create_user_subscription(
            user_id=user_id,
            plan_code=plan_code,
            tenant_id=tenant_id
        )
        
        return {
            "customer": customer,
            "subscription": subscription,
            "status": "subscribed"
        }
        
    except Exception as e:
        logger.error(f"Failed to setup subscription for user {user_id}: {str(e)}")
        raise