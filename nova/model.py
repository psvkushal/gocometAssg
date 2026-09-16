"""Shared model-provider contract, independent of pipeline stages."""

from dataclasses import dataclass
from typing import Any, Protocol

from nova.documents import DocumentInput


@dataclass(frozen=True)
class ModelRequest:
    model: str
    instructions: str
    text: str
    response_schema: dict[str, Any]
    max_output_tokens: int
    document: DocumentInput | None = None


class ModelProvider(Protocol):
    def generate(self, request: ModelRequest) -> str:
        """Return complete JSON text; propagate technical failures with bounded retries."""
        ...


class ModelResponseError(ValueError):
    """A provider did not return a complete response."""
