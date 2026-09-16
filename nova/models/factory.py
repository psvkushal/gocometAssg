"""Select providers at the application boundary, independently for each stage."""

from nova.config import Settings
from nova.models.base import ModelProvider
from nova.models.gemini import GeminiProvider
from nova.models.openai import OpenAIProvider


def create_provider(name: str, settings: Settings) -> ModelProvider:
    if name == "gemini":
        return GeminiProvider(settings)
    if name == "openai":
        return OpenAIProvider(settings)
    raise ValueError(f"Unsupported provider: {name}")
