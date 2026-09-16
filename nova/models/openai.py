"""OpenAI Responses adapter shared by extraction and validation."""

from base64 import b64encode
from copy import deepcopy

from openai import OpenAI

from nova.config import Settings
from nova.models.base import ModelRequest, ModelResponseError


def strict_schema(schema: dict) -> dict:
    """Require nullable optional properties for OpenAI, preserving domain schemas."""
    result = deepcopy(schema)

    def visit(node):
        if isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object":
                node["required"] = list(node.get("properties", {}))
                node["additionalProperties"] = False
            for value in node.values():
                visit(value)

    visit(result)
    return result


class OpenAIProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, request: ModelRequest) -> str:
        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI requests")
        content = [{"type": "input_text", "text": request.text}]
        if request.document is not None:
            document = request.document
            encoded = b64encode(document.content).decode("ascii")
            data_url = f"data:{document.media_type};base64,{encoded}"
            if document.media_type == "application/pdf":
                content.append({"type": "input_file", "filename": document.filename,
                                "file_data": data_url})
            else:
                content.append({"type": "input_image", "image_url": data_url, "detail": "high"})
        with OpenAI(api_key=self.settings.openai_api_key,
                    timeout=self.settings.model_timeout_ms / 1000,
                    max_retries=self.settings.max_retries) as client:
            response = client.responses.create(
                model=request.model, instructions=request.instructions,
                input=[{"role": "user", "content": content}],
                text={"format": {"type": "json_schema", "name": "stage_output",
                                 "strict": True, "schema": strict_schema(request.response_schema)}},
                max_output_tokens=request.max_output_tokens, store=False,
            )
        if response.status != "completed":
            raise ModelResponseError("OpenAI response was incomplete or failed")
        for item in response.output:
            for part in getattr(item, "content", []):
                if part.type == "refusal":
                    raise ModelResponseError("OpenAI refused the request")
        if not response.output_text or not response.output_text.strip():
            raise ModelResponseError("OpenAI returned no JSON text")
        return response.output_text
