"""Live extraction comparison on the same documents; consumes API credits."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from nova.agents.extractor import Extractor
from nova.config import load_settings
from nova.documents import load_document
from nova.models.factory import create_provider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('documents', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    settings = load_settings()
    results = []
    for path in args.documents:
        document = load_document(path, max_bytes=settings.max_document_bytes)
        for provider_name, model in [('openai', 'gpt-5.4-mini'), ('gemini', 'gemini-3.1-pro-preview')]:
            configured = replace(settings, extractor_provider=provider_name, extractor_model=model, max_retries=0)
            started = perf_counter()
            record = {'document': str(path), 'model': model}
            try:
                extraction = Extractor(create_provider(provider_name, configured), configured).extract(document)
                record.update(seconds=round(perf_counter()-started, 2), extraction=extraction.model_dump())
                print(path.name, model, record['seconds'], 'seconds;', len(extraction.fields), 'fields', flush=True)
            except Exception as exc:
                record.update(seconds=round(perf_counter()-started, 2), error=type(exc).__name__, status_code=getattr(exc, 'status_code', None))
                print(path.name, model, record['error'], record['status_code'], flush=True)
            results.append(record)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(results, indent=2)+'\n')
            if record.get('status_code') in {401, 403, 429}:
                raise SystemExit('Stopped on provider access/quota failure.')
    for model in dict.fromkeys(row['model'] for row in results):
        times = [row['seconds'] for row in results if row['model']==model and 'error' not in row]
        print(model, 'median successful seconds:', median(times) if times else None)


if __name__ == '__main__':
    main()
