from plugins.sms.services.providers.base import BaseProvider
from typing import Dict, Any
import httpx,os


class TelenyxProvider(BaseProvider):
    """Telenyx communication gateway implementation."""

    BASE_URL = "https://api.telnyx.com/v2"
    
    def __init__(self, api_key: str | None = None):
        self.api_key = os.environ.get("TELENYX_API",api_key)

    def sanitize_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Optional helper to clean or standardize payload data."""
        data["messaging_profile_id"]=os.environ.get("TELENYX_MESSAGE_PROFILE_ID",None) 
        return data
    async def send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/messages",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=self.sanitize_payload(payload),
                timeout=10
            )
            resp.raise_for_status()
            return resp.json()

    async def pull(self) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/messages/inbound",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            resp.raise_for_status()
            return resp.json()

    async def balance(self) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/balance",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            # {'data': {'currency': 'USD', 'frozen': '0.00', 'credit_limit': '0.00', 'pending': '0.00', 'balance': '2.99', 'available_credit': '2.99', 'record_type': 'balance'}}
            return data.get("data",{})
