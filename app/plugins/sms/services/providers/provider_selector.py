from plugins.sms.services.providers.telenyx import TelenyxProvider
from plugins.sms.services.providers.base import BaseProvider

PROVIDERS: dict[str, type[BaseProvider]] = {
    "telenyx": TelenyxProvider,
    # add others like "twilio": TwilioProvider, "telnyx": TelnyxProvider
}

def get_provider(name: str, api_key: str | None = None) -> BaseProvider:
    """Factory function for selecting a communication provider."""
    provider_cls = PROVIDERS.get(name.lower())
    if not provider_cls:
        raise ValueError(f"Unsupported provider: {name}")
    return provider_cls(api_key)
