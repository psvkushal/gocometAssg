"""Structured stage outputs, independent of model providers."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceEvidence(BaseModel):
    """A source reference when the extractor can identify one."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    page: int | None = Field(default=None, ge=1, description="One-based document page")
    snippet: str | None = Field(default=None, min_length=1, pattern=r"\S")


class ExtractedField(BaseModel):
    """A literal document value and the model's confidence in that value."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    name: str = Field(
        min_length=1, pattern=r"\S",
        description=(
            "Preserve the field label; when needed to distinguish occurrences, add "
            "document-supported context, e.g. 'Consignee / Address'. Do not invent "
            "context or guess equivalent labels. Names need not be unique."
        ),
    )
    value: str | None = Field(
        min_length=1,
        pattern=r"\S",
        description="Text as read, preserving units and leading zeros; null if missing or unreadable",
    )
    confidence: float = Field(
        ge=0, le=1, allow_inf_nan=False,
        description="Model-reported confidence, not a calibrated guarantee of correctness",
    )
    evidence: SourceEvidence | None = None


class ExtractionResult(BaseModel):
    """Document-driven fields; omission does not prove absence from the document."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    fields: list[ExtractedField] = Field(
        description="Discovered fields in order; repeated names are separate occurrences. May be empty.",
    )


NonBlankText = Annotated[str, Field(min_length=1, pattern=r"\S")]


class CustomerRules(BaseModel):
    """Natural-language rules and their source, supplied together to validation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    text: NonBlankText
    source: NonBlankText


class RuleValidation(BaseModel):
    """One rule assessment, including rules whose required data was not extracted."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    rule: NonBlankText = Field(description="Customer rule being evaluated; preserve its wording")
    fields: list[NonBlankText] = Field(
        min_length=1,
        description="Relevant field names, including context or names of unavailable fields",
    )
    status: Literal["MATCH", "MISMATCH", "UNCERTAIN"]
    found: NonBlankText | None = Field(
        description="Observed value(s), with field/context labels as needed; null when unavailable",
    )
    expected: NonBlankText = Field(description="Requirement stated by the customer rule")
    reason: NonBlankText = Field(description="Concise explanation supporting the outcome")
    @model_validator(mode="after")
    def require_uncertainty_for_missing_data(self) -> Self:
        # Missing information is a business uncertainty, not proof of a violation.
        if self.found is None and self.status != "UNCERTAIN":
            raise ValueError("Unavailable found values require UNCERTAIN status")
        return self


class ValidationResult(BaseModel):
    """Rule assessments; the Validator is instructed to cover every supplied rule."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    results: list[RuleValidation] = Field(
        min_length=1,
        description="Assess every customer rule; never omit a rule because its data is missing",
    )


class RoutingDecision(BaseModel):
    """Workflow outcome and explanation; producing a decision performs no action."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    outcome: Literal["AUTO_APPROVE", "HUMAN_REVIEW", "AMENDMENT_REQUEST"]
    reason: NonBlankText
    amendment_request: NonBlankText | None = None

    @model_validator(mode="after")
    def check_amendment_request(self) -> Self:
        if self.outcome == "AMENDMENT_REQUEST" and self.amendment_request is None:
            raise ValueError("AMENDMENT_REQUEST requires a draft")
        if self.outcome != "AMENDMENT_REQUEST" and self.amendment_request is not None:
            raise ValueError("Only AMENDMENT_REQUEST may include a draft")
        return self
