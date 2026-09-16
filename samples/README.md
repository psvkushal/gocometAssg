# Synthetic invoice fixtures

These one-page invoices contain no real shipment data. Each `.expected.json`
file records the expected extracted fields and routing outcome. Use the example
RheinTech customer rules in `rules/rheintech.txt`.

- `clean_invoice.pdf`: all eight fields satisfy the rules.
- `mismatch_invoice.pdf`: Incoterms are EXW, which requires an amendment.
- `missing_hs_invoice.pdf`: HS code is absent, which requires human review.

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

Local results: `data/live_suite_4e5cedc9.sqlite3`.
Full model outputs and check results: `data/live_suite_report.json`.
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

Local database: `data/user_live_2ca0962f.sqlite3`.
Full outputs: `data/user_live_report.json` (ignored by Git).
These three documents cover approval and mismatches; none is an uncertainty case.

## Image attempts — 2026-09-16

Inspected `data/sample01.jpeg` through `data/sample06.jpeg`: two handwritten
invoices and four photos of printed invoices. Each was submitted to the live
pipeline using Gemini 3.1 Pro Preview for extraction. All six requests failed
with HTTP 429 RESOURCE_EXHAUSTED: Google reported that the project's monthly
spending cap had been exceeded. No extraction or validation results were produced;
image accuracy and routing remain unverified.

Local checkpoints: `data/image_live_9424203d.sqlite3`.
Failure details and run IDs: `data/image_live_report.json` (ignored by Git).
Resume these runs after the project spend cap is resolved.

## Image retry results — 2026-09-16

After the spend-cap update, all six saved runs resumed and completed using
Gemini 3.1 Pro Preview for extraction and Gemini 3.6 Flash for validation.
No further quota errors occurred. The exact cause of the earlier billing block
was not independently established. GPT-5.4 nano has not been integrated.

| Image | Outcome | Mismatched assessments |
| --- | --- | --- |
| `data/sample01.jpeg` | AMENDMENT_REQUEST | 6 |
| `data/sample02.jpeg` | AMENDMENT_REQUEST | 4 |
| `data/sample03.jpeg` | AMENDMENT_REQUEST | 1 |
| `data/sample04.jpeg` | AMENDMENT_REQUEST | 1 |
| `data/sample05.jpeg` | AUTO_APPROVE | 0 |
| `data/sample06.jpeg` | AMENDMENT_REQUEST | 5 |

All images yielded 18 fields and completed result storage. The extracted names
and values for printed images 03–06 exactly matched the corresponding previously
reviewed PDF extractions. Images 03 and 04 flagged EXW; image 06 flagged HS code,
loading port, discharge port, gross weight, and invoice number. Amendment drafts
were present for all five amendment outcomes. Queries returned one approval,
zero human reviews, and five documents with mismatches.

Handwriting findings requiring review:

- Image 01 correctly preserved gross weight as 1680 Kg rather than copying the
  printed invoice's 1675.40 kg. It reported the five substantive violations plus
  a consignee mismatch for `Rhein Tech` versus `RheinTech`.
- Image 02 flagged EXW and smartphones instead of laptops, plus the same consignee
  spacing difference and a trailing period in the invoice number.
- Image 02's handwritten invoice number was extracted as `INV2028091602.` with
  confidence 0.93. The overwritten digit is visually ambiguous; this is not a
  verified exact transcription. The Validator flagged the period, not the digit.
- Whether to ignore company-name spacing and incidental punctuation needs an
  agreed rule. No normalization or prompt changes were made during testing.

These runs demonstrate completion, not uniformly verified handwriting accuracy.
No image produced HUMAN_REVIEW; reported confidence alone does not establish
correct transcription. Database and report paths are the same as the image
attempts above; the report now includes successful outputs and refreshed queries.

## Internal Validator comparison

GPT-5.4 nano, GPT-5.4 mini, and Gemini 3.6 Flash were tested on these same six saved
image extractions. See `docs/technical-writeup.md` for timings, outcome differences,
and nano's failure on reporting instructions. Full local output is in
`data/validator_comparison.json`. This comparison makes no new extraction calls.

## Reverted semantic-rule experiment

The semantic-equivalence rule change was reverted at the user's request. The
original consignee requirement is restored; company-name variants are not
explicitly permitted. The temporary experiment accepted `Rhein Tech` in both
handwritten samples, but those results do not represent the current rule set.
Historical diagnostic output remains in `data/semantic_rule_check.json`.

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
tests passed. The active configuration remains Gemini extraction + GPT-5.4 mini
validation. Local experiment reports: `data/nano_prompt_v2*.json`,
`data/nano_prompt_v3*.json`, `data/nano_prompt_final_check.json`,
`data/mini_prompt_v3_controls.json`, and `data/mini_restored_prompt_check.json`.
The comparison script now supports `--models` to select internal experiment models;
use a new output path for each prompt experiment to avoid reusing prior results.
