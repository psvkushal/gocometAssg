# GoComet Nova

A Python proof of concept for reviewing one trade document per run. See
[PROJECT_BRIEF.md](PROJECT_BRIEF.md) for the planned pipeline and scope.

Currently available: document and customer-rule loading, Gemini extraction,
customer-rule validation, and deterministic routing. End-to-end processing and
the UI are not yet available.

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

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `GEMINI_API_KEY` | unset | Required for live Gemini extraction; not needed for tests |
| `NOVA_EXTRACTOR_MODEL` | `gemini-2.5-pro` | Model direction from the brief |
| `NOVA_VALIDATOR_MODEL` | `gemini-2.5-flash` | Model direction from the brief |
| `NOVA_CONFIDENCE_THRESHOLD` | `0.8` | Finite number from 0 to 1; provisional, uncalibrated |
| `NOVA_MAX_RETRIES` | `2` | Maximum transient-failure retries after the initial model request |
| `NOVA_MAX_DOCUMENT_BYTES` | `10485760` | Maximum input file size in bytes (10 MiB); PDF, PNG, or JPEG |
| `NOVA_MODEL_TIMEOUT_MS` | `120000` | Model request timeout in milliseconds per attempt |
| `NOVA_EXTRACTOR_MAX_OUTPUT_TOKENS` | `8192` | Extractor output-token budget |
| `NOVA_VALIDATOR_MAX_OUTPUT_TOKENS` | `8192` | Validator output-token budget |
| `NOVA_STORAGE_PATH` | `data/nova.sqlite3` | Future SQLite file path, relative to the working directory |

Keep credentials in the ignored `.env` or the process environment.

## Verification

```bash
python -m unittest discover -s tests -v
```

The tests run locally without model calls or API credits.
