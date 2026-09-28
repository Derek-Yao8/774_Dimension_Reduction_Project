"""Execute a validated selection, with one explicitly disclosed failure fallback."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from importlib.metadata import version

import numpy as np
import pandas as pd
from scipy import sparse
from .data import InputError
from .codex_planner import CodexPlanner, PlannerError
from .reduction_planner import ResourceLimits, planning_evidence, reduction_instructions, validate_selection


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def response_for(plan):
    return {'status': 'ready', 'explanation': plan['reason'], 'questions': [], 'plan_json': json.dumps(plan)}


def load_inputs(preprocessing_run, selection_run):
    pre, selected = Path(preprocessing_run), Path(selection_run)
    record, profile = read(pre / 'run.json'), read(pre / 'preprocessed/profile.json')
    selection = read(selected / 'selection.json')
    if record['status'] != 'preprocessing_complete' or selection['status'] != 'selection_complete':
        raise InputError('Completed preprocessing and selection are required.')
    digest = hashlib.sha256(json.dumps(profile, sort_keys=True, allow_nan=False).encode()).hexdigest()
    if digest != selection['input_profile_sha256']:
        raise InputError('Selection was made for a different profile.')
    if record['plan'] != profile['provenance']['preprocessing_plan']:
        raise InputError('Preprocessing records disagree.')
    limits = ResourceLimits(**selection['resource_limits'])
    diagnostics = read(selected / 'diagnostics.json') if (selected / 'diagnostics.json').exists() else None
    catalog = selection.get('available_methods', [selection['plan']['method'], *selection['plan']['alternatives']])
    evidence = planning_evidence(profile, selection['plan']['n_components'], limits, diagnostics, available_methods=catalog)
    validate_selection(response_for(selection['plan']), evidence)
    if selection.get('random_state') != 0:
        raise InputError('Only the recorded seed 0 execution contract is supported.')
    matrix = pre / 'preprocessed' / ('measurements.sparse.npz' if profile['storage'].startswith('sparse') else 'measurements.npy')
    matrix_hash = sha256(matrix)
    if diagnostics is None or diagnostics.get('source_sha256') != matrix_hash:
        raise InputError('A matching diagnostic matrix fingerprint is required; regenerate diagnostics/selection if missing or stale.')
    X = sparse.load_npz(matrix) if matrix.suffix == '.npz' else np.load(matrix, mmap_mode='r', allow_pickle=False)
    shape = [profile['n_observations'], profile['n_features']]
    if list(X.shape) != shape or record['output_shape'] != shape:
        raise InputError('Processed matrix/profile shape mismatch.')
    if X.dtype.kind not in 'biuf':
        raise InputError('Numeric matrix required.')
    values = X.data if sparse.issparse(X) else X
    for start in range(0, len(values), 32 if values.ndim == 2 else 100000):
        if not np.isfinite(values[start:start + (32 if values.ndim == 2 else 100000)]).all():
            raise InputError('Nonfinite input; fix preprocessing before execution.')
    ids = pd.read_csv(pre / 'preprocessed/observations.csv', dtype=str, keep_default_na=False).iloc[:, 0]
    if len(ids) != shape[0] or ids.duplicated().any():
        raise InputError('Missing or duplicate observation identifiers.')
    label_path = pre / 'preprocessed/labels.csv'
    if label_path.exists():
        label_ids = pd.read_csv(label_path, dtype=str, keep_default_na=False).iloc[:, 0]
        if not label_ids.equals(ids):
            raise InputError('Label row order disagrees with observations.')
    return matrix.resolve(), ids, selection, evidence, matrix_hash


def run_worker(matrix, plan, directory, timeout, threads, evaluation=None):
    directory.mkdir()
    write(directory / 'request.json', {'plan': plan, 'seed': 0, 'threads': threads, 'evaluation': evaluation})
    env = dict(os.environ)
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS'):
        env[key] = str(threads)
    command = [sys.executable, '-m', 'dimred_agent.reducer_worker', str(matrix),
               str((directory / 'request.json').resolve()), str(directory.resolve())]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {'status': 'failed', 'error_type': 'Timeout', 'error': f'Reducer exceeded {timeout} seconds and was terminated.'}
    (directory / 'stdout.txt').write_text(result.stdout, encoding='utf-8')
    (directory / 'stderr.txt').write_text(result.stderr, encoding='utf-8')
    path = directory / 'worker_result.json'
    details = read(path) if path.exists() else {'status': 'failed', 'error_type': 'ProcessFailure', 'error': f'Worker exited {result.returncode}; see stderr.txt.'}
    if result.returncode and details['status'] == 'complete':
        return {'status': 'failed', 'error_type': 'ProcessFailure', 'error': f'Worker exited {result.returncode}.'}
    return details


def execute(preprocessing_run, selection_run, out, *, timeout=600, threads=2,
            allow_fallback=True, planner=None, worker=run_worker, dimension_config=None,
            excluded_fallback_methods=()):
    from .dimension_selection import DimensionConfig, search_dimensions
    if dimension_config is not None and not isinstance(dimension_config, DimensionConfig):
        raise InputError('dimension_config must be a DimensionConfig or None for fixed mode.')
    for name, value in [('timeout', timeout), ('threads', threads)]:
        if type(value) is not int or value < 1:
            raise InputError(f'{name} must be a positive integer.')
    if type(allow_fallback) is not bool:
        raise InputError('allow_fallback must be boolean.')
    out = Path(out)
    if out.exists():
        raise InputError('Choose a new execution output directory.')
    matrix, ids, selection, evidence, matrix_hash = load_inputs(preprocessing_run, selection_run)
    out.mkdir(parents=True)
    report = {'status': 'running', 'original_plan': selection['plan'], 'attempts': [],
              'fallback_occurred': False, 'fallback_planner_calls': 0, 'final_method': None,
              'input_sha256': matrix_hash, 'selection_sha256': sha256(Path(selection_run) / 'selection.json'),
              'timeout_seconds_per_attempt': timeout, 'threads': threads, 'seed': 0,
              'versions': {k: version(k) for k in ('numpy', 'scipy', 'scikit-learn', 'pandas')},
              'python': platform.python_version(), 'allow_fallback': allow_fallback, 'notices': []}

    def persist():
        write(out / 'execution.json', report)
        (out / 'execution_summary.md').write_text(
            '# Reduction execution\n\nStatus: ' + report['status'] + '\n\n' +
            '\n\n'.join(report['notices']) + '\n\nFinal method: ' + str(report['final_method']) +
            '\n\nThis is an execution record, not the final analysis report.\n', encoding='utf-8')

    def notice(message):
        report['notices'].append(message)
        print(message, flush=True)
        persist()

    plan = selection['plan']
    report['dimension_mode'] = 'auto' if dimension_config is not None else 'fixed'
    deadline = time.monotonic() + dimension_config.total_seconds if dimension_config else None
    persist()
    for index in range(2):
        directory = out / f'attempt_{index + 1}'
        try:
            details = (search_dimensions(matrix, plan, directory, timeout, threads, dimension_config, evidence, deadline)
                       if dimension_config is not None else worker(matrix, plan, directory, timeout, threads))
        except (OSError, ValueError) as exc:
            report['status'] = 'execution_failed'
            notice('WORKER INFRASTRUCTURE FAILED: ' + str(exc) + '; no method fallback for process/logging errors.')
            return report
        report['attempts'].append({'plan': plan, **details})
        report['versions'].update(details.get('dependency_versions', {}))
        if details['status'] == 'complete':
            Y = np.load(directory / 'embedding.npy', allow_pickle=False)
            chosen_dimensions = details.get('selected_dimensions', plan['n_components'])
            if Y.shape != (len(ids), chosen_dimensions) or not np.isfinite(Y).all():
                details = {'status': 'failed', 'error_type': 'InvalidOutput', 'error': 'Saved coordinates have wrong shape or nonfinite values.'}
                report['attempts'][-1].update(details)
            else:
                shutil.copyfile(directory / 'embedding.npy', out / 'embedding.npy')
                frame = pd.DataFrame(Y, columns=[f'dimension_{j + 1}' for j in range(Y.shape[1])])
                frame.insert(0, 'observation_id', ids.to_numpy())
                frame.to_csv(out / 'embedding.csv', index=False)
                view = frame.iloc[:, :min(2, chosen_dimensions) + 1]
                view.to_csv(out / 'visualization_coordinates.csv', index=False)
                write(out / 'visualization_view.json', {
                    'description': 'First coordinate pair of the selected representation, not a separate 2D fit.',
                    'representation_dimensions': chosen_dimensions, 'view_dimensions': min(2, chosen_dimensions),
                    'pca_displayed_variance': sum(details['metrics']['explained_variance_ratio'][:2]) if plan['method'] == 'pca' else None,
                    'limitation': 'A coordinate view can hide structure. Plot rendering is a later stage.'})
                for filename in ('observations.csv', 'labels.csv'):
                    source = Path(preprocessing_run) / 'preprocessed' / filename
                    if source.exists():
                        shutil.copyfile(source, out / filename)
                report.update(status='execution_complete', final_method=plan['method'], output_shape=list(Y.shape),
                              selected_dimensions=chosen_dimensions,
                              embedding_sha256=sha256(out / 'embedding.npy'))
                if 'dimension_selection' in details:
                    write(out / 'dimension_selection.json', details['dimension_selection'])
                    notice('DIMENSION SELECTION: ' + str(chosen_dimensions) + ' dimensions; target_reached=' +
                           str(details['dimension_selection']['target_reached']) + '; stop=' + details['dimension_selection']['stop_reason'])
                notice(('FALLBACK SUCCEEDED: ' if index else 'EXECUTION SUCCEEDED: ') + plan['method'] + ' ' + json.dumps(plan['parameters']))
                return report
        notice('EXECUTION FAILED: ' + plan['method'] + ' ' + json.dumps(plan['parameters']) + ': ' + details.get('error', 'unknown failure'))
        if details.get('error_type') in ('DimensionBudget', 'TimeBudget') or (deadline is not None and time.monotonic() >= deadline):
            report['status'] = 'execution_failed'
            notice('Stopping at the dimension-search budget; no AI fallback or budget reset.')
            return report
        if details.get('error_type') in ('ImportError', 'ModuleNotFoundError', 'PermissionError', 'FileNotFoundError'):
            report['status'] = 'execution_failed'
            notice('Stopping for environment/input repair; changing the method will not fix this failure.')
            return report
        if index or not allow_fallback:
            report['status'] = 'execution_failed'
            notice('Stopping; no additional method will be tried.')
            return report
        fallback_evidence = deepcopy(evidence)
        fallback_evidence['eligibility'][plan['method']] = {'eligible': False, 'reasons': ['Already failed in this execution.']}
        for method in excluded_fallback_methods:
            if method in fallback_evidence['eligibility']:
                fallback_evidence['eligibility'][method] = {'eligible': False, 'reasons': ['Already selected or attempted in this multi-method workflow.']}
        if not any(v['eligible'] for v in fallback_evidence['eligibility'].values()):
            report['status'] = 'execution_failed'
            notice('FALLBACK UNAVAILABLE: no other method satisfies the configured constraints.')
            return report
        notice('FALLBACK PLANNING: requesting one replacement after the recorded failure; limits and dimensions remain unchanged.')
        try:
            planner = planner or CodexPlanner()
            report['fallback_planner_calls'] += 1
            context = 'Authorized execution fallback. Original plan and observed failure: ' + json.dumps({'plan': plan, 'failure': details})
            prompt = reduction_instructions(fallback_evidence, context, 'Select a different eligible method using this failure evidence. This is the only fallback attempt.')
            response = planner.propose(prompt, out / 'fallback_planning')
            write(out / 'fallback_response.json', response)
            replacement = validate_selection(response, fallback_evidence)
            if replacement is None:
                report.update(status='needs_clarification', questions=response['questions'])
                notice('FALLBACK NEEDS CLARIFICATION: ' + json.dumps(response['questions']))
                return report
            plan = replacement
            report['fallback_occurred'] = True
            notice('FALLBACK SELECTED: ' + plan['method'] + ' ' + json.dumps(plan['parameters']) + '. Reason: ' + plan['reason'])
        except (PlannerError, InputError, ValueError, OSError, subprocess.SubprocessError) as exc:
            report['status'] = 'execution_failed'
            notice('FALLBACK PLANNING FAILED: ' + str(exc) + '; stopping without another call.')
            return report
