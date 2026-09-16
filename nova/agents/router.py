"""Deterministic routing of completed customer-rule assessments."""

from nova.schemas import RoutingDecision, RuleValidation, ValidationResult


def _describe_issue(result: RuleValidation) -> str:
    found = result.found if result.found is not None else "Unavailable"
    return (
        f"{', '.join(result.fields)} [{result.status}]: "
        f"Found: {found}. Expected: {result.expected}. "
        f"Rule: {result.rule} Reason: {result.reason}"
    )


def route(validation: ValidationResult) -> RoutingDecision:
    """Prioritize uncertainty over mismatch; the Validator owns rule coverage."""
    # Frozen Pydantic models still allow their contained lists to be cleared.
    if not validation.results:
        raise ValueError("Cannot route an empty validation result")

    issue_descriptions: list[str] = []
    has_uncertainty = False
    for result in validation.results:
        if result.status == "MATCH":
            continue
        issue_descriptions.append(_describe_issue(result))
        if result.status == "UNCERTAIN":
            has_uncertainty = True
    details = "\n".join(issue_descriptions)

    if has_uncertainty:
        return RoutingDecision(
            outcome="HUMAN_REVIEW",
            reason=f"Human review is required because some rules could not be evaluated confidently.\n{details}",
        )
    if issue_descriptions:
        return RoutingDecision(
            outcome="AMENDMENT_REQUEST",
            reason=f"An amendment is required because customer rules were violated.\n{details}",
            amendment_request=f"Please amend the document to address these discrepancies:\n{details}",
        )
    return RoutingDecision(
        outcome="AUTO_APPROVE",
        reason="All reported customer-rule assessments match; no mismatches or uncertainties were reported.",
    )
