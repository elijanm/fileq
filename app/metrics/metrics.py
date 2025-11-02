from prometheus_client import Counter, Histogram, Gauge

from typing import Dict, Any, Optional
import time

# =====================================
# METRICS COLLECTOR
# =====================================

class MetricsCollector:
    """Prometheus metrics collector for authentication system"""
    
    def __init__(self):
        # Counter metrics
        self.auth_requests_total = Counter(
            'auth_requests_total',
            'Total authentication requests',
            ['method', 'status', 'endpoint']
        )
        
        self.user_registrations_total = Counter(
            'user_registrations_total',
            'Total user registrations',
            ['tenant_id', 'status']
        )
        
        self.security_events = Counter(
            'security_events',
            'Total user registrations',
            ['tenant_id','event_type', 'severity']
        )
        
        
        self.login_attempts_total = Counter(
            'login_attempts_total',
            'Total login attempts',
            ['status', 'tenant_id','user_id']
        )
        
        self.permission_checks_total = Counter(
            'permission_checks_total',
            'Total permission checks',
            ['permission', 'granted', 'tenant_id']
        )
        
        # Histogram metrics
        self.auth_request_duration = Histogram(
            'auth_request_duration_seconds',
            'Authentication request duration',
            ['endpoint']
        )
        
        self.db_operation_duration = Histogram(
            'db_operation_duration_seconds',
            'Database operation duration',
            ['operation', 'collection']
        )
        
        # Gauge metrics
        self.active_sessions = Gauge(
            'active_sessions_total',
            'Number of active user sessions',
            ['tenant_id']
        )
        
        self.active_users = Gauge(
            'active_users_total',
            'Number of active users',
            ['tenant_id']
        )
        
        self.failed_login_attempts = Gauge(
            'failed_login_attempts_total',
            'Number of failed login attempts in last hour',
            ['ip_address']
        )
        
        # How many files were uploaded successfully
        self.files_uploaded_total = Counter(
            "files_uploaded_total",
            "Total number of successfully uploaded files",
            ["method", "status"]  # method=simple|multipart, status=approved|quarantined
        )
        
        self.files_downloaded_bytes_total = Counter(
            "files_downloaded_bytes_total",
            "Total bytes successfully downloaded",
            ["source", "country", "file_type"]
        )

        # Total number of downloads (count of requests)
        self.files_downloaded_total = Counter(
            "files_downloaded_total",
            "Total number of file downloads",
            ["source", "country", "file_type"]
        )
        self.files_downloaded_fail_total = Counter(
            "files_downloaded_fail_total",
            "Total number of unsuccesful downloads attemps",
            ["source", "file_type", "country"]  # source=tmp|minio, id=file_id
        )
       

        
        self.download_duration_seconds = Histogram(
            "files_download_duration_seconds",
            "Time taken to serve a file download",
            ["country"]
        )

        # How many uploads failed
        self.files_failed_total = Counter(
            "files_failed_total",
            "Total number of failed file uploads",
            ["reason"]  # reason=timeout|validation|virus|other
        )

        # Bandwidth usage
        self.ingress_bytes_total = Counter(
            "ingress_bytes_total",
            "Total bytes uploaded by users"
        )
        self.egress_bytes_total = Counter(
            "egress_bytes_total",
            "Total bytes downloaded by users"
        )
        self.files_uploading = Gauge(
            "files_uploading",
            "Number of files currently in uploading state"
        )

        # Total size currently in staging / quarantine
        self.files_quarantined_bytes = Gauge(
            "files_quarantined_bytes",
            "Total size of files currently quarantined"
        )

        # Queue depth (pending uploads)
        self.upload_queue_depth = Gauge(
            "upload_queue_depth",
            "Number of files waiting to start upload"
        )
        # Distribution of file sizes uploaded
        self.file_size_bytes = Histogram(
            "file_size_bytes",
            "Histogram of uploaded file sizes in bytes",
            buckets=[1024, 10*1024, 100*1024, 1*1024*1024,
                    10*1024*1024, 100*1024*1024, float("inf")]
        )

        # Upload duration (end-to-end time)
        self.upload_duration_seconds = Histogram(
            "upload_duration_seconds",
            "Histogram of file upload durations"
        )

        # Bandwidth per upload
        self.upload_bandwidth_bytes_per_sec = Histogram(
            "upload_bandwidth_bytes_per_sec",
            "Histogram of upload bandwidth"
        )
    
    def record_auth_request(self, method: str, status: str, endpoint: str, duration: float):
        """Record authentication request metrics"""
        self.auth_requests_total.labels(
            method=method,
            status=status,
            endpoint=endpoint
        ).inc()
        
        self.auth_request_duration.labels(endpoint=endpoint).observe(duration)
    
    def record_registration(self, tenant_id: Optional[str], status: str):
        """Record user registration"""
        self.user_registrations_total.labels(
            tenant_id=tenant_id or "global",
            status=status
        ).inc()
    
    def record_login_attempt(self, status: str, tenant_id: Optional[str]):
        """Record login attempt"""
        self.login_attempts_total.labels(
            status=status,
            tenant_id=tenant_id or "global"
        ).inc()
    
    def record_permission_check(self, permission: str, granted: bool, tenant_id: Optional[str]):
        """Record permission check"""
        self.permission_checks_total.labels(
            permission=permission,
            granted=str(granted).lower(),
            tenant_id=tenant_id or "global"
        ).inc()

# Global metrics instance
_metrics_collector = MetricsCollector()

def get_metrics() -> MetricsCollector:
    """Dependency to get metrics collector"""
    return _metrics_collector
