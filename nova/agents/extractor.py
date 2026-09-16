"""Extraction behavior composed with an interchangeable model provider."""

from nova.config import Settings
from nova.documents import DocumentInput
from nova.models.base import ModelProvider, ModelRequest
from nova.agents.prompts import EXTRACTION_INSTRUCTIONS
from nova.schemas import ExtractionResult


class Extractor:
    def __init__(self, provider: ModelProvider, settings: Settings) -> None:
        self.provider = provider
        self.settings = settings

    def extract(self, document: DocumentInput) -> ExtractionResult:
        if not document.content or len(document.content) > self.settings.max_document_bytes:
            raise ValueError("Document must be non-empty and within the configured byte limit")
        response = self.provider.generate(ModelRequest(
            model=self.settings.extractor_model,
            instructions=EXTRACTION_INSTRUCTIONS,
            text="Extract the fields from this document.",
            document=document,
            response_schema=ExtractionResult.model_json_schema(),
            max_output_tokens=self.settings.extractor_max_output_tokens,
        ))
        return ExtractionResult.model_validate_json(response)
