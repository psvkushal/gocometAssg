"""Live comparison on identical saved extraction inputs; consumes API credits."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from nova.agents.router import route
from nova.agents.validator import Validator
from nova.config import load_settings
from nova.models.factory import create_provider
from nova.persistence.storage import SQLiteResultStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True, help='Prior live report containing database and case run IDs')
    parser.add_argument('--output', type=Path, default=Path('data/validator_comparison.json'))
    parser.add_argument("--models", nargs="+", choices=["gpt-5.4-nano", "gpt-5.4-mini", "gemini-3.6-flash"],
                        default=["gpt-5.4-nano", "gpt-5.4-mini", "gemini-3.6-flash"])
    args = parser.parse_args()
    settings = load_settings()
    source = json.loads(args.report.read_text())
    store = SQLiteResultStore(source['database'])
    results = json.loads(args.output.read_text()) if args.output.exists() else []
    completed = {(row["sample"], row["model"]) for row in results if "error" not in row}
    for case in source['cases']:
        saved = store.get(case['run_id'])
        for model in args.models:
            provider_name = 'openai' if model.startswith('gpt-') else 'gemini'
            if (case["sample"], model) in completed:
                continue
            configured = replace(settings, validator_provider=provider_name, validator_model=model, max_retries=0)
            start = perf_counter()
            record = {'sample': case['sample'], 'model': model}
            provider = create_provider(provider_name, configured)
            class Capture:
                def generate(self, request):
                    response = provider.generate(request)
                    record['raw_response'] = response
                    return response
            try:
                result = Validator(Capture(), configured).validate(saved.extraction, saved.rules)
                record.update(seconds=round(perf_counter()-start, 2), validation=result.model_dump(), decision=route(result).model_dump())
                print(case['sample'], model, record['seconds'], record['decision']['outcome'], flush=True)
            except Exception as exc:
                # Do not save raw SDK error bodies, which can contain submitted data.
                record.update(seconds=round(perf_counter()-start, 2), error=type(exc).__name__, status_code=getattr(exc, 'status_code', None))
                print(case['sample'], model, record['seconds'], record['error'], flush=True)
                if hasattr(exc, 'errors'):
                    record['validation_errors'] = str(exc.errors(include_input=False))
                if getattr(exc, 'status_code', None) in {401, 403, 429}:
                    results.append(record)
                    args.output.write_text(json.dumps(results, indent=2)+'\n')
                    raise SystemExit('Comparison stopped: provider access or quota failure.') from None
            results.append(record)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(results, indent=2)+'\n')
    for model in dict.fromkeys(row['model'] for row in results):
        times = [row['seconds'] for row in results if row['model'] == model and 'error' not in row]
        print(model, 'median successful seconds:', median(times) if times else 'no successful calls')


if __name__ == '__main__':
    main()
