"""Load configuration explicitly at the application boundary."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None = field(default=None, repr=False)
    openai_api_key: str | None = field(default=None, repr=False)
    extractor_provider: str = "gemini"
    validator_provider: str = "gemini"
    extractor_model: str = "gemini-2.5-pro"
    validator_model: str = "gemini-2.5-flash"
    confidence_threshold: float = 0.8
    max_retries: int = 2
    max_document_bytes: int = 10 * 1024 * 1024
    model_timeout_ms: int = 120_000
    extractor_max_output_tokens: int = 8192
    validator_max_output_tokens: int = 8192
    storage_path: Path = Path("data/nova.sqlite3")

    def __post_init__(self) -> None:
        for name in ("extractor_provider", "validator_provider"):
            if getattr(self, name) not in {"gemini", "openai"}:
                raise ValueError(f"{name} must be gemini or openai")
        for name in ("extractor_model", "validator_model"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty model name")
        if (
            isinstance(self.confidence_threshold, bool)
            or not isinstance(self.confidence_threshold, (int, float))
            or not math.isfinite(self.confidence_threshold)
            or not 0 <= self.confidence_threshold <= 1
        ):
            raise ValueError("confidence_threshold must be between 0 and 1")
        if type(self.max_retries) is not int or self.max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")
        if type(self.max_document_bytes) is not int or self.max_document_bytes <= 0:
            raise ValueError("max_document_bytes must be a positive integer")
        for name in ("model_timeout_ms", "extractor_max_output_tokens", "validator_max_output_tokens"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.storage_path, Path) or self.storage_path == Path("."):
            raise ValueError("storage_path must be a file path")


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read environment variables without loading files or creating directories."""
    env = os.environ if environ is None else environ
    defaults = Settings()
    try:
        threshold = float(env.get("NOVA_CONFIDENCE_THRESHOLD", str(defaults.confidence_threshold)))
    except ValueError:
        raise ValueError("NOVA_CONFIDENCE_THRESHOLD must be a number between 0 and 1") from None
    try:
        retries = int(env.get("NOVA_MAX_RETRIES", str(defaults.max_retries)))
    except ValueError:
        raise ValueError("NOVA_MAX_RETRIES must be a non-negative integer") from None
    storage_path = env.get("NOVA_STORAGE_PATH", str(defaults.storage_path)).strip()
    try:
        max_document_bytes = int(env.get("NOVA_MAX_DOCUMENT_BYTES", str(defaults.max_document_bytes)))
    except ValueError:
        raise ValueError("NOVA_MAX_DOCUMENT_BYTES must be a positive integer") from None
    if not storage_path:
        raise ValueError("NOVA_STORAGE_PATH must be a file path")
    model_limits = {}
    for name in ("model_timeout_ms", "extractor_max_output_tokens", "validator_max_output_tokens"):
        env_name = f"NOVA_{name.upper()}"
        try:
            model_limits[name] = int(env.get(env_name, str(getattr(defaults, name))))
        except ValueError:
            raise ValueError(f"{env_name} must be a positive integer") from None
    return Settings(
        openai_api_key=env.get("OPENAI_API_KEY", "").strip() or None,
        extractor_provider=env.get("NOVA_EXTRACTOR_PROVIDER", defaults.extractor_provider).strip(),
        validator_provider=env.get("NOVA_VALIDATOR_PROVIDER", defaults.validator_provider).strip(),
        gemini_api_key=env.get("GEMINI_API_KEY", "").strip() or None,
        extractor_model=env.get("NOVA_EXTRACTOR_MODEL", defaults.extractor_model).strip(),
        validator_model=env.get("NOVA_VALIDATOR_MODEL", defaults.validator_model).strip(),
        confidence_threshold=threshold,
        max_retries=retries,
        max_document_bytes=max_document_bytes,
        storage_path=Path(storage_path).expanduser(),
        **model_limits,
    )
