from typing import Dict, Any, Optional,Union
from fastapi import Request, Depends, HTTPException, Body
import time
import logging
from pymongo.database import Database
import os
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import user_agents
import hashlib
import secrets
from utils.db import get_database,Database
from metrics.metrics import get_metrics
from metrics.metrics import MetricsCollector
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
from services.rbac_services import UserPermissionService, RoleService, PermissionService
from typing import List
import requests
# Monitoring and metrics
import structlog

# Security imports
from cryptography.fernet import Fernet
import jwt
from passlib.context import CryptContext
import redis


logger = structlog.get_logger()


#Configuration & Security Setup
# --------------------------

limiter = Limiter(key_func=get_remote_address, storage_uri=REDIS_URL)

# Structured logging
logger = structlog.get_logger()

# =====================================
# CLIENT INFO EXTRACTOR
# =====================================

@dataclass
class ClientInfo:
    ip_address: str
    user_agent: str
    country: Optional[str]
    city: Optional[str]
    is_mobile: bool
    browser: str
    os: str
    device: str

    

def get_client_info(request: Request) -> Dict[str, Any]:
    """Extract client information from request"""
    
    # Get IP address (handle proxies and load balancers)
    ip_address = get_real_ip(request)
    
    # Parse user agent
    user_agent_string = request.headers.get("User-Agent", "")
    ua = user_agents.parse(user_agent_string)
    
    # Basic client info
    client_info = {
        "ip_address": ip_address,
        "user_agent": user_agent_string,
        "is_mobile": ua.is_mobile,
        "browser": f"{ua.browser.family} {ua.browser.version_string}",
        "os": f"{ua.os.family} {ua.os.version_string}",
        "device": ua.device.family,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Add geolocation info if available (you'd integrate with a GeoIP service)
    geo_info = get_geolocation(ip_address)
    if geo_info:
        client_info.update(geo_info)
    
    return client_info

def get_real_ip(request: Request) -> str:
    """Extract real IP address from request headers"""
    # Check common proxy headers in order of preference
    headers_to_check = [
        "CF-Connecting-IP",      # Cloudflare
        "X-Forwarded-For",       # Standard proxy header
        "X-Real-IP",             # Nginx proxy
        "X-Forwarded",           # Less common
        "Forwarded-For",         # Less common
        "Forwarded"              # RFC 7239
    ]
    
    for header in headers_to_check:
        ip = request.headers.get(header)
        if ip:
            # X-Forwarded-For can contain multiple IPs, take the first one
            if "," in ip:
                ip = ip.split(",")[0].strip()
            
            # Validate IP address
            try:
                ipaddress.ip_address(ip.strip())
                return ip.strip()
            except ValueError:
                continue
    
    # Fallback to client host
    return request.client.host if request.client else "unknown"


def get_geolocation(ip_address: str) -> Optional[Dict[str, str]]:
    """Get geolocation info for IP address (placeholder - integrate with GeoIP service)"""
    # This is a placeholder. In production, you'd integrate with:
    # - MaxMind GeoIP2
    # - IP2Location
    # - ipstack
    # - etc.
    
    try:
        # Example integration with a hypothetical GeoIP service
        # import geoip2.database
        # reader = geoip2.database.Reader('/path/to/GeoLite2-City.mmdb')
        # response = reader.city(ip_address)
        # return {
        #     "country": response.country.name,
        #     "city": response.city.name,
        #     "region": response.subdivisions.most_specific.name,
        #     "postal_code": response.postal.code,
        #     "latitude": float(response.location.latitude),
        #     "longitude": float(response.location.longitude)
        # }
        
        # For now, return None (no geo data)
        return None
        
    except Exception as e:
        logger.warning(f"Failed to get geolocation for IP {ip_address}: {str(e)}")
        return None