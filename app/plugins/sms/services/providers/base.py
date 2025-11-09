from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseProvider(ABC):
    """Abstract base class for communication providers."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    @abstractmethod
    async def send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message or request via provider."""
        pass

    @abstractmethod
    async def pull(self) -> Dict[str, Any]:
        """Fetch inbound messages, delivery reports, or queued items."""
        pass

    @abstractmethod
    async def balance(self) -> Dict[str, Any]:
        """Check account balance or credits."""
        pass

    def sanitize_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Optional helper to clean or standardize payload data."""
        return data
