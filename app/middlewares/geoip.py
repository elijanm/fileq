import json
import ipaddress
import httpx,time
import user_agents
from datetime import datetime, timezone
from typing import Dict, Any, Optional,Tuple
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from pymongo import ReturnDocument
from bson import ObjectId
from utils.db import get_database
from utils.redis_client import get_redis_client

GEOIP_SERVICE_URL = "http://172.232.181.126:8123/geoip"
API_KEY = "geo_eWtgOOKe9OV8IKvlsmGbkYPz0SyRErTX2v3DOVZSFbgStyPvjHTWkTKRTHVH"

class GeoIPMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.redis = get_redis_client()
        self.db = get_database()
    def normalize_ip(self,ip: str) -> str:
        try:
            ip_obj = ipaddress.ip_address(ip)
            # Convert IPv6-mapped IPv4 (::ffff:192.0.2.1) to IPv4
            if ip_obj.version == 6 and ip_obj.ipv4_mapped:
                return str(ip_obj.ipv4_mapped)
            return str(ip_obj)
        except ValueError:
            return ip


    def get_real_ip(self,request: Request) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract client IP from headers or connection.
        Always prefers IPv4 if available.
        Returns (ipv4, ipv6).
        """
        headers_to_check = [
            "CF-Connecting-IP",      # Cloudflare
            "X-Forwarded-For",       # Standard proxy header
            "X-Real-IP",             # Nginx proxy
            "X-Forwarded",           # Less common
            "Forwarded-For",         # Less common
            "Forwarded",             # RFC 7239
        ]

        ip_raw = None
        for header in headers_to_check:
            ip = request.headers.get(header)
            if ip:
                # X-Forwarded-For may contain multiple IPs -> take first
                if "," in ip:
                    ip = ip.split(",")[0].strip()
                ip_raw = ip
                break

        # fallback to client host
        if not ip_raw and request.client:
            ip_raw = request.client.host

        if not ip_raw:
            return None, None

        try:
            ip_obj = ipaddress.ip_address(ip_raw)

            # ✅ IPv4 case
            if ip_obj.version == 4:
                return str(ip_obj), None

            # ✅ IPv6 case
            elif ip_obj.version == 6:
                # IPv6-mapped IPv4 (::ffff:192.0.2.1)
                if ip_obj.ipv4_mapped:
                    return str(ip_obj.ipv4_mapped), str(ip_obj)
                
                # 6to4 format (2002::/16 encodes IPv4)
                if ip_raw.startswith("2002:"):
                    # decode embedded IPv4 from hex
                    hex_ip = ip_raw.split(":")[1]
                    if len(hex_ip) == 4:  # 16 bits for IPv4 high + low
                        ipv4 = ".".join(str(int(hex_ip[i:i+2], 16)) for i in range(0, 4, 2))
                        return ipv4, str(ip_obj)

                # plain IPv6, no IPv4 mapping
                return None, str(ip_obj)

        except ValueError:
            return None, None


    async def get_geolocation(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Call external GeoIP service"""
        ip_obj = ipaddress.ip_address(ip_address)
        if ip_obj.is_private or ip_obj.is_loopback:
            return {
                "ip": ip_address,
                "type": "local",
                "country": {},
                "city": None,
                "note": "Private/loopback address"
            }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{GEOIP_SERVICE_URL}/{ip_address}",
                    params={"api_key": API_KEY},
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    return resp.json()
                
        except Exception as e:
            print(f"GeoIP lookup failed for {ip_address}: {e}")
        return None

    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now(timezone.utc)
        ipv4, ipv6 = self.get_real_ip(request)
        ua_string = request.headers.get("User-Agent", "")
        ua = user_agents.parse(ua_string)
        client_ip = ipv4 or ipv6 or "unknown"
        cache_key = f"geoip:{client_ip}"
        ip_data = None
        
        # 1. Redis
        cached = self.redis.get(cache_key)
        if cached:
           
            ip_data = cached
            
        else:
            # 2. Mongo: ip_geolocation
            record = self.db.ip_geolocation.find_one({"ip": client_ip})
            if record:
              
                ip_data = record["geo_data"]
                self.redis.set(cache_key, json.dumps(ip_data), ex=86400)
            else:
                # 3. External GeoIP API
                ip_data = await self.get_geolocation(client_ip)
                if ip_data:
                    self.db.ip_geolocation.update_one(
                        {"ip": client_ip},
                        {"$set": {"geo_data": ip_data, "updated_at": datetime.now(timezone.utc)}},
                        upsert=True
                    )
                    self.redis.set(cache_key, json.dumps(ip_data), ex=86400)

        # --- Always update ip_cache (last seen + hit count) ---
        doc = self.db.ip_cache.find_one_and_update(
            {"ip": client_ip},
            {
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
                "$set": {"last_seen": datetime.now(timezone.utc), "ipv4": ipv4, "ipv6": ipv6},
                "$inc": {"hit_count": 1}
            },
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        iso_code = "UNKNOWN"
        if ip_data.get("country"):
            iso_code = ip_data.get("country",{}).get("iso_code")
       
        # Attach geoip info
        ip_data["geo_id"]=str(doc["_id"])
        request.state.geoip = ip_data
        request.state.geo = self
        request.state.ip_country = iso_code
        request.state.geo_id = ip_data["geo_id"] #from ip_cache unique ip

        response = await call_next(request)
        end_time = datetime.now(timezone.utc)
        duration_ms = (end_time - start_time).total_seconds() * 1000
        # --- Insert activity log ---
        self.db.ip_activities.insert_one({
            "ip": client_ip,
            "geo_ref": doc["_id"],   
            "user_agent": ua_string,
            "is_mobile": ua.is_mobile,
            "browser": f"{ua.browser.family} {ua.browser.version_string}",
            "os": f"{ua.os.family} {ua.os.version_string}",
            "device": ua.device.family,
            "endpoint": request.url.path,
            "method": request.method,
            "start_time": start_time,
            "end_time": end_time,
            "duration_ms": duration_ms,
            "status_code":response.status_code,
            "payload": {
                "params": dict(request.query_params),
                # "body": await request.json() if request.method in ("POST", "PUT", "PATCH") else None,
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        minute_key = int(time.time() // 60)
        redis_key = f"hits:{client_ip}:{minute_key}"
        count = self.redis.incr(redis_key)
        self.redis.expire(redis_key, 600)  # expire after 10 minutes

        
        
        
        return response
