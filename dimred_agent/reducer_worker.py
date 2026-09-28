"""Private subprocess entry point; contains no AI calls."""
import json
from pathlib import Path
import sys
import time
import numpy as np
from scipy import sparse


def main():
    matrix, spec, output = map(Path, sys.argv[1:])
    request = json.loads(spec.read_text(encoding='utf-8'))
    start = time.monotonic()
    try:
        from .reducers import fit_reducer
        X = sparse.load_npz(matrix) if matrix.suffix == '.npz' else np.load(matrix, mmap_mode='r', allow_pickle=False)
        Y, details = fit_reducer(X, request['plan'], request['seed'], request['threads'])
        if request.get('evaluation') is not None:
            from .dimension_metrics import measure
            details['dimension_metrics'] = measure(X, Y, request['plan'], request['evaluation'])
        # Ensure details serialize before publishing a successful result.
        json.dumps(details, allow_nan=False)
        np.save(output / 'embedding.npy', Y, allow_pickle=False)
        result = {'status': 'complete', **details}
    except Exception as exc:
        result = {'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)}
    result['elapsed_seconds'] = time.monotonic() - start
    (output / 'worker_result.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    return 0 if result['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
