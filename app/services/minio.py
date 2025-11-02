import httpx,os
from typing import Dict, Any, Optional, List


class MinioAPIClient:
    """
    Client wrapper for MinIO Management FastAPI
    running at http://95.110.228.29:8730
    """
    def __init__(self, 
                 base_url: Optional[str] = None, 
                 api_token: Optional[str] = None,debug: bool = False):
        self.base_url = (base_url or os.getenv("MINIO_API_BASE_URL", "http://95.110.228.29:8730")).rstrip("/")
        self.api_token = api_token or os.getenv("MINIO_API_TOKEN", "d5524c96-298a-4b42-bed3-98850ffb2d6d")
        self.headers = {"x-api-token": self.api_token}
        self.debug = debug
        self._client = httpx.AsyncClient(headers=self.headers, timeout=20.0)


    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            if self.debug:
                print(f"➡️ {method.upper()} {url} {kwargs.get('json') or ''}")
            resp = await self._client.request(method, url, **kwargs)
            resp.raise_for_status()
            data = resp.json()
            if self.debug:
                print(f"⬅️ {resp.status_code} {data}")
            return data
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"API error {e.response.status_code}: {e.response.text}") from e
        except Exception as e:
            raise RuntimeError(f"Request failed: {str(e)}") from e

    # =========================
    # USERS
    # =========================
    async def create_user(self, username: str, password: str, create_bucket: bool = True) -> Dict[str, Any]:
        return await self._request("POST", "/users", json={"username": username, "password": password, "create_bucket": create_bucket})

    async def list_users(self) -> Dict[str, Any]:
        return await self._request("GET", "/users")

    async def update_user(self, username: str, password: str, policy: Optional[str] = None) -> Dict[str, Any]:
        return await self._request("PUT", f"/users/{username}", json={"password": password, "policy": policy})

    async def delete_user(self, username: str) -> Dict[str, Any]:
        return await self._request("DELETE", f"/users/{username}")

    # =========================
    # BUCKETS
    # =========================
    async def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
        return await self._request("POST", "/buckets", json={"bucket_name": bucket_name})

    # =========================
    # POLICIES
    # =========================
    async def create_policy(
        self,
        name: str,
        bucket: str,
        prefix: str = "*",
        permissions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        return await self._request(
            "POST",
            "/policies",
            json={
                "name": name,
                "bucket": bucket,
                "prefix": prefix,
                "permissions": permissions or ["s3:PutObject"],
            },
        )

    # =========================
    # NOTIFICATIONS
    # =========================
    async def add_notification(self, bucket: str) -> Dict[str, Any]:
        return await self._request("POST", f"/buckets/{bucket}/notifications")

    async def list_notifications(self, bucket: str) -> Dict[str, Any]:
        return await self._request("GET", f"/buckets/{bucket}/notifications")

    async def remove_notifications(self, bucket: str) -> Dict[str, Any]:
        return await self._request("DELETE", f"/buckets/{bucket}/notifications")

    async def send_notification(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("POST", "/notifications", json=payload)

    # =========================
    # CLEANUP
    # =========================
    async def close(self):
        await self._client.aclose()
