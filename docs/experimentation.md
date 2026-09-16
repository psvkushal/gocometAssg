# Experimentation

All paths below are relative to the repository root. Experiments were performed
on 2026-09-16. Local outputs and credentials under `test_samples/` and `.env` are ignored
by Git. The active setup now uses GPT-5.4 mini for both extraction and validation.

## Sample fixtures

These one-page invoices contain no real shipment data. Each `.expected.json`
file records the expected extracted fields and routing outcome. Use the example
RheinTech customer rules in `rules/rheintech.txt`.

- `clean_invoice.pdf`: all eight fields satisfy the rules.
- `mismatch_invoice.pdf`: Incoterms are EXW, which requires an amendment.
- `missing_hs_invoice.pdf`: HS code is absent, which requires human review.


## Pipeline context for the experiments

The three Router branches illustrate policy; the implementation returns one typed
`RoutingDecision` from a single Router node before proceeding to Storage.
Checkpoint and result tables share a SQLite file but serve different purposes.
The original document and completed outputs are retained in checkpoints, while
`review_results` holds completed reviews for queries. Saving an identical result
again is harmless; conflicting content under the same run ID is rejected.

Each stage receives a provider independently. Gemini extraction can therefore be
paired with GPT validation. Provider adapters own API transport, bounded retries,
and incomplete/refused-response handling. OpenAI uses the Responses API with
strict JSON schema; nullable optional schema properties become required nullable
properties only in the provider request. Pydantic validates the returned payload
against the unchanged domain contract.

Business mismatches never trigger re-extraction. Technical failures stop the graph;
resume executes pending work using current application model settings. The local
saved-run dropdown lists the latest checkpoint per run, including interrupted runs.
Listing scans checkpoint history, which is acceptable for this POC but is not a
paginated production index.

## Live verification — 2026-09-16

Extractor: `gemini-3.1-pro-preview`. Validator: `gemini-3.6-flash`.
All three documents were processed through the real model calls, LangGraph,
Router, and SQLite storage, with automatic retries disabled.

| Sample | Actual outcome | Checks |
| --- | --- | --- |
| `clean_invoice.pdf` | `AUTO_APPROVE` | Passed |
| `mismatch_invoice.pdf` | `AMENDMENT_REQUEST` | Passed |
| `missing_hs_invoice.pdf` | `HUMAN_REVIEW` | Passed |

All extracted names and values matched the corresponding expected fixture.
EXW produced an Incoterms mismatch and an amendment draft. Missing HS code
produced an UNCERTAIN assessment without a fabricated value. All completed
results were retrieved successfully from storage.

Queries over the isolated test database returned one approval, one human review,
and one document with mismatches; Incoterms was the only failing field (count 1).

Local results: `database/live_suite_4e5cedc9.sqlite3`.
Full model outputs and check results: `test_samples/live_suite_report.json`.
These local artifacts and credentials are ignored by Git.

To repeat manually, launch the UI with the model overrides above, upload each
PDF with the example rules, and compare against its expected JSON. Query counts
are cumulative, so use a fresh database to reproduce the counts above.

This is one live run per scenario, not a reliability measurement. The uncertainty
case tests missing data; blurry-document confidence and browser interaction were
not tested in this run. Project model defaults remain unchanged. Earlier attempts
were blocked by quota and unavailable 2.5 models; the models above succeeded.

## User-supplied invoices — 2026-09-16

The three synthetic PDFs in the repository root were also tested live with the
same models and RheinTech rules. Each produced 18 extracted fields; values were
reviewed against the PDF text, including the additional invoice details.

| Document | Actual outcome | Mismatches |
| --- | --- | --- |
| `01_invoice_valid.pdf` | `AUTO_APPROVE` | 0 |
| `02_invoice_incoterm_mismatch.pdf` | `AMENDMENT_REQUEST` | 1 |
| `03_invoice_multiple_rule_mismatches.pdf` | `AMENDMENT_REQUEST` | 5 |

The second document correctly flagged EXW. The third correctly flagged HS code
8471301A, loading port Kochi, discharge port Rotterdam, gross weight 1675.40 kg,
and invoice number PO20260916A. Both amendment drafts included every discrepancy.
Stored results were retrieved successfully. Queries returned one approval, zero
human reviews, and two documents with mismatches, with six distinct failing fields.

Local database: `database/user_live_2ca0962f.sqlite3`.
Full outputs: `test_samples/user_live_report.json` (ignored by Git).
These three documents cover approval and mismatches; none is an uncertainty case.

## Image attempts — 2026-09-16

Inspected `test_samples/sample01.jpeg` through `test_samples/sample06.jpeg`: two handwritten
invoices and four photos of printed invoices. Each was submitted to the live
pipeline using Gemini 3.1 Pro Preview for extraction. All six requests failed
with HTTP 429 RESOURCE_EXHAUSTED: Google reported that the project's monthly
spending cap had been exceeded. No extraction or validation results were produced;
image accuracy and routing could not be evaluated in that attempt.

Local checkpoints: `database/image_live_9424203d.sqlite3`.
Failure details and run IDs: `test_samples/image_live_report.json` (ignored by Git).
The following retry resumed these saved runs after the spend-cap update.

## Image retry results — 2026-09-16

After the spend-cap update, all six saved runs resumed and completed using
Gemini 3.1 Pro Preview for extraction and Gemini 3.6 Flash for validation.
No further quota errors occurred. The exact cause of the earlier billing block
was not independently established. These runs preceded the OpenAI provider integration.

| Image | Outcome | Mismatched assessments |
| --- | --- | --- |
| `test_samples/sample01.jpeg` | AMENDMENT_REQUEST | 6 |
| `test_samples/sample02.jpeg` | AMENDMENT_REQUEST | 4 |
| `test_samples/sample03.jpeg` | AMENDMENT_REQUEST | 1 |
| `test_samples/sample04.jpeg` | AMENDMENT_REQUEST | 1 |
| `test_samples/sample05.jpeg` | AUTO_APPROVE | 0 |
| `test_samples/sample06.jpeg` | AMENDMENT_REQUEST | 5 |

All images yielded 18 fields and completed result storage. The extracted names
and values for printed images 03–06 exactly matched the corresponding previously
reviewed PDF extractions. Images 03 and 04 flagged EXW; image 06 flagged HS code,
loading port, discharge port, gross weight, and invoice number. Amendment drafts
were present for all five amendment outcomes. Queries returned one approval,
zero human reviews, and five documents with mismatches.

Handwriting findings recorded during the initial image runs:

- Image 01 correctly preserved gross weight as 1680 Kg rather than copying the
  printed invoice's 1675.40 kg. It reported the five substantive violations plus
  a consignee mismatch for `Rhein Tech` versus `RheinTech`.
- Image 02 flagged EXW and smartphones instead of laptops, plus the same consignee
  spacing difference and a trailing period in the invoice number.
- Image 02's handwritten invoice number was extracted as `INV2028091602.` with
  confidence 0.93. At that stage the overwritten digit had not been independently
  confirmed; the later extractor comparison records the user's correction. The Validator flagged the period, not the digit.
- Whether to ignore company-name spacing and incidental punctuation needs an
  agreed rule. No normalization or prompt changes were made during testing.

These runs demonstrate completion, not uniformly verified handwriting accuracy.
No image produced HUMAN_REVIEW; reported confidence alone does not establish
correct transcription. Database and report paths are the same as the image
attempts above; the report now includes successful outputs and refreshed queries.

## Validator timing comparison

Run `scripts/compare_validators.py --report test_samples/image_live_report.json` with API
keys exported. This makes paid requests for GPT-5.4 nano, GPT-5.4 mini, and Gemini
3.6 Flash against identical saved extraction data and rules. It records elapsed
validator time and complete assessments in an ignored JSON report. Extraction is
excluded, so this measures the effect of changing only the Validator. Model-default
reasoning settings are used; retries are disabled. One call per document/model is
a small exploratory comparison, not a latency benchmark or calibrated accuracy
score. Existing Gemini outputs are a comparison reference, not ground truth.

### Measured results — 2026-09-16

| Validator | Median successful call | Results across six images |
| --- | --- | --- |
| GPT-5.4 nano | 5.33 s | 4 HUMAN_REVIEW, 1 AMENDMENT_REQUEST, 1 failed sample |
| GPT-5.4 mini | 5.06 s | 5 AMENDMENT_REQUEST, 1 AUTO_APPROVE |
| Gemini 3.6 Flash | 22.78 s | 5 AMENDMENT_REQUEST, 1 AUTO_APPROVE |

Mini matched the earlier reviewed Gemini mismatch fields and routing across all
six saved extractions. Its median validator latency was about 4.5 times lower
than the freshly measured Flash baseline. This does not imply a 4.5-times-faster
whole pipeline: Gemini extraction time is excluded.

Nano misinterpreted the rule file's reporting instructions as document
requirements, causing extra uncertainty on four samples, including the valid
invoice. It failed local validation on sample03 twice; the second request was a
manual diagnostic rerun after the comparison initially stopped, not an automatic
retry. Its median above excludes those two failed calls (5.81 s and 7.24 s).
The raw diagnostic response is retained only in the ignored comparison report.

Mini is the better candidate for the current prompts on this small sample.
All validators consumed the same Gemini extraction, so this experiment does not
measure transcription accuracy. The app was subsequently configured to use mini
for validation; the later extractor comparison includes the user's handwriting corrections.

## Reverted semantic-rule experiment

The semantic-equivalence rule change was reverted at the user's request. The
original consignee requirement is restored; company-name variants are not
explicitly permitted. The temporary experiment accepted `Rhein Tech` in both
handwritten samples, but those results do not represent the current rule set.
Historical diagnostic output remains in `test_samples/semantic_rule_check.json`.

The latest operator run inspected during this change (sample01.jpeg, run
48a5f617-fe21-4c6f-b603-68cc39d61590) spanned approximately 17.4 seconds between
checkpoints: 11.1 seconds in extraction and 6.2 seconds in validation. These are
checkpoint intervals including step overhead, not isolated API timings or a
controlled comparison against earlier runs.

## Nano prompt experiment — reverted

Tested two Validator prompt revisions distinguishing business requirements from
reporting instructions, including a worked example and final output check. Nano
still generated assessments for reporting instructions. On the final three-case
check it returned AUTO_APPROVE for the clean invoice, HUMAN_REVIEW for the clear
mismatch (incorrect routing), and HUMAN_REVIEW for the missing-HS-code invoice.
The expanded prompt also regressed mini on the clean control in one check.

At the user's request, stopped tuning and restored the original Validator prompt.
The restored mini setup passed all three controls: AUTO_APPROVE, AMENDMENT_REQUEST,
and HUMAN_REVIEW, with a median validator time of 5.09 seconds. All 50 offline
tests passed. At that point the active configuration remained Gemini extraction + GPT-5.4 mini
validation. Local experiment reports: `test_samples/nano_prompt_v2*.json`,
`test_samples/nano_prompt_v3*.json`, `test_samples/nano_prompt_final_check.json`,
`test_samples/mini_prompt_v3_controls.json`, and `test_samples/mini_restored_prompt_check.json`.
The comparison script now supports `--models` to select internal experiment models;
use a new output path for each prompt experiment to avoid reusing prior results.

## Extractor comparison — 2026-09-16

One fresh extraction call per model/document, identical source files and extraction
prompt, no retries. Model-default reasoning is used; OpenAI image detail is high.
The adapters use their respective native image/PDF input mechanisms. No Validator
calls are included in these timings. Full local results: `test_samples/extractor_comparison.json`.

| Document | GPT-5.4 mini | Gemini 3.1 Pro Preview |
| --- | --- | --- |
| `test_samples/sample01.jpeg` | 5.12 s | 10.55 s |
| `test_samples/sample02.jpeg` | 4.35 s | 8.09 s |
| `test_samples/sample03.jpeg` | 5.61 s | 8.08 s |
| `test_samples/sample04.jpeg` | 6.26 s | 13.39 s |
| `test_samples/sample05.jpeg` | 4.90 s | 13.25 s |
| `test_samples/sample06.jpeg` | 9.51 s | 7.95 s |
| `01_invoice_valid.pdf` | 4.68 s | 18.14 s |
| Median across seven documents | 5.12 s | 10.55 s |

All fourteen requests succeeded with 18 fields each. For four printed invoice
photos and one PDF, both models' field names and values exactly matched the
previously reviewed PDF reference extractions (90/90 entries per model). This
comparison does not score evidence snippets, page references, or confidence
calibration, and the small repeated-layout set is not representative of all trade
documents. Mini was faster on six of seven documents, but slower on sample06.

Handwritten sample01 exposed a name disagreement: mini returned `Rheim Tech
Distribution GmbH`, while Gemini returned `Rhein Tech Distribution GmbH`, both
with confidence 0.98. Mini also rendered the goods model as `A×14`, whereas Gemini
returned `Ax14`. The user subsequently confirmed that mini's readings of the disputed handwritten
values were correct. This is user-confirmed ground truth for these examples, not
an inference from the model's confidence. On sample02 mini read `INV 2028091602.`
(confidence 0.98), while Gemini read `INV2026091602.` (confidence 0.81).

Mini matched the printed references and was correct on the user-confirmed
handwritten disagreements. This small sample does not establish general accuracy. After the user confirmed mini's handwritten readings, both stages were switched
to GPT-5.4 mini at the user's request.
Reproduce with `scripts/compare_extractors.py DOCUMENT... --output NEW_REPORT.json`
with credentials exported; each invocation makes fresh paid calls.
