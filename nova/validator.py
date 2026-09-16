"""Apply customer rules with a model and enforce source uncertainty locally."""

import json
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from nova.config import Settings
from nova.model import ModelProvider, ModelRequest
from nova.prompts import VALIDATION_INSTRUCTIONS
from nova.schemas import CustomerRules, ExtractionResult, RuleValidation, ValidationResult


class _ReferencedAssessment(RuleValidation):
    source_field_indices: list[Annotated[int, Field(ge=0)]] = Field(
        description="Zero-based indices of all extracted fields used; empty if data is absent",
    )


class _ValidatorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    results: list[_ReferencedAssessment] = Field(min_length=1)


class Validator:
    def __init__(self, provider: ModelProvider, settings: Settings) -> None:
        self.provider = provider
        self.settings = settings

    def validate(self, extraction: ExtractionResult, rules: CustomerRules) -> ValidationResult:
        response = self.provider.generate(ModelRequest(
            model=self.settings.validator_model,
            instructions=VALIDATION_INSTRUCTIONS,
            text=json.dumps({
                "customer_rules": rules.text,
                "confidence_threshold": self.settings.confidence_threshold,
                "extracted_fields": [
                    {"index": index, **entry.model_dump()}
                    for index, entry in enumerate(extraction.fields)
                ],
            }, ensure_ascii=False),
            response_schema=_ValidatorResponse.model_json_schema(),
            max_output_tokens=self.settings.validator_max_output_tokens,
        ))
        parsed = _ValidatorResponse.model_validate_json(response)
        results = []
        for assessment in parsed.results:
            results.append(self._guard_sources(assessment, extraction))
        return ValidationResult(results=results)

    def _guard_sources(
        self, assessment: _ReferencedAssessment, extraction: ExtractionResult,
    ) -> RuleValidation:
        data = assessment.model_dump(exclude={"source_field_indices"})
        sources = []
        has_missing_value = False
        has_low_confidence = False
        for index in assessment.source_field_indices:
            if index >= len(extraction.fields):
                raise ValueError("Validator cited an extracted field index that does not exist")
            source = extraction.fields[index]
            sources.append(source)
            if source.value is None:
                has_missing_value = True
            if source.confidence < self.settings.confidence_threshold:
                has_low_confidence = True

        uncertainty = None
        if not sources:
            data["found"] = None
            uncertainty = "No extracted source was supplied for this assessment."
        else:
            # Display actual cited extraction values, not a model-invented summary.
            if len(sources) == 1:
                data["found"] = sources[0].value
            else:
                data["found"] = "\n".join(
                    f"{source.name}: {source.value if source.value is not None else 'Unavailable'}"
                    for source in sources
                )
            if has_missing_value:
                uncertainty = "Required source information is missing or unreadable."
            elif has_low_confidence:
                uncertainty = "Source extraction confidence is below the configured threshold."
        if uncertainty:
            data["status"] = "UNCERTAIN"
            data["reason"] = f"{uncertainty} Model assessment: {assessment.reason}"
        return RuleValidation.model_validate(data)
