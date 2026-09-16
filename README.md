# GoComet Nova

A Python proof of concept for reviewing one trade document per run. See
[PROJECT_BRIEF.md](PROJECT_BRIEF.md) for the planned pipeline and scope.

Currently implemented: package skeleton and validated environment configuration.
Pipeline stages and UI will be added in separate reviewable features.

## Local setup

Use Python 3.11 or later. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
cp .env.example .env
# Edit .env locally, then export its settings into this shell:
set -a
source .env
set +a
```

There are no runtime dependencies. The package can be imported directly from the
repository root; optional installation uses `python -m pip install -e .` and
requires setuptools as a build dependency. Environment files are not loaded
automatically. Use shell quoting for values containing spaces.

## Configuration

Call `nova.config.load_settings()` at the application boundary. Tests can pass an
explicit mapping instead of reading the process environment.

| Variable | Default | Meaning |
| --- | --- | --- |
| `GEMINI_API_KEY` | unset | Optional at this stage; excluded from settings repr |
| `NOVA_EXTRACTOR_MODEL` | `gemini-2.5-pro` | Model direction from the brief |
| `NOVA_VALIDATOR_MODEL` | `gemini-2.5-flash` | Model direction from the brief |
| `NOVA_CONFIDENCE_THRESHOLD` | `0.8` | Finite number from 0 to 1; provisional, uncalibrated |
| `NOVA_MAX_RETRIES` | `2` | Non-negative retry count after the initial attempt, for future transient failure handling |
| `NOVA_STORAGE_PATH` | `data/nova.sqlite3` | Future SQLite file path, relative to the working directory |

Loading settings makes no model calls and creates no storage files. Model
availability and credential checks belong to the later provider integration.
Keep credentials in the ignored `.env` or the process environment.

## Verification

```bash
python -m unittest discover -s tests -v
python -c 'from nova.config import load_settings; print(load_settings())'
```

The tests use no API credits and cover defaults, overrides, boundary values,
invalid configuration, environment isolation, and secret omission from repr.
