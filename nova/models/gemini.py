"""Reusable Gemini provider; no extraction or validation business logic."""

from google import genai
from google.genai import types

from nova.config import Settings
from nova.model import ModelRequest, ModelResponseError


class GeminiProvider:
    """Implements ModelProvider for any stage requesting structured Gemini output."""

    def __init__(self, settings: Settings, *, client: genai.Client | None = None) -> None:
        self.settings = settings
        self._client = client

    def generate(self, request: ModelRequest) -> str:
        """An injected client belongs to its caller; otherwise create and close one."""
        if self._client is not None:
            return self._generate(request, self._client)
        if not self.settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini requests")
        with genai.Client(api_key=self.settings.gemini_api_key, vertexai=False) as client:
            return self._generate(request, client)

    def _generate(self, request: ModelRequest, client: genai.Client) -> str:
        settings = self.settings
        parts = [types.Part.from_text(text=request.text)]
        if request.document is not None:
            parts.append(types.Part.from_bytes(
                data=request.document.content, mime_type=request.document.media_type,
            ))
        response = client.models.generate_content(
            model=request.model,
            contents=types.Content(role="user", parts=parts),
            config=types.GenerateContentConfig(
                system_instruction=request.instructions,
                response_mime_type="application/json",
                response_json_schema=request.response_schema,
                max_output_tokens=request.max_output_tokens,
                candidate_count=1,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                http_options=types.HttpOptions(
                    timeout=settings.model_timeout_ms,
                    retry_options=types.HttpRetryOptions(
                        attempts=settings.max_retries + 1,
                        http_status_codes=[408, 429, 500, 502, 503, 504],
                    ),
                ),
            ),
        )
        if not response.candidates or response.candidates[0].finish_reason != types.FinishReason.STOP:
            raise ModelResponseError("Model response did not finish normally; response may be blocked or truncated")
        text = response.text
        if not text or not text.strip():
            raise ModelResponseError("Model returned no JSON text")
        return text
