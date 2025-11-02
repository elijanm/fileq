from utils.user import AuditLogger
from typing import Optional,Dict,Any
from utils.db import get_database
from pymongo.database import Database
from metrics.metrics import get_metrics
from metrics.metrics import MetricsCollector

class AuditService:
    # Global/static DB and metrics
    _db: Optional[Database] = None
    _metrics: Optional[MetricsCollector] = None

    @classmethod
    def configure(cls, db: Database, metrics: Optional[MetricsCollector] = None):
        """
        Configure global DB and metrics. Call this once at app startup.
        """
        cls._db = db
        cls._metrics = metrics

    @staticmethod
    async def log_event(
        event_type: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info",
        db: Optional[Database] = None,
        metrics: Optional[MetricsCollector] = None,
    ):
        """
        Public API for logging audit events. Delegates to AuditLogger.
        Uses global db/metrics if not provided explicitly.
        """
        try:
            db = db or AuditService._db
            metrics = metrics or AuditService._metrics

            if  db is None:
                raise RuntimeError("AuditService is not configured with a database")

        
            await AuditLogger.log_event(
                event_type=event_type,
                tenant_id=tenant_id,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
                severity=severity,
                db=db,
                metrics=metrics,
            )
        except Exception as e:
           print(f"errx: {e}")