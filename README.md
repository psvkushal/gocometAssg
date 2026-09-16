# GoComet Nova

A Python proof of concept for reviewing one trade document per run. See
[PROJECT_BRIEF.md](PROJECT_BRIEF.md) for the planned pipeline and scope.

Currently available: document and customer-rule loading, extraction, validation,
and routing connected through LangGraph, with SQLite checkpoints for resuming
interrupted runs and SQLite storage for completed results. A minimal operator UI
and command-line query interface are available.
Live sample results and limitations are recorded in [samples/README.md](samples/README.md).

## Local setup

Use Python 3.11 or later. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
# Edit .env locally, then export its settings into this shell:
set -a
source .env
set +a
```

Environment files are not loaded automatically. Use shell quoting for values
containing spaces.

## Run the operator UI

From the repository root, with the virtual environment active and settings exported:

```bash
streamlit run nova/ui.py
```

Upload one PDF, PNG, or JPEG, review/edit the customer rules, and click
**Process document**. This makes live model calls and uses API credits.
The screen displays the run ID, extraction confidence/evidence, validation,
decision, and any amendment draft. Download the original document for comparison.

Select a saved document by its filename and run ID to load its saved state later. After a processing failure, correct
the underlying problem and use **Resume run** to continue from the saved stage.
For a replacement document or changed rules, start a new run instead. Loading a
saved run and querying results do not call models. Amendment drafts are not sent.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `OPENAI_API_KEY` | unset | Required when using an OpenAI provider |
| `NOVA_EXTRACTOR_PROVIDER` | `gemini` | Internal selection: `gemini` or `openai` |
| `NOVA_VALIDATOR_PROVIDER` | `gemini` | Internal selection: `gemini` or `openai` |
| `GEMINI_API_KEY` | unset | Required for live Gemini extraction/validation; not needed for tests |
| `NOVA_EXTRACTOR_MODEL` | `gemini-2.5-pro` | Model direction from the brief |
| `NOVA_VALIDATOR_MODEL` | `gemini-2.5-flash` | Model direction from the brief |
| `NOVA_CONFIDENCE_THRESHOLD` | `0.8` | Finite number from 0 to 1; provisional, uncalibrated |
| `NOVA_MAX_RETRIES` | `2` | Maximum transient-failure retries after the initial model request |
| `NOVA_MAX_DOCUMENT_BYTES` | `10485760` | Maximum input file size in bytes (10 MiB); PDF, PNG, or JPEG |
| `NOVA_MODEL_TIMEOUT_MS` | `120000` | Model request timeout in milliseconds per attempt |
| `NOVA_EXTRACTOR_MAX_OUTPUT_TOKENS` | `8192` | Extractor output-token budget |
| `NOVA_VALIDATOR_MAX_OUTPUT_TOKENS` | `8192` | Validator output-token budget |
| `NOVA_STORAGE_PATH` | `data/nova.sqlite3` | SQLite file path, relative to the working directory |

Model selection is internal configuration, not an operator control. For the
Gemini extraction / GPT validation combination, export:

```bash
export NOVA_EXTRACTOR_PROVIDER=gemini
export NOVA_EXTRACTOR_MODEL=gemini-3.1-pro-preview
export NOVA_VALIDATOR_PROVIDER=openai
export NOVA_VALIDATOR_MODEL=gpt-5.4-mini
```

Use `gpt-5.4-nano` to evaluate the smaller validator. Both stages can use OpenAI
when explicitly configured; image/PDF extraction through OpenAI still requires
separate live evaluation. Saved runs resume with the current internal settings.

Keep credentials in the ignored `.env` or the process environment.

## Query stored results

After storing review results, ask one of these questions:

- How many documents were auto-approved?
- How many documents required human review?
- How many documents had mismatches?
- Which fields most frequently failed validation?

```bash
python -m nova.query --database data/nova.sqlite3 "How many documents had mismatches?"
```

Answers cover all stored results. Date and customer filters are not supported
yet. Field failures mean `MISMATCH`, counted once per field per document;
`UNCERTAIN` is not counted as a mismatch. These queries make no model calls.

## Verification

```bash
python -m unittest discover -s tests -v
```

The tests run locally without model calls or API credits.
