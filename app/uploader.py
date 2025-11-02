#!/usr/bin/env python3
"""
Enhanced Multipart File Uploader v4.0
=====================================

A production-ready multipart file upload client with:
- Optimized HTTP session management and connection reuse
- Memory-optimized streaming for large files
- Adaptive concurrency and chunk sizing
- Directory manifest generation
- Comprehensive progress tracking and error handling
"""

import os
import sys
import math
import time
import random
import hashlib
import mimetypes
import requests
import logging
import argparse
import json
import threading
import socket
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Event
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Configure comprehensive logging with fixed duplicate issue
def setup_logging(level=logging.INFO, log_file="upload.log"):
    """Setup logging with both file and console handlers."""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get root logger and clear existing handlers to prevent duplicates
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    return logging.getLogger(__name__)

logger = setup_logging()


@dataclass
class AuthConfig:
    """Authentication configuration."""
    auth_type: str = "none"  # "none", "bearer", "token", "api_key"
    token: Optional[str] = None
    api_key: Optional[str] = None
    header_name: Optional[str] = None  # Custom header name for token auth
    param_name: Optional[str] = None   # Parameter name for URL-based auth


@dataclass
class SessionConfig:
    """HTTP session configuration for optimal performance."""
    # Connection pooling
    pool_connections: int = 30
    pool_maxsize: int = 50
    pool_block: bool = False
    
    # Retry configuration
    retries_total: int = 3
    retries_backoff_factor: float = 0.3
    retries_status_forcelist: List[int] = field(default_factory=lambda: [500, 502, 503, 504])
    
    # Timeout configuration
    connect_timeout: float = 10.0
    read_timeout: float = 300.0  # 5 minutes for large uploads
    
    # Keep-alive settings
    keep_alive_timeout: int = 300  # 5 minutes
    keep_alive_max_requests: int = 10000
    
    # TCP socket optimization
    tcp_keepalive: bool = True
    tcp_keepidle: int = 60
    tcp_keepintvl: int = 30
    tcp_keepcnt: int = 3
    tcp_nodelay: bool = True


@dataclass
class OptimizedUploadConfig:
    """Enhanced configuration with memory and speed optimizations."""
    api_base: str = "http://localhost:8000/uploads"
    
    # Authentication
    auth_config: AuthConfig = field(default_factory=AuthConfig)
    
    # Session configuration
    session_config: SessionConfig = field(default_factory=SessionConfig)
    
    # Adaptive concurrency
    adaptive_workers: bool = True
    min_workers: int = 2
    max_workers: int = 6
    max_workers_large_files: int = 12
    
    # Memory management
    streaming_threshold: int = 50 * 1024 * 1024  # 50MB
    read_chunk_size: int = 64 * 1024  # 64KB
    
    # Adaptive chunk sizes
    adaptive_chunk_size: bool = True
    min_chunk_size: int = 5 * 1024 * 1024    # 5MB (S3 minimum)
    max_chunk_size: int = 100 * 1024 * 1024  # 100MB
    default_chunk_size: int = 10 * 1024 * 1024  # 10MB
    
    # Retry and timeout settings
    max_retries: int = 3
    timeout: int = 900
    
    # Features
    verify_checksums: bool = False
    progress_tracking: bool = True
    progress_interval: int = 5
    debug: bool = False
    generate_manifest: bool = True
    
    user_agent: str = "EnhancedMultipartUploader/4.0"
    
    def __post_init__(self):
        # Environment variable overrides
        self.api_base = os.getenv("UPLOAD_API_BASE", self.api_base)
        self.max_workers = int(os.getenv("MAX_WORKERS", str(self.max_workers)))
        self.max_retries = int(os.getenv("MAX_RETRIES", str(self.max_retries)))
        self.timeout = int(os.getenv("TIMEOUT", str(self.timeout)))
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.progress_tracking = os.getenv("PROGRESS_TRACKING", "true").lower() == "true"
        
        # Authentication overrides
        if os.getenv("AUTH_TOKEN"):
            self.auth_config.auth_type = "bearer"
            self.auth_config.token = os.getenv("AUTH_TOKEN")
        elif os.getenv("API_KEY"):
            self.auth_config.auth_type = "api_key"
            self.auth_config.api_key = os.getenv("API_KEY")
        
        # Validation
        if self.max_workers < 1 or self.max_workers > 20:
            raise ValueError("max_workers must be between 1 and 20")
        if self.timeout < 60:
            raise ValueError("timeout must be at least 60 seconds")


class OptimizedHTTPAdapter(HTTPAdapter):
    """Custom HTTP adapter with performance optimizations and platform compatibility."""
    
    def __init__(self, session_config: SessionConfig, *args, **kwargs):
        self.session_config = session_config
        
        # Configure retry strategy with safer defaults
        try:
            retry_strategy = Retry(
                total=session_config.retries_total,
                backoff_factor=session_config.retries_backoff_factor,
                status_forcelist=session_config.retries_status_forcelist,
                allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
            )
        except Exception as e:
            logger.warning(f"Failed to configure retry strategy: {e}, using defaults")
            retry_strategy = Retry(total=3)
        
        super().__init__(max_retries=retry_strategy, *args, **kwargs)
    
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        """Initialize connection pool with optimized settings and platform compatibility."""
        
        # Socket options for performance (with platform compatibility)
        socket_options = []
        if self.session_config.tcp_keepalive:
            try:
                if hasattr(socket, 'SOL_SOCKET') and hasattr(socket, 'SO_KEEPALIVE'):
                    socket_options.append((socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1))
                
                # TCP keep-alive settings (platform-specific)
                if hasattr(socket, 'IPPROTO_TCP'):
                    if hasattr(socket, 'TCP_KEEPIDLE'):
                        socket_options.append((socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, self.session_config.tcp_keepidle))
                    if hasattr(socket, 'TCP_KEEPINTVL'):
                        socket_options.append((socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, self.session_config.tcp_keepintvl))
                    if hasattr(socket, 'TCP_KEEPCNT'):
                        socket_options.append((socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self.session_config.tcp_keepcnt))
                    
                    # Enable TCP_NODELAY for lower latency
                    if self.session_config.tcp_nodelay and hasattr(socket, 'TCP_NODELAY'):
                        socket_options.append((socket.IPPROTO_TCP, socket.TCP_NODELAY, 1))
                        
            except Exception as e:
                logger.debug(f"TCP socket optimization not available: {e}")
                socket_options = []
        
        # Use session config values, but respect parent class parameters
        final_connections = self.session_config.pool_connections
        final_maxsize = self.session_config.pool_maxsize
        final_block = self.session_config.pool_block
        
        # Add socket options if available
        if socket_options:
            try:
                pool_kwargs['socket_options'] = socket_options
            except Exception as e:
                logger.debug(f"Socket options not supported: {e}")
        
        try:
            return super().init_poolmanager(
                final_connections, 
                final_maxsize, 
                block=final_block, 
                **pool_kwargs
            )
        except Exception as e:
            # Fallback to basic configuration if advanced options fail
            logger.warning(f"Advanced pool configuration failed: {e}, using basic settings")
            basic_pool_kwargs = {k: v for k, v in pool_kwargs.items() 
                               if k not in ['socket_options']}
            return super().init_poolmanager(
                final_connections, 
                final_maxsize, 
                block=final_block, 
                **basic_pool_kwargs
            )


class SessionManager:
    """Advanced session manager with automatic optimization and authentication."""
    
    def __init__(self, config: OptimizedUploadConfig):
        self.config = config
        self.session_config = config.session_config
        self.auth_config = config.auth_config
        self.session = None
        self.stats = {
            'requests_made': 0,
            'connection_reuses': 0,
            'connection_errors': 0,
            'session_recreations': 0,
            'total_bytes_uploaded': 0
        }
        self._create_session()
    
    def _create_session(self):
        """Create an optimized requests session with authentication."""
        if self.session:
            try:
                self.session.close()
            except:
                pass
        
        self.session = requests.Session()
        
        # Create optimized adapters
        http_adapter = OptimizedHTTPAdapter(self.session_config)
        https_adapter = OptimizedHTTPAdapter(self.session_config)
        
        # Mount adapters
        self.session.mount("http://", http_adapter)
        self.session.mount("https://", https_adapter)
        
        # Base headers
        headers = {
            'User-Agent': self.config.user_agent,
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Keep-Alive': f'timeout={self.session_config.keep_alive_timeout}, max={self.session_config.keep_alive_max_requests}',
        }
        
        # Add authentication headers
        auth_headers = self._get_auth_headers()
        headers.update(auth_headers)
        
        self.session.headers.update(headers)
        
        # Set timeout as tuple (connect, read)
        self.session.timeout = (
            self.session_config.connect_timeout,
            self.session_config.read_timeout
        )
        
        self.stats['session_recreations'] += 1
        logger.debug(f"Created new HTTP session (recreation #{self.stats['session_recreations']})")
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Generate authentication headers based on config."""
        headers = {}
        
        if self.auth_config.auth_type == "bearer" and self.auth_config.token:
            headers['Authorization'] = f'Bearer {self.auth_config.token}'
        
        elif self.auth_config.auth_type == "token" and self.auth_config.token:
            if self.auth_config.header_name:
                headers[self.auth_config.header_name] = self.auth_config.token
            else:
                headers['Authorization'] = f'Token {self.auth_config.token}'
        
        elif self.auth_config.auth_type == "api_key" and self.auth_config.api_key:
            if self.auth_config.header_name:
                headers[self.auth_config.header_name] = self.auth_config.api_key
            else:
                headers['X-API-Key'] = self.auth_config.api_key
        
        return headers
    
    def _add_auth_params(self, url: str, params: Dict[str, Any] = None) -> Tuple[str, Dict[str, Any]]:
        """Add authentication parameters to URL if needed."""
        if params is None:
            params = {}
        
        if (self.auth_config.auth_type in ["token", "api_key"] and 
            self.auth_config.param_name and 
            (self.auth_config.token or self.auth_config.api_key)):
            
            auth_value = self.auth_config.token or self.auth_config.api_key
            params[self.auth_config.param_name] = auth_value
        
        return url, params
    
    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make request with session management, authentication, and statistics tracking."""
        self.stats['requests_made'] += 1
        
        # Add authentication parameters if needed
        if 'params' in kwargs:
            url, kwargs['params'] = self._add_auth_params(url, kwargs['params'])
        else:
            url, auth_params = self._add_auth_params(url)
            if auth_params:
                kwargs['params'] = auth_params
        
        try:
            # Use session for the request
            response = self.session.request(method, url, **kwargs)
            
            # Track connection reuse (approximation)
            if hasattr(response, 'connection') and response.connection:
                self.stats['connection_reuses'] += 1
            
            return response
            
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.SSLError) as e:
            
            self.stats['connection_errors'] += 1
            logger.warning(f"Connection error: {e}")
            
            # Recreate session on persistent connection issues
            if self.stats['connection_errors'] % 3 == 0:
                logger.info("Recreating session due to repeated connection errors")
                self._create_session()
            
            raise
    
    def put_file_part(self, url: str, data, headers: Dict[str, str] = None) -> requests.Response:
        """Optimized PUT request for file parts with authentication."""
        put_headers = headers or {}
        
        # Add upload-specific headers
        put_headers.update({
            'Content-Type': 'application/octet-stream',
            'Expect': '100-continue',  # Enable HTTP 100-continue for large uploads
        })
        
        response = self.request('PUT', url, data=data, headers=put_headers)
        
        # Track uploaded bytes for statistics
        if hasattr(data, '__len__'):
            self.stats['total_bytes_uploaded'] += len(data)
        elif 'Content-Length' in put_headers:
            self.stats['total_bytes_uploaded'] += int(put_headers['Content-Length'])
        
        return response
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        stats = self.stats.copy()
        stats['auth_type'] = self.auth_config.auth_type
        return stats
    
    def close(self):
        """Clean up session resources."""
        if self.session:
            try:
                self.session.close()
            except:
                pass
            self.session = None


@dataclass
class FileManifestEntry:
    """Individual file entry in manifest."""
    relative_path: str
    size: int
    content_type: str
    checksum: Optional[str] = None
    modified_time: Optional[str] = None
    permissions: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DirectoryManifest:
    """Complete directory structure manifest."""
    root_path: str
    created_at: str
    total_files: int
    total_size: int
    files: List[FileManifestEntry]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_path": self.root_path,
            "created_at": self.created_at,
            "total_files": self.total_files,
            "total_size": self.total_size,
            "files": [f.to_dict() for f in self.files],
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class EnhancedFileInfo:
    """Enhanced file metadata container with manifest support."""
    filename: str
    total_size: int
    content_type: str = "application/octet-stream"
    checksum: Optional[str] = None
    relative_path: Optional[str] = None
    manifest_entry: Optional[FileManifestEntry] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.manifest_entry:
            data["manifest_entry"] = self.manifest_entry.to_dict()
        return data


@dataclass
class UploadSession:
    """Upload session information."""
    filename: str
    file_id: str
    upload_id: str
    part_size: int
    parts: List[Dict[str, Any]]
    upload_token: Optional[str] = None
    
    @property
    def parts_map(self) -> Dict[int, str]:
        """Get mapping of part numbers to upload URLs."""
        return {p["part_number"]: p["url"] for p in self.parts}
    
    @property
    def total_parts(self) -> int:
        """Get total number of parts."""
        return len(self.parts)


@dataclass
class UploadStats:
    """Upload statistics and progress tracking."""
    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    total_bytes: int = 0
    uploaded_bytes: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now()
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        return (self.uploaded_bytes / self.total_bytes * 100) if self.total_bytes > 0 else 0
    
    @property
    def elapsed_time(self) -> timedelta:
        """Get elapsed time."""
        end = self.end_time or datetime.now()
        return end - self.start_time
    
    @property
    def upload_speed(self) -> float:
        """Get upload speed in bytes per second."""
        elapsed_seconds = self.elapsed_time.total_seconds()
        return self.uploaded_bytes / elapsed_seconds if elapsed_seconds > 0 else 0
    
    def format_speed(self) -> str:
        """Format upload speed as human-readable string."""
        speed = self.upload_speed
        for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
            if speed < 1024:
                return f"{speed:.2f} {unit}"
            speed /= 1024
        return f"{speed:.2f} TB/s"


class StreamingFileReader:
    """Memory-efficient file reader for large uploads."""
    
    def __init__(self, file_path: Path, chunk_size: int = 64 * 1024):
        self.file_path = file_path
        self.chunk_size = chunk_size
    
    def read_part_streaming(self, offset: int, size: int) -> Iterator[bytes]:
        """Stream file part in chunks to avoid loading entire part into memory."""
        with open(self.file_path, "rb") as f:
            f.seek(offset)
            remaining = size
            
            while remaining > 0:
                chunk_size = min(self.chunk_size, remaining)
                chunk = f.read(chunk_size)
                
                if not chunk:
                    break
                    
                yield chunk
                remaining -= len(chunk)


class ProgressTracker:
    """Enhanced progress tracking with real-time updates."""
    
    def __init__(self, config: OptimizedUploadConfig):
        self.config = config
        self.stats = UploadStats()
        self.lock = Lock()
        self.stop_event = Event()
        self.progress_thread = None
        self.callbacks = []
        self._bytes_updates = []
    
    def start(self, total_bytes: int, total_files: int = 1):
        """Start progress tracking."""
        with self.lock:
            self.stats.total_bytes = total_bytes
            self.stats.total_files = total_files
            self.stats.start_time = datetime.now()
        
        if self.config.progress_tracking:
            self.progress_thread = threading.Thread(target=self._progress_loop, daemon=True)
            self.progress_thread.start()
    
    def stop(self):
        """Stop progress tracking."""
        self.stop_event.set()
        if self.progress_thread:
            self.progress_thread.join(timeout=2)
        
        with self.lock:
            self.stats.end_time = datetime.now()
    
    def update_bytes(self, bytes_uploaded: int):
        """Update uploaded bytes count with thread safety."""
        with self.lock:
            old_bytes = self.stats.uploaded_bytes
            self.stats.uploaded_bytes += bytes_uploaded
            
            # Debug logging for tracking double-counting
            if self.config.debug:
                self._bytes_updates.append({
                    'timestamp': time.time(),
                    'bytes_added': bytes_uploaded,
                    'total_before': old_bytes,
                    'total_after': self.stats.uploaded_bytes,
                    'thread_id': threading.get_ident()
                })
                
                # Log if we exceed total
                if self.stats.uploaded_bytes > self.stats.total_bytes:
                    logger.warning(f"Progress exceeded total! "
                                 f"{self.stats.uploaded_bytes:,} > {self.stats.total_bytes:,}")
    
    def file_completed(self):
        """Mark a file as completed."""
        with self.lock:
            self.stats.completed_files += 1
    
    def file_failed(self):
        """Mark a file as failed."""
        with self.lock:
            self.stats.failed_files += 1
    
    def add_callback(self, callback: Callable[[UploadStats], None]):
        """Add progress callback."""
        self.callbacks.append(callback)
    
    def _progress_loop(self):
        """Background progress monitoring loop."""
        while not self.stop_event.wait(self.config.progress_interval):
            with self.lock:
                stats_copy = UploadStats(
                    total_files=self.stats.total_files,
                    completed_files=self.stats.completed_files,
                    failed_files=self.stats.failed_files,
                    total_bytes=self.stats.total_bytes,
                    uploaded_bytes=self.stats.uploaded_bytes,
                    start_time=self.stats.start_time
                )
            
            # Log progress
            logger.info(f"Progress: {stats_copy.progress_percent:.1f}% "
                       f"({stats_copy.uploaded_bytes:,}/{stats_copy.total_bytes:,} bytes) "
                       f"Speed: {stats_copy.format_speed()}")
            
            # Call callbacks
            for callback in self.callbacks:
                try:
                    callback(stats_copy)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")


class ManifestGenerator:
    """Generate directory structure manifests."""
    
    @staticmethod
    def create_manifest(dir_path: Path, include_checksums: bool = False) -> DirectoryManifest:
        """Create a comprehensive directory manifest."""
        if not dir_path.exists() or not dir_path.is_dir():
            raise ValueError(f"Invalid directory: {dir_path}")
        
        files = []
        total_size = 0
        
        logger.info(f"Generating manifest for {dir_path}")
        
        for file_path in dir_path.rglob("*"):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    relative_path = str(file_path.relative_to(dir_path))
                    
                    # Calculate checksum if requested
                    checksum = None
                    if include_checksums:
                        checksum = ManifestGenerator._calculate_checksum(file_path)
                    
                    entry = FileManifestEntry(
                        relative_path=relative_path,
                        size=stat.st_size,
                        content_type=mimetypes.guess_type(str(file_path))[0] or "application/octet-stream",
                        checksum=checksum,
                        modified_time=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        permissions=oct(stat.st_mode)[-3:]
                    )
                    
                    files.append(entry)
                    total_size += stat.st_size
                    
                except (OSError, PermissionError) as e:
                    logger.warning(f"Skipping {file_path}: {e}")
        
        return DirectoryManifest(
            root_path=str(dir_path),
            created_at=datetime.now().isoformat(),
            total_files=len(files),
            total_size=total_size,
            files=files,
            metadata={
                "platform": os.name,
                "python_version": sys.version,
                "uploader_version": "4.0"
            }
        )
    
    @staticmethod
    def _calculate_checksum(file_path: Path) -> str:
        """Calculate MD5 checksum for a file."""
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()


class EnhancedMultipartUploader:
    """Enhanced multipart file uploader with optimized HTTP session management."""
    
    def __init__(self, config: OptimizedUploadConfig):
        self.config = config
        self.session_manager = SessionManager(config)
        self.upload_lock = Lock()
        self.progress_tracker = ProgressTracker(config)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session_manager.close()
        self.progress_tracker.stop()
        
        # Print session statistics
        if self.config.debug:
            stats = self.session_manager.get_stats()
            logger.info("=== SESSION STATISTICS ===")
            for key, value in stats.items():
                logger.info(f"{key}: {value}")
    
    def calculate_optimal_workers(self, file_size: int, total_parts: int) -> int:
        """Calculate optimal number of workers based on file characteristics."""
        if not self.config.adaptive_workers:
            return self.config.max_workers
        
        # Base calculation on file size and parts
        if file_size > 1024 * 1024 * 1024:  # > 1GB
            optimal = min(self.config.max_workers_large_files, total_parts)
        elif file_size > 100 * 1024 * 1024:  # > 100MB
            optimal = min(8, total_parts)
        else:
            optimal = min(self.config.max_workers, total_parts)
        
        return max(self.config.min_workers, optimal)
    
    def calculate_optimal_chunk_size(self, file_size: int) -> int:
        """Calculate optimal chunk size based on file size."""
        if not self.config.adaptive_chunk_size:
            return self.config.default_chunk_size
        
        # Larger chunks for larger files (better throughput)
        if file_size > 10 * 1024 * 1024 * 1024:  # > 10GB
            return min(self.config.max_chunk_size, 100 * 1024 * 1024)  # 100MB
        elif file_size > 1024 * 1024 * 1024:     # > 1GB
            return min(self.config.max_chunk_size, 50 * 1024 * 1024)   # 50MB
        elif file_size > 100 * 1024 * 1024:      # > 100MB
            return min(self.config.max_chunk_size, 25 * 1024 * 1024)   # 25MB
        else:
            return self.config.min_chunk_size  # 5MB minimum
    
    def _log_request(self, method: str, url: str, **kwargs):
        """Log request details for debugging."""
        if not self.config.debug:
            return
        
        logger.debug(f"=== {method} {url} ===")
        if 'json' in kwargs:
            logger.debug(f"JSON: {json.dumps(kwargs['json'], indent=2)}")
        if 'headers' in kwargs:
            logger.debug(f"Headers: {kwargs['headers']}")
    
    def _log_response(self, response: requests.Response):
        """Log response details for debugging."""
        if not self.config.debug:
            return
        
        logger.debug(f"=== Response {response.status_code} ===")
        logger.debug(f"Headers: {dict(response.headers)}")
        
        try:
            if 'application/json' in response.headers.get('content-type', ''):
                logger.debug(f"JSON: {json.dumps(response.json(), indent=2)}")
            else:
                logger.debug(f"Body: {response.text[:500]}...")
        except:
            logger.debug("Body: <unable to decode>")
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic and error handling."""
        self._log_request(method, url, **kwargs)
        
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.session_manager.request(method, url, **kwargs)
                self._log_response(response)
                
                # Check for client errors (don't retry 4xx)
                if 400 <= response.status_code < 500:
                    logger.error(f"Client error {response.status_code}: {response.text}")
                    response.raise_for_status()
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"Timeout on attempt {attempt + 1}: {e}")
                
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
                
            except requests.exceptions.HTTPError as e:
                last_exception = e
                # Don't retry 4xx errors
                if hasattr(e, 'response') and 400 <= e.response.status_code < 500:
                    raise
                logger.warning(f"HTTP error on attempt {attempt + 1}: {e}")
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Request error on attempt {attempt + 1}: {e}")
            
            if attempt < self.config.max_retries:
                wait_time = min((2 ** attempt) + random.uniform(0, 1), 30)
                logger.info(f"Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
        
        raise last_exception
    
    def generate_test_files(self, folder: str = "test_files", num_files: int = 3):
        """Generate test files for upload testing."""
        folder_path = Path(folder)
        folder_path.mkdir(exist_ok=True)
        
        sizes_mb = [1, 5, 10, 20, 50]
        for i in range(num_files):
            size_mb = random.choice(sizes_mb)
            size_bytes = size_mb * 1024 * 1024
            file_path = folder_path / f"test_file_{i+1}_{size_mb}MB.bin"
            
            logger.info(f"Creating {file_path} ({size_mb} MB)...")
            
            with open(file_path, "wb") as f:
                remaining = size_bytes
                while remaining > 0:
                    chunk_size = min(self.config.default_chunk_size, remaining)
                    f.write(os.urandom(chunk_size))
                    remaining -= chunk_size
        
        logger.info(f"Generated {num_files} test files in {folder}")
    
    def calculate_checksum(self, file_path: Path) -> Optional[str]:
        """Calculate MD5 checksum of file."""
        if not self.config.verify_checksums:
            return None
        
        logger.debug(f"Calculating checksum for {file_path}")
        return ManifestGenerator._calculate_checksum(file_path)
    
    def init_upload(self, file_info: EnhancedFileInfo) -> UploadSession:
        """Initialize multipart upload for a single file."""
        logger.info(f"Initializing upload: {file_info.filename} ({file_info.total_size:,} bytes)")
        
        # Use adaptive chunk size
        optimal_chunk_size = self.calculate_optimal_chunk_size(file_info.total_size)
        
        payload = {
            "filename": file_info.filename,
            "total_size": file_info.total_size,
            "content_type": file_info.content_type,
            "tos_accept": True,
            "upload_token": "enhanced-client-v4",
            "meta": {
                "client_version": self.config.user_agent,
                "adaptive_chunk_size": optimal_chunk_size,
                "session_stats": self.session_manager.get_stats()
            }
        }
        
        if file_info.checksum:
            payload["meta"]["checksum"] = file_info.checksum
        if file_info.relative_path:
            payload["meta"]["relative_path"] = file_info.relative_path
        
        response = self._make_request("POST", f"{self.config.api_base}/multipart/init", json=payload)
        data = response.json()
        
        session = UploadSession(
            filename=data["filename"],
            file_id=data["file_id"],
            upload_id=data["upload_id"],
            part_size=data["part_size"],
            parts=data["parts"],
            upload_token=data.get("upload_token")
        )
        
        logger.info(f"Upload config: {args.workers} workers, {args.timeout}s timeout, "
               f"streaming threshold: {format_bytes(streaming_threshold)}")
    
    try:
        with EnhancedMultipartUploader(config) as uploader:
            
            # Test connection
            if args.test_connection:
                logger.info("Testing API connection...")
                try:
                    response = uploader._make_request("GET", f"{config.api_base}/../health")
                    logger.info("API connection successful")
                    return
                except Exception as e:
                    logger.error(f"API connection failed: {e}")
                    sys.exit(1)
            
            # Generate test files
            if args.generate_test_files:
                uploader.generate_test_files(num_files=args.generate_test_files)
                return
            
            # Validate path argument
            if not args.path:
                parser.error("path is required unless using --generate-test-files or --test-connection")
            
            # Setup progress callback
            tqdm = create_progress_bar()
            progress_bar = None
            
            if tqdm and not args.quiet:
                def progress_callback(stats: UploadStats):
                    if progress_bar:
                        progress_bar.set_description(
                            f"Files: {stats.completed_files}/{stats.total_files}"
                        )
                        progress_bar.set_postfix(
                            speed=stats.format_speed(),
                            refresh=False
                        )
                        progress_bar.n = stats.uploaded_bytes
                        progress_bar.refresh()
                
                uploader.progress_tracker.add_callback(progress_callback)
            
            # Start upload
            start_time = time.time()
            
            try:
                logger.info(f"Starting upload of: {args.path}")
                
                # Perform upload - progress tracking is handled in upload_path
                results = uploader.upload_path(args.path, use_batch=args.batch)
                
                # Close progress bar
                if progress_bar:
                    progress_bar.close()
                    progress_bar = None
                
                # Print summary
                if not args.quiet:
                    print_upload_summary(uploader.progress_tracker.stats)
                
                logger.info(f"Upload completed! {len(results)} files processed")
                
                # Print session statistics
                if args.debug:
                    session_stats = uploader.session_manager.get_stats()
                    logger.info("=== SESSION STATISTICS ===")
                    logger.info(f"Total requests: {session_stats['requests_made']}")
                    logger.info(f"Connection reuses: {session_stats['connection_reuses']}")
                    logger.info(f"Connection errors: {session_stats['connection_errors']}")
                    logger.info(f"Session recreations: {session_stats['session_recreations']}")
                    logger.info(f"Total bytes uploaded: {format_bytes(session_stats['total_bytes_uploaded'])}")
                    logger.info(f"Authentication type: {session_stats['auth_type']}")
                    
                    if session_stats['requests_made'] > 0:
                        reuse_ratio = session_stats['connection_reuses'] / session_stats['requests_made'] * 100
                        logger.info(f"Connection reuse ratio: {reuse_ratio:.1f}%")
                
                # Save results to file
                results_file = f"upload_results_{int(time.time())}.json"
                with open(results_file, "w") as f:
                    json.dump({
                        "timestamp": datetime.now().isoformat(),
                        "config": {
                            "api_base": config.api_base,
                            "workers": config.max_workers,
                            "batch_mode": args.batch,
                            "checksums": config.verify_checksums,
                            "streaming_threshold": config.streaming_threshold,
                            "adaptive_workers": config.adaptive_workers,
                            "manifest_enabled": config.generate_manifest,
                            "authentication": {
                                "type": config.auth_config.auth_type,
                                "has_token": bool(config.auth_config.token),
                                "has_api_key": bool(config.auth_config.api_key)
                            },
                            "session_config": {
                                "pool_connections": config.session_config.pool_connections,
                                "pool_maxsize": config.session_config.pool_maxsize,
                                "keep_alive_timeout": config.session_config.keep_alive_timeout
                            }
                        },
                        "stats": {
                            "total_files": len(results),
                            "total_time": time.time() - start_time,
                            "average_speed": uploader.progress_tracker.stats.format_speed()
                        },
                        "session_stats": uploader.session_manager.get_stats(),
                        "results": results
                    }, f, indent=2, default=str)
                
                logger.info(f"Results saved to {results_file}")
                
            except Exception as e:
                if progress_bar:
                    progress_bar.close()
                raise
    
    except KeyboardInterrupt:
        logger.info("Upload cancelled by user")
        sys.exit(130)
    
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(2)
    
    except PermissionError as e:
        logger.error(f"Permission denied: {e}")
        sys.exit(13)
    
    except requests.exceptions.ConnectionError:
        logger.error(f"Failed to connect to API at {config.api_base}")
        logger.error("Please check that the server is running and accessible")
        sys.exit(3)
    
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        if args.debug:
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()d initialized: {session.total_parts} parts of {session.part_size:,} bytes each")
        
        # Validate URLs aren't expired
        self._validate_presigned_urls(session)
        
        return session
    
    def init_batch_upload(self, files: List[EnhancedFileInfo]) -> Dict[str, UploadSession]:
        """Initialize batch multipart upload."""
        logger.info(f"Initializing batch upload for {len(files)} files")
        
        # Fix progress tracking before batch initialization
        self._fix_progress_before_batch(files)
        
        payload = {
            "files": [f.to_dict() for f in files],
            "tos_accept": True,
            "upload_token": "enhanced-client-v4"
        }
        
        response = self._make_request("POST", f"{self.config.api_base}/multipart/init-batch", json=payload)
        data = response.json()
        
        sessions = {}
        for session_data in data["sessions"]:
            session = UploadSession(
                filename=session_data["filename"],
                file_id=session_data["file_id"],
                upload_id=session_data["upload_id"],
                part_size=session_data["part_size"],
                parts=session_data["parts"],
                upload_token=session_data.get("upload_token")
            )
            sessions[session.filename] = session
        
        logger.info(f"Batch upload initialized for {len(sessions)} files")
        return sessions
    
    def _fix_progress_before_batch(self, file_infos: List[EnhancedFileInfo]):
        """Fix progress tracking before batch upload initialization."""
        correct_total_bytes = sum(f.total_size for f in file_infos)
        correct_total_files = len(file_infos)
        
        logger.info(f"Fixing progress: {correct_total_files} files, {correct_total_bytes:,} bytes")
        
        with self.progress_tracker.lock:
            self.progress_tracker.stats.total_bytes = correct_total_bytes
            self.progress_tracker.stats.total_files = correct_total_files
            self.progress_tracker.stats.uploaded_bytes = 0
            self.progress_tracker.stats.completed_files = 0
            self.progress_tracker.stats.failed_files = 0
            self.progress_tracker._bytes_updates = []
    
    def _validate_presigned_urls(self, session: UploadSession):
        """Validate presigned URLs for expiration and correctness."""
        current_time = int(time.time())
        min_expires = None
        
        for part in session.parts:
            try:
                parsed = urlparse(part["url"])
                query_params = parse_qs(parsed.query)
                
                # Check required parameters
                required = ['uploadId', 'partNumber', 'AWSAccessKeyId', 'Signature']
                missing = [p for p in required if p not in query_params]
                if missing:
                    raise ValueError(f"Part {part['part_number']} missing URL params: {missing}")
                
                # Check expiration
                if 'Expires' in query_params:
                    expires = int(query_params['Expires'][0])
                    if min_expires is None or expires < min_expires:
                        min_expires = expires
                        
                    if current_time >= expires:
                        raise ValueError(f"Part {part['part_number']} URL expired")
                
            except Exception as e:
                logger.error(f"URL validation failed for part {part['part_number']}: {e}")
                raise
        
        if min_expires:
            time_left = min_expires - current_time
            logger.info(f"URLs expire in {time_left} seconds")
            if time_left < 300:  # 5 minutes
                logger.warning("URLs expire soon - upload may fail!")
    
    def upload_part_streaming(self, file_path: Path, part_number: int, offset: int, 
                             size: int, upload_url: str, session: UploadSession) -> Tuple[int, str]:
        """Upload a single part using optimized session management."""
        logger.debug(f"Uploading part {part_number}: offset={offset:,}, size={size:,}")
        
        for attempt in range(self.config.max_retries + 1):
            try:
                # Use streaming approach for large parts
                if size > self.config.streaming_threshold:
                    return self._upload_part_streaming_large(file_path, part_number, offset, size, upload_url)
                else:
                    return self._upload_part_memory(file_path, part_number, offset, size, upload_url)
                    
            except Exception as e:
                logger.error(f"Part {part_number} attempt {attempt + 1} failed: {e}")
                
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response status: {e.response.status_code}")
                    logger.error(f"Response body: {e.response.text}")
                    
                    # Don't retry 403 errors
                    if e.response.status_code == 403:
                        raise
                
                if attempt == self.config.max_retries:
                    raise
                
                wait_time = min((2 ** attempt) + random.uniform(0, 1), 60)
                logger.info(f"Retrying part {part_number} in {wait_time:.1f}s...")
                time.sleep(wait_time)
    
    def _upload_part_streaming_large(self, file_path: Path, part_number: int, 
                                   offset: int, size: int, upload_url: str) -> Tuple[int, str]:
        """Upload large parts using streaming with optimized session."""
        logger.debug(f"Streaming large part {part_number} ({size:,} bytes)")
        
        stream_reader = StreamingFileReader(file_path, self.config.read_chunk_size)
        
        # Create a generator that yields chunks
        def data_generator():
            for chunk in stream_reader.read_part_streaming(offset, size):
                yield chunk
        
        headers = {"Content-Length": str(size)}
        
        start_time = time.time()
        # Use optimized session manager
        response = self.session_manager.put_file_part(upload_url, data_generator(), headers)
        upload_time = time.time() - start_time
        
        # Update progress ONLY ONCE after successful upload
        self.progress_tracker.update_bytes(size)
        
        etag = response.headers.get("ETag", "").strip('"')
        if not etag:
            etag = response.headers.get("etag", "").strip('"')
        
        speed = size / upload_time if upload_time > 0 else 0
        logger.debug(f"Part {part_number} streamed in {upload_time:.1f}s "
                    f"({speed/1024/1024:.1f} MB/s), ETag: {etag}")
        
        return part_number, etag
    
    def _upload_part_memory(self, file_path: Path, part_number: int, 
                          offset: int, size: int, upload_url: str) -> Tuple[int, str]:
        """Upload smaller parts using memory with optimized session."""
        with open(file_path, "rb") as f:
            f.seek(offset)
            part_data = f.read(size)
        
        if len(part_data) != size:
            raise ValueError(f"Read {len(part_data)} bytes, expected {size}")
        
        headers = {"Content-Length": str(len(part_data))}
        
        start_time = time.time()
        # Use optimized session manager
        response = self.session_manager.put_file_part(upload_url, part_data, headers)
        upload_time = time.time() - start_time
        
        etag = response.headers.get("ETag", "").strip('"')
        if not etag:
            etag = response.headers.get("etag", "").strip('"')
        if not etag:
            etag = hashlib.md5(part_data).hexdigest()
        
        # Update progress
        self.progress_tracker.update_bytes(size)
        
        speed = size / upload_time if upload_time > 0 else 0
        logger.debug(f"Part {part_number} completed in {upload_time:.1f}s "
                    f"({speed/1024/1024:.1f} MB/s), ETag: {etag}")
        
        return part_number, etag
    
    def _report_part_completion(self, upload_id: str, part_number: int, etag: str, size: int):
        """Report part completion to backend."""
        try:
            payload = {
                "upload_id": upload_id,
                "part_number": part_number,
                "etag": etag,
                "size": size
            }
            
            response = self._make_request("POST", f"{self.config.api_base}/report-part", json=payload)
            logger.debug(f"Reported part {part_number} completion")
            
        except Exception as e:
            logger.warning(f"Failed to report part {part_number}: {e}")
    
    def get_upload_progress(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Get upload progress from backend."""
        try:
            response = self._make_request("GET", f"{self.config.api_base}/progress/{upload_id}")
            return response.json()
        except Exception as e:
            logger.debug(f"Failed to get progress for {upload_id}: {e}")
            return None
    
    def upload_file_optimized(self, file_path: Path, session: UploadSession) -> Dict[str, Any]:
        """Optimized file upload with adaptive concurrency and session reuse."""
        logger.info(f"Starting optimized upload: {file_path.name}")
        
        total_size = file_path.stat().st_size
        optimal_workers = self.calculate_optimal_workers(total_size, session.total_parts)
        
        logger.info(f"Using {optimal_workers} workers for {session.total_parts} parts")
        logger.info(f"File size: {total_size:,} bytes, Part size: {session.part_size:,} bytes")
        
        uploaded_parts = []
        failed_parts = []
        
        # Dynamic load balancing - prioritize larger parts first
        parts_by_size = sorted(session.parts, 
                              key=lambda p: -((p["part_number"] - 1) * session.part_size))
        
        # Progress tracking thread
        progress_thread = None
        stop_progress = Event()
        
        def track_upload_progress():
            """Background thread to track individual upload progress."""
            while not stop_progress.wait(10):
                progress_data = self.get_upload_progress(session.upload_id)
                if progress_data:
                    logger.info(f"Backend progress: {progress_data.get('progress', 0):.1f}% "
                               f"({progress_data.get('parts_done', 0)}/{progress_data.get('parts_total', 0)} parts)")
        
        if self.config.progress_tracking and session.total_parts > 1:
            progress_thread = threading.Thread(target=track_upload_progress, daemon=True)
            progress_thread.start()
        
        try:
            # Upload parts with controlled concurrency
            with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
                futures = {}
                
                for part_info in parts_by_size:
                    part_number = part_info["part_number"]
                    offset = (part_number - 1) * session.part_size
                    size = min(session.part_size, total_size - offset)
                    
                    future = executor.submit(
                        self.upload_part_streaming,
                        file_path,
                        part_number,
                        offset,
                        size,
                        part_info["url"],
                        session
                    )
                    futures[future] = part_number
                
                # Collect results with progress updates
                for future in as_completed(futures):
                    part_number = futures[future]
                    try:
                        part_num, etag = future.result()
                        uploaded_parts.append({
                            "part_number": part_num,
                            "etag": etag
                        })
                        logger.debug(f"Completed part {part_num}")
                        
                        # Report to backend for progress tracking
                        if self.config.progress_tracking:
                            self._report_part_completion(session.upload_id, part_num, etag, 
                                                       min(session.part_size, total_size - ((part_num - 1) * session.part_size)))
                        
                    except Exception as e:
                        logger.error(f"Part {part_number} failed: {e}")
                        failed_parts.append(part_number)
                        
                        # Cancel remaining on critical errors
                        if "403" in str(e) or "expired" in str(e).lower():
                            for f in futures:
                                if not f.done():
                                    f.cancel()
                            break
        
        finally:
            if progress_thread:
                stop_progress.set()
                progress_thread.join(timeout=2)
        
        # Check upload success
        if failed_parts:
            raise Exception(f"Failed to upload parts: {failed_parts}")
        
        if len(uploaded_parts) != session.total_parts:
            raise Exception(f"Expected {session.total_parts} parts, got {len(uploaded_parts)}")
        
        # Complete the upload
        return self._complete_upload(session, uploaded_parts)
    
    def _complete_upload(self, session: UploadSession, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Complete the multipart upload."""
        logger.info(f"Completing upload: {session.filename}")
        
        # Sort parts by part number
        sorted_parts = sorted(parts, key=lambda p: p["part_number"])
        
        payload = {
            "file_id": session.file_id,
            "upload_id": session.upload_id,
            "filename": session.filename,
            "parts": sorted_parts
        }
        
        try:
            response = self._make_request("POST", f"{self.config.api_base}/multipart/complete", json=payload)
            result = response.json()
            
            logger.info(f"Upload completed: {session.filename}")
            if "download_url" in result:
                logger.info(f"Download URL: {result['download_url']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Complete upload failed: {e}")
            
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            
            raise
    
    def upload_single_file(self, file_path: Path) -> Dict[str, Any]:
        """Upload a single file with optimized session management."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Prepare file info
        file_info = EnhancedFileInfo(
            filename=file_path.name,
            total_size=file_path.stat().st_size,
            content_type=mimetypes.guess_type(str(file_path))[0] or "application/octet-stream",
            checksum=self.calculate_checksum(file_path)
        )
        
        # Initialize upload
        session = self.init_upload(file_info)
        
        # Upload file with optimizations
        try:
            result = self.upload_file_optimized(file_path, session)
            return result
        except Exception as e:
            logger.error(f"Upload failed for {file_path}: {e}")
            raise
    
    def upload_directory_with_manifest(self, dir_path: Path, 
                                     include_manifest: bool = True,
                                     use_batch: bool = True) -> Dict[str, Any]:
        """Upload directory with manifest and optimized session management."""
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        
        # Calculate actual total size FIRST
        files = []
        file_infos = []
        actual_total_size = 0
        
        logger.info("Analyzing directory structure...")
        
        for file_path in dir_path.rglob("*"):
            if file_path.is_file():
                file_size = file_path.stat().st_size
                actual_total_size += file_size
                
                relative_path = str(file_path.relative_to(dir_path))
                
                file_info = EnhancedFileInfo(
                    filename=file_path.name,
                    total_size=file_size,
                    content_type=mimetypes.guess_type(str(file_path))[0] or "application/octet-stream",
                    relative_path=relative_path
                )
                
                files.append(file_path)
                file_infos.append(file_info)
        
        logger.info(f"Directory analysis complete: {len(files)} files, {actual_total_size:,} bytes total")
        
        # Update progress tracker with CORRECT totals
        if hasattr(self, 'progress_tracker') and self.progress_tracker:
            with self.progress_tracker.lock:
                self.progress_tracker.stats.total_bytes = actual_total_size
                self.progress_tracker.stats.total_files = len(files)
                self.progress_tracker.stats.uploaded_bytes = 0
                self.progress_tracker.stats.completed_files = 0
                self.progress_tracker.stats.failed_files = 0
            
            logger.info(f"Progress tracker updated: {len(files)} files, {actual_total_size:,} bytes")
        
        # Generate manifest if needed
        manifest = None
        if include_manifest:
            logger.info("Generating directory manifest...")
            manifest = ManifestGenerator.create_manifest(dir_path, self.config.verify_checksums)
            
            # Update file_infos with manifest data
            for file_info in file_infos:
                manifest_entry = next(
                    (f for f in manifest.files if f.relative_path == file_info.relative_path),
                    None
                )
                if manifest_entry:
                    file_info.checksum = manifest_entry.checksum
                    file_info.manifest_entry = manifest_entry
        
        # Upload files
        results = []
        
        # Upload manifest first (if enabled)
        if manifest:
            manifest_path = dir_path / ".upload_manifest.json"
            try:
                with open(manifest_path, "w") as f:
                    f.write(manifest.to_json())
                
                logger.info("Uploading directory manifest...")
                manifest_result = self.upload_single_file(manifest_path)
                results.append(manifest_result)
                manifest_path.unlink()
                
            except Exception as e:
                logger.warning(f"Failed to upload manifest: {e}")
                if manifest_path.exists():
                    manifest_path.unlink()
        
        # Upload directory files
        if use_batch and len(files) > 1:
            logger.info("Using batch upload mode")
            try:
                sessions = self.init_batch_upload(file_infos)
                
                for file_path, file_info in zip(files, file_infos):
                    logger.info(f"Starting upload of {file_path.name} ({file_info.total_size:,} bytes)")
                    try:
                        session = sessions[file_info.filename]
                        result = self.upload_file_optimized(file_path, session)
                        results.append(result)
                        self.progress_tracker.file_completed()
                        logger.info(f"Completed {file_path.name}")
                    except Exception as e:
                        logger.error(f"Failed to upload {file_path.name}: {e}")
                        self.progress_tracker.file_failed()
                        
            except Exception as e:
                logger.error(f"Batch initialization failed: {e}")
                logger.info("Falling back to individual uploads")
                use_batch = False
        
        if not use_batch:
            logger.info("Using individual upload mode")
            for file_path in files:
                logger.info(f"Starting upload of {file_path.name}")
                try:
                    result = self.upload_single_file(file_path)
                    results.append(result)
                    self.progress_tracker.file_completed()
                    logger.info(f"Completed {file_path.name}")
                    
                except Exception as e:
                    logger.error(f"Failed to upload {file_path.name}: {e}")
                    self.progress_tracker.file_failed()
        
        return {
            "manifest": manifest.to_dict() if manifest else None,
            "upload_results": results,
            "summary": {
                "total_files": len(results),
                "total_bytes": actual_total_size,
                "manifest_included": include_manifest,
                "upload_mode": "batch" if use_batch else "individual"
            }
        }
    
    def upload_path(self, path: str, use_batch: bool = True) -> List[Dict[str, Any]]:
        """Upload a file or directory with optimized session management."""
        path_obj = Path(path)
        
        if not path_obj.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        
        if path_obj.is_file():
            logger.info(f"Uploading single file: {path_obj}")
            total_size = path_obj.stat().st_size
            self.progress_tracker.start(total_size, 1)
            
            try:
                result = self.upload_single_file(path_obj)
                self.progress_tracker.file_completed()
                return [result]
            except Exception as e:
                self.progress_tracker.file_failed()
                raise
            finally:
                self.progress_tracker.stop()
                
        elif path_obj.is_dir():
            logger.info(f"Uploading directory: {path_obj}")
            
            # Calculate directory size for initial progress setup
            files = list(path_obj.rglob("*"))
            files = [f for f in files if f.is_file()]
            total_size = sum(f.stat().st_size for f in files)
            
            logger.info(f"Directory contains {len(files)} files, {total_size:,} bytes total")
            
            # Start progress tracking
            self.progress_tracker.start(total_size, len(files))
            
            try:
                result = self.upload_directory_with_manifest(path_obj, self.config.generate_manifest, use_batch)
                return result["upload_results"]
            finally:
                self.progress_tracker.stop()
        else:
            raise ValueError(f"Invalid path type: {path}")


def create_progress_bar():
    """Create a progress bar if tqdm is available."""
    try:
        from tqdm import tqdm
        return tqdm
    except ImportError:
        logger.warning("tqdm not available - progress bars disabled")
        return None


def format_bytes(bytes_value: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.2f} PB"


def format_duration(seconds: float) -> str:
    """Format duration as human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def print_upload_summary(stats: UploadStats):
    """Print a comprehensive upload summary."""
    print("\n" + "="*60)
    print("UPLOAD SUMMARY")
    print("="*60)
    
    print(f"Files: {stats.completed_files}/{stats.total_files} completed")
    if stats.failed_files > 0:
        print(f"Failed: {stats.failed_files}")
    
    print(f"Data: {format_bytes(stats.uploaded_bytes)}/{format_bytes(stats.total_bytes)}")
    print(f"Progress: {stats.progress_percent:.1f}%")
    print(f"Duration: {format_duration(stats.elapsed_time.total_seconds())}")
    print(f"Speed: {stats.format_speed()}")
    
    if stats.failed_files == 0 and stats.completed_files == stats.total_files:
        print("All uploads completed successfully!")
    elif stats.failed_files > 0:
        print("Some uploads failed - check logs for details")
    
    print("="*60)


def main():
    """Enhanced command line interface with comprehensive options."""
    parser = argparse.ArgumentParser(
        description="Enhanced Multipart File Uploader v4.0 with Optimized HTTP Session Management",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="""
Examples:
  %(prog)s file.zip                           # Upload single file
  %(prog)s /path/to/folder --batch            # Batch upload directory
  %(prog)s folder --workers 6 --timeout 1800 # Custom settings
  %(prog)s --generate-test-files 5            # Generate test files
  %(prog)s folder --debug --no-manifest      # Debug mode, no manifest
  %(prog)s folder --streaming-threshold 25MB # Custom streaming threshold

Authentication Examples:
  %(prog)s file.zip --auth-type bearer --token "your_token_here"
  %(prog)s folder --auth-type api_key --api-key "your_api_key"
  %(prog)s folder --auth-type token --token "abc123" --auth-header "X-Auth-Token"
  %(prog)s folder --auth-type api_key --api-key "key123" --auth-param "api_key"
  
Environment Variables:
  export AUTH_TOKEN="your_bearer_token"      # Sets bearer auth automatically
  export API_KEY="your_api_key"              # Sets API key auth automatically
  export UPLOAD_API_BASE="https://api.example.com/uploads"
  export MAX_WORKERS=8
  export DEBUG=true
        """
    )
    
    # Primary arguments
    parser.add_argument("path", nargs="?", help="File or directory to upload")
    
    # Upload options
    parser.add_argument("--api-base", default="http://localhost:8000/uploads",
                       help="API base URL")
    parser.add_argument("--workers", type=int, default=6,
                       help="Number of concurrent workers (1-20)")
    parser.add_argument("--timeout", type=int, default=900,
                       help="Request timeout in seconds")
    parser.add_argument("--retries", type=int, default=3,
                       help="Maximum number of retries per request")
    
    # Authentication options
    auth_group = parser.add_argument_group('authentication')
    auth_group.add_argument("--auth-type", choices=["none", "bearer", "token", "api_key"], 
                           default="none", help="Authentication type")
    auth_group.add_argument("--token", help="Bearer token or auth token")
    auth_group.add_argument("--api-key", help="API key for authentication")
    auth_group.add_argument("--auth-header", help="Custom header name for token/key")
    auth_group.add_argument("--auth-param", help="URL parameter name for token/key")
    
    # Session and performance options
    parser.add_argument("--pool-connections", type=int, default=30,
                       help="HTTP connection pool size")
    parser.add_argument("--pool-maxsize", type=int, default=50,
                       help="Maximum connections per pool")
    parser.add_argument("--streaming-threshold", type=str, default="50MB",
                       help="Size threshold for streaming uploads")
    parser.add_argument("--adaptive-workers", action="store_true", default=True,
                       help="Use adaptive worker count based on file size")
    parser.add_argument("--adaptive-chunks", action="store_true", default=True,
                       help="Use adaptive chunk sizes based on file size")
    
    # Upload behavior
    parser.add_argument("--batch", action="store_true",
                       help="Use batch upload initialization for directories")
    parser.add_argument("--checksums", action="store_true",
                       help="Enable file checksum verification")
    parser.add_argument("--no-manifest", action="store_true",
                       help="Disable directory manifest generation")
    
    # Progress and monitoring
    parser.add_argument("--progress-off", action="store_true",
                       help="Disable progress tracking")
    parser.add_argument("--progress-interval", type=int, default=5,
                       help="Progress check interval in seconds")
    
    # Debugging and logging
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging and detailed output")
    parser.add_argument("--log-file", default="upload.log",
                       help="Log file path")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="Suppress console output (log file only)")
    
    # Utility functions
    parser.add_argument("--generate-test-files", type=int, metavar="N",
                       help="Generate N test files and exit")
    parser.add_argument("--test-connection", action="store_true",
                       help="Test API connection and exit")
    
    args = parser.parse_args()
    
    # Parse streaming threshold
    def parse_size(size_str):
        """Parse size string like '50MB' into bytes."""
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    streaming_threshold = parse_size(args.streaming_threshold)
    
    # Setup logging
    if args.quiet:
        console_level = logging.ERROR
    elif args.debug:
        console_level = logging.DEBUG
    else:
        console_level = logging.INFO
    
    logger = setup_logging(console_level, args.log_file)
    
    # Create configuration
    try:
        # Setup authentication
        auth_config = AuthConfig(
            auth_type=args.auth_type,
            token=args.token,
            api_key=args.api_key,
            header_name=args.auth_header,
            param_name=args.auth_param
        )
        
        session_config = SessionConfig(
            pool_connections=args.pool_connections,
            pool_maxsize=args.pool_maxsize
        )
        
        config = OptimizedUploadConfig(
            api_base=args.api_base,
            auth_config=auth_config,
            session_config=session_config,
            max_workers=args.workers,
            max_retries=args.retries,
            timeout=args.timeout,
            streaming_threshold=streaming_threshold,
            verify_checksums=args.checksums,
            progress_tracking=not args.progress_off,
            progress_interval=args.progress_interval,
            debug=args.debug,
            generate_manifest=not args.no_manifest,
            adaptive_workers=args.adaptive_workers,
            adaptive_chunk_size=args.adaptive_chunks
        )
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    logger.info(f"Starting Enhanced Multipart Uploader v4.0")
    logger.info(f"Authentication: {auth_config.auth_type}")
    logger.info(f"Session config: {args.pool_connections} pool connections, {args.pool_maxsize} max pool size")
    logger.info(f"Upload config: {args.workers} workers, {args.timeout}s timeout, "
               f"streaming threshold: {format_bytes(streaming_threshold)}"
               f"streaming threshold: {format_bytes(streaming_threshold)}")
    
    
    try:
        with EnhancedMultipartUploader(config) as uploader:
            
            # Test connection
            if args.test_connection:
                logger.info("Testing API connection...")
                try:
                    response = uploader._make_request("GET", f"{config.api_base}/../health")
                    logger.info("API connection successful")
                    return
                except Exception as e:
                    logger.error(f"API connection failed: {e}")
                    sys.exit(1)
            
            # Generate test files
            if args.generate_test_files:
                uploader.generate_test_files(num_files=args.generate_test_files)
                return
            
            # Validate path argument
            if not args.path:
                parser.error("path is required unless using --generate-test-files or --test-connection")
            
            # Setup progress callback
            tqdm = create_progress_bar()
            progress_bar = None
            
            if tqdm and not args.quiet:
                def progress_callback(stats: UploadStats):
                    if progress_bar:
                        progress_bar.set_description(
                            f"Files: {stats.completed_files}/{stats.total_files}"
                        )
                        progress_bar.set_postfix(
                            speed=stats.format_speed(),
                            refresh=False
                        )
                        progress_bar.n = stats.uploaded_bytes
                        progress_bar.refresh()
                
                uploader.progress_tracker.add_callback(progress_callback)
            
            # Start upload
            start_time = time.time()
            
            try:
                logger.info(f"Starting upload of: {args.path}")
                
                # Perform upload - progress tracking is handled in upload_path
                results = uploader.upload_path(args.path, use_batch=args.batch)
                
                # Close progress bar
                if progress_bar:
                    progress_bar.close()
                    progress_bar = None
                
                # Print summary
                if not args.quiet:
                    print_upload_summary(uploader.progress_tracker.stats)
                
                logger.info(f"Upload completed! {len(results)} files processed")
                
                # Print session statistics
                if args.debug:
                    session_stats = uploader.session_manager.get_stats()
                    logger.info("=== SESSION STATISTICS ===")
                    logger.info(f"Total requests: {session_stats['requests_made']}")
                    logger.info(f"Connection reuses: {session_stats['connection_reuses']}")
                    logger.info(f"Connection errors: {session_stats['connection_errors']}")
                    logger.info(f"Session recreations: {session_stats['session_recreations']}")
                    logger.info(f"Total bytes uploaded: {format_bytes(session_stats['total_bytes_uploaded'])}")
                    
                    if session_stats['requests_made'] > 0:
                        reuse_ratio = session_stats['connection_reuses'] / session_stats['requests_made'] * 100
                        logger.info(f"Connection reuse ratio: {reuse_ratio:.1f}%")
                
                # Save results to file
                results_file = f"upload_results_{int(time.time())}.json"
                with open(results_file, "w") as f:
                    json.dump({
                        "timestamp": datetime.now().isoformat(),
                        "config": {
                            "api_base": config.api_base,
                            "workers": config.max_workers,
                            "batch_mode": args.batch,
                            "checksums": config.verify_checksums,
                            "streaming_threshold": config.streaming_threshold,
                            "adaptive_workers": config.adaptive_workers,
                            "manifest_enabled": config.generate_manifest,
                            "session_config": {
                                "pool_connections": config.session_config.pool_connections,
                                "pool_maxsize": config.session_config.pool_maxsize,
                                "keep_alive_timeout": config.session_config.keep_alive_timeout
                            }
                        },
                        "stats": {
                            "total_files": len(results),
                            "total_time": time.time() - start_time,
                            "average_speed": uploader.progress_tracker.stats.format_speed()
                        },
                        "session_stats": uploader.session_manager.get_stats(),
                        "results": results
                    }, f, indent=2, default=str)
                
                logger.info(f"Results saved to {results_file}")
                
            except Exception as e:
                if progress_bar:
                    progress_bar.close()
                raise
    
    except KeyboardInterrupt:
        logger.info("Upload cancelled by user")
        sys.exit(130)
    
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(2)
    
    except PermissionError as e:
        logger.error(f"Permission denied: {e}")
        sys.exit(13)
    
    except requests.exceptions.ConnectionError:
        logger.error(f"Failed to connect to API at {config.api_base}")
        logger.error("Please check that the server is running and accessible")
        sys.exit(3)
    
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        if args.debug:
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()