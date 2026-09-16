# GoComet Nova --- Project Brief

## 1. Purpose

Build a small, reviewable proof of concept for **of the GoComet Nova
assignment**.

The POC processes **one trade document per pipeline run**. For the
primary demo, use a **Commercial Invoice**. The architecture should not
cross-document consistency, supplier amendment loops, or customer-system
connectors.

The product goal is to automate the routine portion of trade-document
review while surfacing uncertainty and discrepancies to the
Cargo/Control Group (CG) operator.

## 2. Scope

### In scope

A single uploaded PDF or image flows through:

`Upload -> Extractor -> Validator -> Router -> Storage -> Minimal UI / Query`

The POC must demonstrate:

1.  Uploading one trade document.
2.  Extracting required fields using a vision-capable LLM.
3.  Returning structured extraction results with field-level confidence
    and source evidence where practical.
4.  Validating extracted fields against a customer-specific
    **natural-language rule set**.
5.  Returning `MATCH`, `MISMATCH`, or `UNCERTAIN` per field.
6.  Routing the validation result to:
    -   `AUTO_APPROVE`
    -   `HUMAN_REVIEW`
    -   `AMENDMENT_REQUEST`
7.  Persisting pipeline state/results.
8.  Showing the pipeline result in a minimal UI.
9.  Supporting a simple grounded query over stored results.

## 3. Primary POC Document

Use a **Commercial Invoice** as the primary demo document.

The Extractor should identify fields present in a PDF or image and return a
structured collection of field entries. Explicitly look for the assignment's
eight target fields when present, without limiting extraction to this list:

-   consignee name
-   HS code
-   port of loading
-   port of discharge
-   Incoterms
-   description of goods
-   gross weight
-   invoice number

Within one model request, first discover all identifiable fields across the
document, then check these eight targets for omissions before returning output.
The checklist must not restrict discovery, fabricate absent values, or duplicate
an occurrence already extracted. It does not introduce a second extraction call.

The agreed output direction is a collection such as `fields: [...]`, where
each entry has a name, a text-or-null value, confidence, and optional source
evidence/page information. The structure of each entry is fixed; the list of
field names is driven by the document. Additional fields, such as country of
origin, do not require extending the schema.

The eight target fields guide extraction and evaluation; they are not mandatory
keys in the output. An absent field may be omitted from the collection. When
an identifiable field has an unreadable value, preserve it with a null value
and appropriate confidence. Never invent values to complete the target list.
An absent entry alone cannot distinguish absence in the document from an
extraction omission; the Validator must treat unavailable required information
as uncertain.

Preserve document wording and enough source context to interpret fields.
Do not silently equate ambiguous labels such as Buyer and Consignee, or
collapse repeated values with different meanings. Preserve the field label and,
when needed to distinguish occurrences, add document-supported context to `name`,
for example `Consignee / Address` and `Buyer / Address`. Use the existing `name`
property rather than a separate section property. Do not invent context merely
to force unique names; unambiguous labels need no added context. The Validator
must interpret these labels against the rules rather than rely on exact name
matching. Repeated names remain separate entries in the list, with source
evidence where available; the schema does not normalize aliases or group table
rows. The `fields` list is required but may be empty when no fields are identified.
An empty list does not imply that customer rules are satisfied.

Implementation status: `nova/schemas.py` implements this collection contract.
The Extractor and Validator services use the shared model-provider boundary.

The Extractor may also identify `document_type`, but do not create
separate extractor agents for each trade-document type in current.

## 4. Customer Rule Set

Use a plain-text / natural-language rule set for the POC.

Example customer: **RheinTech Distribution GmbH**

Rules:

1.  The consignee on the invoice must be RheinTech Distribution GmbH.
2.  The HS code must contain exactly 8 numeric digits.
3.  The port of loading must be either Chennai, India or Mumbai, India.
4.  The port of discharge must be Hamburg, Germany.
5.  Only FOB or CIF Incoterms are accepted.
6.  The description of goods must indicate that the shipment contains
    laptop computers.
7.  Gross shipment weight must be between 1,000 kg and 1,500 kg.
8.  The invoice number must start with `INV` and be followed by numeric
    characters.
9.  If a required field is missing or cannot be confidently evaluated,
    it must be marked `UNCERTAIN`; it must never be silently treated as
    a match.
10. If a field violates a rule, return `MISMATCH` with the found value,
    expected requirement, and concise reason.

Keep this rule set external to the Validator prompt/code so it can later
be replaced by customer-specific context.

## 5. Pipeline Architecture

### Extractor

**Responsibility:** Extract structured information from the uploaded
document.

**Input:** One PDF or image.

**Output:** Structured data containing each required field's value and
confidence. Include source evidence/page information where practical.

**Model direction:** Gemini 2.5 Pro, because this stage requires
vision/PDF understanding and structured extraction.

Important behavior:

-   Do not invent missing fields.
-   Schema-constrain output.
-   Preserve uncertainty.
-   Extraction failure is not a reason to repeatedly regenerate until a
    desirable value appears.

### Validator

**Responsibility:** Apply the customer's natural-language rules to the
extracted fields.

**Input:**

-   Extractor structured output.
-   Customer natural-language rule set.

**Output:** Per-field structured validation:

-   `MATCH`
-   `MISMATCH`
-   `UNCERTAIN`

For a mismatch include:

-   field
-   found value
-   expected rule/value
-   concise reason

For uncertainty include the reason the field cannot be safely validated.

Confidence is retained on extraction fields only. The Validator expresses its
own evaluation uncertainty through `UNCERTAIN` and a reason; it does not produce
or threshold a separate numeric confidence score. The Part 1 overview mentions
Validator confidence, but its detailed Validator requirements specify outcomes
and explanations. This is the agreed interpretation for this POC. The configured
confidence threshold applies only to cited extraction fields.

Evaluate every customer rule, not only the fields present in extraction data.
If information needed to evaluate a rule is null or absent, return `UNCERTAIN`
with a reason, regardless of any reported confidence. This also applies when
a rule references a field outside the eight extraction fields; never skip
the rule, invent the missing data, or silently treat it as a match.

For example, if a rule requires country of origin to be India but extraction
does not supply country of origin, report that rule as `UNCERTAIN` because
the necessary information is unavailable.

Validation results must identify the customer rule and relevant field(s),
preserving coverage when multiple rules apply to one field or a rule refers
to data absent from the extracted collection. Discovering additional document
fields is part of extraction; missing data during validation does not trigger
automatic re-extraction or changes to the schema.

**Model direction:** Gemini 2.5 Flash for the POC: bounded
rule-following / semantic comparison with lower expected cost and
latency than the extraction model.

### Router

**Responsibility:** Decide the next workflow outcome from Validator
output.

**Input:** Validator structured output.

**Output:**

-   `AUTO_APPROVE`
-   `HUMAN_REVIEW`
-   `AMENDMENT_REQUEST`

plus operator-friendly reasoning.

For this POC, **do not use an LLM for routing unless implementation
evidence shows it is necessary**. The decision policy is sufficiently
bounded to implement programmatically, with templates for human-readable
reasoning.

A reasonable initial policy is:

-   Any `UNCERTAIN` -\> `HUMAN_REVIEW`
-   Else any `MISMATCH` -\> `AMENDMENT_REQUEST`
-   Else -\> `AUTO_APPROVE`

Keep this policy isolated so it can later evolve without changing
extraction/validation.

## 6. Agent Communication and State

Model execution and pipeline orchestration are separate boundaries. A shared
`ModelProvider` accepts stage-supplied instructions, input text, an optional
document, model name, output schema, and token budget. The Extractor owns its
extraction prompt and local response validation; the Gemini provider owns SDK
calls and bounded technical retries. Future stages can reuse the same provider
contract with their own task details.

Add LangGraph after the Validator service works to connect the stages and manage
state/checkpoints. Provider selection does not replace LangGraph orchestration.

Use **structured handoffs**, not free-form agent-to-agent conversation.

The pipeline state should be explicit and serializable, for example:

-   document metadata
-   current pipeline stage
-   extraction result
-   validation result
-   routing decision
-   errors/retry metadata
-   timestamps

Use LangGraph for orchestration/checkpointing if it remains lightweight
for the POC.

Persist enough state so a technical crash does not require restarting
successful earlier stages. Resume from the last completed stage where
practical.

The graph is intentionally acyclic:

`Extractor -> Validator -> Router -> Storage`

`MISMATCH` and `UNCERTAIN` are valid business outcomes, **not reasons to
loop until validation succeeds**.

Retries should only cover transient technical failures and must have a
fixed maximum.

## 7. Structured Output and Tool Use

Use structured output for:

-   Extractor output.
-   Validator output.
-   Router/internal decision representation.

Do not use LLM tool/function calling in the workflow. All required
context is supplied directly to the pipeline.

Future customer knowledge-base or engagement-system access may use
tools/connectors, but that is outside this implementation.

## 8. Trust and Failure Handling

### Low-confidence extraction

A low-confidence required field must propagate as uncertainty and result
in human review rather than silent approval.

Do not solve uncertainty by repeatedly asking the Extractor until it
returns a high-confidence answer.

### Confidently wrong extraction

The POC does not claim that model confidence guarantees correctness.
Confidence thresholds must eventually be calibrated against labelled
data.

For evaluation, track cases where high-confidence extraction was wrong
rather than assuming model-reported confidence is calibrated.

### Technical failures

-   Bound transient retries.
-   Record failure stage and reason.
-   Preserve successful prior-stage outputs.
-   Make failures visible rather than silently swallowing them.
-   Bound token/output sizes and number of model calls per pipeline run.

## 9. Storage and Query

Use a simple queryable store such as SQLite for the POC unless
implementation constraints justify something else.

Persist enough information to answer questions such as:

-   How many documents were auto-approved?
-   How many required human review?
-   How many had mismatches?
-   Which fields most frequently failed validation?

The query layer may be simple. Correct grounding is more important than
sophistication.

## 10. Minimal UI

The UI should prioritize the CG operator's decision.

For one processed document, show:

-   uploaded/original document reference
-   extracted fields
-   confidence
-   source evidence where available
-   validation status per field
-   found vs expected for mismatches
-   uncertainty clearly highlighted
-   final routing decision
-   concise reasoning

Do not spend significant time on visual polish before the pipeline works
end-to-end.

## 11. Evaluation

### Offline

Maintain a labelled golden dataset of representative trade documents.

Track:

-   field-level extraction accuracy
-   per-class precision, recall, and F1 for Validator outcomes
-   routing decision correctness / per-class metrics where applicable

When production or manual testing reveals a failure, retain the document
and corrected expected output as a **failure/regression case** for
future model/prompt releases.

### Online / operational

North-star metric:

**Straight-Through Processing (STP) Rate:** percentage of documents
successfully processed end-to-end without human intervention.

Primary quality guardrail:

**False Auto-Approval Rate:** incorrect approvals per 1,000
auto-approved documents, estimated through audit/downstream feedback
where ground truth is available.

Supporting operational/business metrics include:

-   p95 end-to-end latency
-   pipeline failure rate
-   cost per document
-   median CG handling time for intervention cases

## 12. POC Test Cases

At minimum, keep deterministic demo fixtures for:

### Happy path

All extracted values satisfy the customer rules -\> `AUTO_APPROVE`.

### Mismatch path

Change one clearly readable field so it violates a customer rule, for
example `Incoterms = EXW` -\> `AMENDMENT_REQUEST`.

### Uncertain path

Use a deliberately ambiguous/poorly written required field so extraction
confidence falls below the configured threshold -\> `HUMAN_REVIEW`.

These three paths should be easy to rerun during development.

## 13. Engineering Priorities

Optimize for:

1.  Correctness and traceability.
2.  Clear contracts between stages.
3.  Small independently testable components.
4.  Easy local execution.
5.  Fast iteration for a time-boxed POC.
6.  Avoiding unnecessary abstractions.

Do not add functionality beyond the current project brief unless
requested.

## 14. Suggested Implementation Sequence

Treat these as separate reviewable features, not one large
implementation:

1.  Project skeleton + configuration.
2.  Domain schemas / structured contracts.
3.  Commercial Invoice upload/input handling.
4.  Extractor implementation.
5.  Extractor fixture/tests.
6.  Natural-language customer rule loading.
7.  Validator implementation.
8.  Validator fixture/tests.
9.  Router implementation.
10. Router tests for all three outcomes.
11. LangGraph orchestration/state.
12. Persistence/checkpointing.
13. End-to-end happy-path test.
14. Mismatch and uncertainty end-to-end tests.
15. Minimal UI.
16. Query layer.
17. Logging/metrics/eval harness.

The exact order may be adjusted when dependencies require it, but each
change should remain small and independently reviewable.
