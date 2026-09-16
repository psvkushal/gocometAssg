# Known Limitations and Deferred Capabilities

This document records deliberate limits of the current POC and topics to revisit.
It does not replace [PROJECT_BRIEF.md](PROJECT_BRIEF.md) or authorize additional
scope. Part 2 of the assignment remains excluded.

Currently, configuration, stage output schemas, document/rule loading, the Gemini
Extractor, Validator service, and deterministic Router are implemented.
The LangGraph core-stage workflow and durable SQLite checkpoints are implemented.
Queryable SQLite result storage and a bounded command-line question interface
are implemented, along with a minimal Streamlit operator UI.
Behaviors described below as planned are not yet implemented.

## Operator UI

The local Streamlit screen accepts one document, editable natural-language rules,
and explicit process/load/resume actions. New runs receive UUIDs automatically
from `PipelineInput`, including runs created outside the UI. It shows saved
stage outputs, original-document download, decisions, amendment drafts, and the
supported stored-result queries. Processing failures are surfaced without raw
provider payloads; partial outputs remain visible when checkpoints are available.
The initial UI shows a running indicator and the saved stage after execution,
not live per-stage progress. There is no authentication, multi-user isolation,
run browser, inline PDF viewer, or email sending.

UI tests use Streamlit AppTest with a fake model provider to exercise upload,
processing, query, and failure/resume flows. Live model quality and browser-level
visual behavior remain unverified. Rule edits affect new runs only; resume uses
the original saved rules and document.

## Pipeline persistence and recovery

The checkpointed graph runs Extractor -> Validator -> Router -> Storage.
It carries a run ID, input document/rules, completed stage outputs, and
the last completed stage. State can be serialized, and streaming exposes stage
updates. Technical errors propagate and stop downstream execution; the graph
does not add retries on top of provider retries.

`open_pipeline` connects a SQLite checkpointer. Its start/resume helpers use the
run ID as the LangGraph thread ID, save checkpoints synchronously between stages,
and reject starting an existing run. Resume uses saved document/rule inputs and
completed outputs; completed runs return their saved result without model calls.
Failed task details can be inspected from the persisted snapshot.

Recovery is at stage boundaries, not exactly-once model execution. A process exit
after an API response but before its checkpoint can require repeating that stage.
Tests reopen the database and recreate services after exceptions; hard process
termination and power-loss scenarios have not been tested. Only one local caller
should operate on a run at a time; start's duplicate-ID check is not a concurrent
reservation. Resume uses the currently supplied services, so model/configuration
version pinning and migrations are not implemented. Exact SDK retry counts are
not yet recorded; task errors and completed stage outputs are persisted.

The Storage stage writes a separate `review_results` table in the same database.
It saves all three outcomes, the rules used, extraction and validation results,
decision/reason/draft, filename, mismatch presence, and a UTC save timestamp.
The run ID links back to the original document bytes in checkpoints. Repeated
identical saves do not duplicate or overwrite a result; conflicting results for
an existing run ID are rejected. Storage failures leave that stage resumable.
The query interface supports the four question types in the brief using fixed
read-only SQL templates. It answers across all stored completed results; date
ranges, customer filters, arbitrary question phrasing, and in-progress/failed-run
queries are not supported. Unsupported questions fail explicitly rather than
silently dropping filters. Field-frequency counts use exact saved field labels
and count each field once per document with a mismatch; aliases are not merged.
Uncertainty is separate from mismatch. No query model or generated SQL is used.

Checkpoints completed under the earlier three-stage graph are not automatically
backfilled into result tables. No checkpoint/schema migration tooling exists yet.

## Extractor verification

The Extractor now receives an interchangeable `ModelProvider`. Gemini is the only
live provider implementation; fake providers are used in tests. Other providers
need their own adapter, but do not require rewriting extraction behavior.
Discovery followed by a target-field checklist happens within one prompt; its
effect on real-document coverage still needs evaluation.

Extractor contract tests use a fake model provider to check request preparation
and local response validation without API calls. Separate Gemini provider tests
were removed to avoid duplicating SDK behavior. Retry configuration and the
blocked/truncated-response guard currently have no automated integration coverage.
Live model availability, provider acceptance of the schema, and extraction quality
on real documents have not yet been verified. The brief's model name remains
configurable; there is no automatic model fallback.

The request has a configurable per-attempt timeout and output-token budget.
Transient HTTP failures and SDK-supported timeout/connection failures may retry
within the configured attempt limit. Malformed, blocked, or truncated output
fails without automatic re-extraction. With SQLite checkpointing enabled, failed
task errors are retained and an explicit resume can retry the failed stage.

## Customer rules requiring information absent from extraction

The Validator requests source indices for each assessment and checks cited entries
for null values and confidence below the configured threshold. Missing references
produce uncertainty; invalid indices cause a technical error. Displayed found
values come from the cited extraction entries. Validator evaluation uncertainty
is expressed through status and reason, without a separate confidence score. These guards do not prove that the model selected the right
sources or cited every relevant occurrence.

Complete coverage of the natural-language rule set is currently prompt-driven,
not deterministically verified. The model may omit a rule or select unrelated
high-confidence evidence. Real evaluation must include these failure cases before
trusting approvals. Stable rule preparation/identifiers remain deferred below.

A customer rule may need information absent from the extracted collection.
For example, "Country of origin must be India" is uncertain if extraction does
not supply country of origin. Absence in output does not prove absence in the
original document: the Extractor may have missed it.

**Planned POC handling:** The Validator must evaluate every rule and report
`UNCERTAIN` when the required information is unavailable. Results must identify
the rule and relevant field(s). The Router must send uncertainty to
`HUMAN_REVIEW`. Missing data must not cause a rule to be skipped, treated as a
match, or trigger automatic re-extraction. This fallback is required POC work.

**Deferred:** Rule-driven follow-up extraction and automatic re-extraction to
resolve missing data. Ordinary discovery of additional document fields is
part of the agreed extraction design and does not require a schema extension.

## Stable customer rules: revisit later

Customer rules are expected to change infrequently. Revisit whether loading or
preparing the same rules for every run is unnecessary once the Validator works.
Possible options include reusing loaded rule text, preparing a reviewed rule
representation with stable identifiers, and provider prompt caching where useful.
These are investigation topics, not approved implementation steps.

Any reuse must be scoped to the customer and rule version/content so changes
invalidate stale context. Keep the natural-language source authoritative and
preserve every rule's meaning and coverage. Do not silently convert the entire
rule set into hardcoded business logic. Reusing rule context does not mean
reusing validation decisions for different documents.

## Field naming, repetition, and completeness

A flexible collection does not by itself resolve aliases, ambiguous labels,
repeated line-item values, or conflicting values within one document. Buyer
and Consignee, for example, must not automatically be treated as equivalent.

**Current handling:** The schema description allows document-supported context
in `name`, such as `Consignee / Address`, when needed to distinguish fields.
There is no separate section property or uniqueness requirement. The
Extractor is instructed to supply that context without inventing it; schema validation
cannot verify whether a name is grounded in the document. A list retains
repeated occurrences, with optional source evidence for context. The schema
does not normalize aliases, group table rows, or establish that extraction is
exhaustive. An empty collection is valid structured output, not an approval.
Full table reconstruction and a general field ontology have not been agreed
as POC requirements.

## Schema validity does not establish factual correctness

The schema checks structure, types, and confidence bounds. It cannot establish
that an extracted value actually appears in the document or that a source
snippet is accurate. Evidence is optional and is not independently verified.

**Current limit:** A confidently wrong value can pass schema validation.
Model-reported confidence is not calibrated; the configured threshold is
provisional.

**Planned POC handling:** Preserve missing values and uncertainty, provide source
evidence where practical, and evaluate against labelled examples as described in
the brief. Calibration and stronger source verification need additional data
and evaluation before relying on confidence for production decisions.

## Single-document scope

The input loader currently accepts PDF, PNG, and JPEG files up to a configurable
10 MiB default. It checks extensions and initial file signatures, not full file
integrity, encryption, page count, or image dimensions. Passing these checks
does not guarantee that a provider can read the document. Other image formats
and richer document checks are not implemented. This is a local POC limit,
not a claim about any model provider's upload limit.

**Deferred:** Multi-document shipment orchestration and cross-document
consistency checks. A result for one document cannot establish consistency
across a shipment's invoice, packing list, and bill of lading.

**Planned POC handling:** Process one PDF or image per run, with a Commercial
Invoice as the primary demo document.

## External workflows and production infrastructure

**Deferred:** Inbox triggers, supplier email sending, customer-system connectors,
autonomous tool calling, dynamic agent loops, long-term memory, and
production-scale infrastructure.

**Planned POC handling:** Use uploaded documents, an external natural-language
rule file, explicit stage handoffs, and simple local persistence. Part 1's
amendment-request drafting and grounded natural-language queries remain in
scope; drafting a request does not imply sending it.

Update this document when a limitation is resolved or a new deliberate scope
decision is agreed with the human developer.

## GPT validator comparison

GPT-5.4 nano can interpret rule-file instructions 9 and 10 (uncertainty handling
and mismatch reporting) as independent document requirements. In the live
comparison this produced extra UNCERTAIN assessments and, on a printed invoice,
MATCH assessments with null found values rejected by the existing domain
validator. Strict JSON schema constrains shape, not these semantic invariants.
The comparison records failures; it does not silently coerce or retry them.
Prompt/rule separation should be evaluated as a separate change before relying
on nano. Company-name whitespace and incidental punctuation tolerance remain
unspecified. See `docs/technical-writeup.md` for comparison scope/results.

The saved-document selector scans checkpoint history and lists runs from the
configured database only. Separate live-test databases are not merged into the
operator database. Provider/model settings are not stored with older checkpoints;
resuming uses current internal configuration.
