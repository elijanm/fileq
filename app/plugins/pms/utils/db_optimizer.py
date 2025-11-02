class DatabaseOptimizer:
    """Database optimization for large-scale operations"""
    
    def __init__(self, db):
        self.db = db
    
    async def create_indexes(self):
        """Create essential indexes for performance"""
        
        # Invoice indexes
        await self.db.property_invoices.create_index([
            ("tenant_id", 1),
            ("meta.billing_period", 1)
        ])
        
        await self.db.property_invoices.create_index([
            ("property_id", 1),
            ("date_issued", -1)
        ])
        
        await self.db.property_invoices.create_index([
            ("status", 1),
            ("balance_amount", 1)
        ])
        
        await self.db.property_invoices.create_index([
            ("tenant_id", 1),
            ("balance_amount", 1),
            ("status", 1),
            ("balance_forwarded", 1)
        ])
        
        # Lease indexes
        await self.db.property_leases.create_index([
            ("status", 1),
            ("property_id", 1)
        ])
        
        await self.db.property_leases.create_index([
            ("tenant_id", 1),
            ("status", 1)
        ])
        
        # Payment indexes
        await self.db.property_payments.create_index([
            ("tenant_id", 1),
            ("payment_date", -1)
        ])
        
        await self.db.property_payments.create_index([
            ("property_id", 1),
            ("payment_date", -1)
        ])
        
        # Ticket indexes
        await self.db.property_tickets.create_index([
            ("metadata.property_id", 1),
            ("status", 1),
            ("metadata.billing_month", 1)
        ])
        
        await self.db.property_tickets.create_index([
            ("tasks.metadata.invoice_id", 1)
        ])
        
        # Tenant indexes
        await self.db.property_tenants.create_index([
            ("property_id", 1),
            ("credit_balance", 1)
        ])
        
        print("✓ All indexes created successfully")