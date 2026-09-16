# AGENTS.md --- Instructions for Codex Working on GoComet Nova current

This file contains **instructions for the coding agent (Codex)**. It
does not describe the Nova runtime agents.

Read `PROJECT_BRIEF.md` before making implementation decisions.

## Assignment Reference and Scope

The original assignment is
[`GoComet-AI-Engineer-DAW-Assignment.docx.pdf`](GoComet-AI-Engineer-DAW-Assignment.docx.pdf).
Use **Part 1 only** as reference for the project's background and deliverables.
**Ignore Part 2** when planning, implementing, or evaluating this project unless
the human developer explicitly expands the scope.

`PROJECT_BRIEF.md` defines the agreed implementation scope. If Part 1 introduces
a requirement that conflicts with or materially expands that scope, flag it for
discussion before implementing it.

Part 1 already includes amendment-request drafting and basic natural-language
queries over stored results; these should not be excluded merely because Part 2
also discusses them. Part 2's inbox triggers, multiple attachments per shipment,
cross-document validation, and email workflow remain outside the current scope.

These repository documents guide development. Do not load them as runtime
Extractor or Validator prompts; keep runtime prompts and customer rules separate.

## Core Working Agreement

The human developer wants to understand and review the code while it is
being built.

**Do not implement the whole project in one pass.**

Work in **atomic, feature-sized changes**.

For every feature:

1.  Inspect the existing code relevant to that feature.
2.  Explain what you intend to change and why.
3.  State the files you expect to add or modify.
4.  Implement **only that feature**.
5.  Run the smallest relevant tests/checks.
6.  Summarize:
    -   what changed
    -   why
    -   how to test it
    -   any trade-offs or open questions
7.  Stop and wait for human review before beginning the next feature.

Do not silently continue into the next planned feature.

## Atomic Change Rule

One change should have one clear purpose and should be understandable as
one commit.

Good examples:

-   Add Pydantic schemas for extraction output.
-   Add Gemini Extractor service behind an interface.
-   Add customer-rule file loading.
-   Add Validator structured-output schema.
-   Add deterministic Router policy.
-   Add SQLite persistence for pipeline state.

Bad examples:

-   "Build the backend."
-   Add Extractor + Validator + Router + UI together.
-   Refactor unrelated files while adding a feature.
-   Introduce a framework abstraction that is not needed by the current
    feature.

If a requested feature is too large, split it into smaller reviewable
steps and propose the split before coding.

## Do Not Overbuild

This is **current**.

The current pipeline processes **one trade document per run**.

Do not implement without explicit approval:

-   multi-document shipment orchestration
-   cross-document consistency
-   email ingestion
-   supplier email sending
-   customer knowledge-base connectors
-   engagement-platform connectors
-   autonomous tool calling
-   dynamic agent loops
-   long-term memory
-   elaborate microservices
-   production-scale infrastructure

Prefer the smallest implementation that demonstrates the required
behavior cleanly.

## Architecture Constraints

Keep stage boundaries explicit:

`Extractor -> Validator -> Router -> Storage`

Each stage must have typed/structured input and output.

Do not pass unstructured conversational history between runtime agents
when a typed object is sufficient.

### Extractor

-   Accept one PDF or image.
-   Use a vision-capable model.
-   Produce schema-constrained structured output.
-   Use a document-driven collection of named field entries; keep each entry
    structured, without restricting field names to eight fixed properties.
-   The eight target fields in `PROJECT_BRIEF.md` guide extraction when present,
    but are not mandatory output keys. Preserve additional discovered fields.
-   Add document-supported context to `name` when needed to distinguish fields,
    e.g. `Consignee / Address`. Keep simple labels when sufficient; do not invent
    context or force unique names. Keep repeated occurrences in the list.
-   Absent fields may be omitted; identifiable fields with unreadable values
    should retain a null value. Never infer document absence from omission alone.
-   Include confidence.
-   Include source evidence/page information where practical.
-   Never invent a value simply to satisfy the schema.

### Validator

-   Receive Extractor output plus the customer natural-language rule
    set.
-   Produce per-field `MATCH`, `MISMATCH`, or `UNCERTAIN`.
-   Evaluate every customer rule, including rules whose needed data is absent
    from extraction. Report unavailable information as `UNCERTAIN`, and identify
    the rule and relevant field(s); never silently skip a rule.
-   A mismatch must include found vs expected.
-   Interpret field names and their document context against the natural-language
    rules; do not depend on exact name matching or assume ambiguous labels agree.
-   Low-confidence / insufficient-evidence cases must remain uncertain.
-   Do not turn uncertainty into a match merely to complete the
    pipeline.

### Router

For the current POC, prefer deterministic program logic over an LLM.

Initial policy:

-   `UNCERTAIN` present -\> `HUMAN_REVIEW`
-   else `MISMATCH` present -\> `AMENDMENT_REQUEST`
-   else -\> `AUTO_APPROVE`

Keep routing policy isolated and testable.

## Agent Loops and Retries

The graph is acyclic.

Do **not** retry extraction because the Validator returned `MISMATCH` or
`UNCERTAIN`.

Those are valid business results.

Retries are permitted only for transient technical failures such as rate
limits/timeouts, and must be bounded.

Never create an unbounded model/tool loop.

## State and Crash Recovery

Pipeline state should be explicit and serializable.

When orchestration/checkpointing is added:

-   record the last successfully completed stage
-   persist completed stage outputs
-   resume rather than recompute where practical
-   record technical errors and retry counts

Do not add crash-recovery complexity before the core stage contracts
work.

## Model and Provider Isolation

Model/provider-specific code should be behind small boundaries so model
choice can be changed without rewriting business logic.

Do not scatter Gemini SDK calls throughout domain logic.

Configuration such as model names, API keys, confidence thresholds,
retry limits, and paths must not be hardcoded throughout the codebase.

Never commit secrets.

## Natural-Language Rules

The POC intentionally uses a **natural-language customer rule file**.

Do not convert the entire rule set into hardcoded Python/YAML validation
logic unless explicitly requested.

The purpose of the Validator POC is to demonstrate applying
customer-written rules to extracted structured data.

Keep the rule source replaceable so future connectors can supply it.

## Testing Philosophy

Every feature should add the smallest useful tests.

Prefer deterministic tests around:

-   schemas
-   rule loading
-   Router behavior
-   persistence
-   orchestration transitions

LLM-dependent behavior should be testable through fixtures/mocks where
possible so ordinary tests do not consume API credits.

Maintain three end-to-end scenarios:

1.  Happy path -\> `AUTO_APPROVE`
2.  Clear mismatch -\> `AMENDMENT_REQUEST`
3.  Low-confidence/uncertain field -\> `HUMAN_REVIEW`

When a real failure is discovered and fixed, add it as a regression
fixture/test where practical.

## Observability

Prefer structured logging.

Useful fields include:

-   pipeline/run ID
-   document ID
-   stage
-   duration
-   model used
-   retry count
-   outcome
-   error category

Do not log API keys or sensitive credentials.

Avoid logging full documents/model prompts by default unless
deliberately enabled for local POC debugging.

## Dependency Discipline

Before adding a dependency:

1.  Check whether the standard library or an existing dependency is
    sufficient.
2.  Explain why the new dependency is needed.
3.  Avoid adding multiple libraries that solve the same problem.

Use LangGraph when orchestration/checkpointing is implemented, as
described in the project brief, but do not introduce it merely to call
one function from another.

## Code Quality

Prefer:

-   simple readable Python
-   type hints
-   small functions/classes
-   explicit schemas
-   dependency injection at model/storage boundaries where useful
-   descriptive names
-   comments for *why*, not obvious *what*

Avoid:

-   speculative abstractions
-   giant service classes
-   hidden global state
-   deeply nested control flow
-   broad exception swallowing
-   magic constants spread across files

## Handling Ambiguity

If a product/architecture decision is not specified and materially
changes the design, **ask before implementing it**.

If the choice is local, reversible, and low-impact, choose the simplest
option and state the assumption in the feature summary.

useful.

## Definition of Done for an Atomic Feature

A feature is ready for review when:

-   its stated scope is implemented
-   relevant tests/checks pass
-   no unrelated functionality was added
-   changed files are summarized
-   manual verification steps are provided when relevant
-   known limitations are stated

Then **stop and wait for review**.

## First Action

Before writing code:

1.  Read `PROJECT_BRIEF.md`.
2.  Inspect the repository.
3.  Report the current repository state.
4.  Propose the **first atomic feature** and the files it would touch.
5.  Wait for approval before implementing it.
