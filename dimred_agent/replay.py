"""Offline recomputation from a completed pipeline's saved decisions."""
from copy import deepcopy
from pathlib import Path
import json
import math
import shutil

import numpy as np
import pandas as pd
from scipy import sparse

from .data import InputError, load_dataset
from .preprocessing import PreprocessingPlan, preprocess
from .profile import profile_dataset, render_summary
from .pipeline import input_snapshot, files_snapshot, resolve_config
from .diagnostics import DiagnosticConfig, diagnostics_from_run
from .reduction_planner import ResourceLimits, planning_evidence, validate_selection
from .execution import read, write, sha256, response_for, execute, run_worker
from .evaluation import EvaluationConfig, evaluate
from .reporting import collect, decision_ledger, digest, generate_report


def checked_stage(root, record):
    folder = (root/record['output']).resolve()
    if root not in folder.parents or record.get('status') != 'complete':
        raise InputError('Replay requires completed stages contained in the source run.')
    if files_snapshot(folder) != record['files']:
        raise InputError('Source checkpoint files changed: '+record['output'])
    return folder


def array_comparison(a, b, rtol, atol):
    if a.shape != b.shape:
        return {'matches': False, 'reason': 'shape mismatch'}
    largest = 0.
    matches = True
    for start in range(0, len(a), 128):
        x, y = np.asarray(a[start:start+128]), np.asarray(b[start:start+128])
        matches = matches and bool(np.allclose(x, y, rtol=rtol, atol=atol))
        if x.size:
            largest = max(largest, float(np.max(np.abs(x-y))))
    return {'matches': matches, 'max_absolute_difference': largest}


def embedding_comparison(current, reference, rtol, atol):
    direct = array_comparison(current, reference, rtol, atol)
    if current.shape != reference.shape:
        return {'coordinates': direct, 'geometry_matches': False}
    a = current-current.mean(axis=0)
    b = reference-reference.mean(axis=0)
    u, _, vt = np.linalg.svd(a.T@b, full_matrices=False)
    error = float(np.linalg.norm(a@(u@vt)-b))
    reference_norm = float(np.linalg.norm(b))
    return {'coordinates': direct, 'geometry_matches': bool(error <= atol+rtol*reference_norm),
            'alignment': 'Translation and orthogonal rotation/reflection only; no rescaling.',
            'aligned_frobenius_error': error, 'reference_frobenius_norm': reference_norm,
            'relative_aligned_error': error/reference_norm if reference_norm else None}


def metric_comparison(a, b, rtol, atol):
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(metric_comparison(a[k], b[k], rtol, atol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(metric_comparison(x, y, rtol, atol) for x, y in zip(a, b))
    if type(a) in (int, float) and type(b) in (int, float):
        return math.isclose(a, b, rel_tol=rtol, abs_tol=atol)
    return a == b


def replay_pipeline(source, out, *, dataset=None, rtol=1e-5, atol=1e-8, _method=None):
    for name, value in [('rtol', rtol), ('atol', atol)]:
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise InputError(name+' must be finite and nonnegative.')
    source, out = Path(source).resolve(), Path(out).resolve()
    if out.exists() or source == out or source in out.parents:
        raise InputError('Replay requires a new output directory outside the source run.')
    saved = read(source/'pipeline.json')
    if saved['configuration']['settings'].get('method_policy') == 'all_suitable' and _method is None:
        from .multi_method import replay_methods
        return replay_methods(source, out, saved, dataset, rtol, atol)
    if saved['status'] not in ('pipeline_complete', 'pipeline_partial'):
        raise InputError('Source must be a completed integrated pipeline run.')
    config, _ = resolve_config({'method_policy':'single', **saved['configuration']['settings']})
    stages = {key: checked_stage(source, value) for key, value in saved['stages'].items()}
    if _method is not None:
        if _method not in saved.get('method_results', {}) or saved['method_results'][_method]['status'] != 'execution_complete':
            raise InputError('Replay requires a saved successful method.')
        stages['selection'] = stages['selection']/_method
        for key in ('execution', 'evaluation', 'report'):
            stages[key] = stages[key+'_'+_method]
    for key in ('inspection', 'preprocessing', 'diagnostics', 'selection', 'execution', 'evaluation', 'report'):
        if key not in stages:
            raise InputError('Missing source stage: '+key)
    if read(stages['preprocessing']/'workflow_config.json') != saved['configuration']:
        raise InputError('Pipeline configuration disagrees with the saved stage configuration.')
    dataset = Path(dataset or saved['dataset']).resolve()
    if dataset.is_dir() and (dataset == out or dataset in out.parents):
        raise InputError('Replay output must be outside the input directory.')
    if input_snapshot(dataset) != saved['input_snapshot']:
        raise InputError('Raw dataset fingerprint differs from the saved input.')
    out.mkdir(parents=True)
    state = {'status': 'running', 'source_run': str(source), 'source_pipeline_sha256': sha256(source/'pipeline.json'),
             'dataset': str(dataset), 'model_calls_attempted': 0, 'rtol': rtol, 'atol': atol,
             'policy': 'Recompute saved successful plan; no replanning, new fallback, or dimension search.',
             'stages': {}}

    def progress(stage):
        state['current_stage'] = stage
        write(out/'replay.json', state)
        print('REPLAY: '+stage, flush=True)

    try:
        progress('inspection')
        data = load_dataset(dataset, **config['loader'])
        before = profile_dataset(data)
        (out/'inspection').mkdir()
        write(out/'inspection/profile.json', before)
        (out/'inspection/profile.md').write_text(render_summary(before), encoding='utf-8')
        state['stages']['inspection'] = 'complete'
        progress('preprocessing')
        pre = out/'preprocessing'
        pre.mkdir()
        prior_pre = read(stages['preprocessing']/'run.json')
        result = preprocess(data, PreprocessingPlan.from_dict(prior_pre['plan']))
        result.save(pre/'preprocessed')
        after = profile_dataset(result.dataset)
        write(pre/'input_profile.json', before)
        write(pre/'preprocessed/profile.json', after)
        (pre/'preprocessed/profile.md').write_text(render_summary(after), encoding='utf-8')
        write(pre/'run.json', {'status': 'preprocessing_complete', 'plan': prior_pre['plan'],
                              'explanation': prior_pre.get('explanation', prior_pre['plan']['reason']),
                              'output_shape': list(result.dataset.X.shape), 'validation_history': [],
                              'backend': 'saved_plan_replay', 'reduction_executed': False})
        write(pre/'workflow_config.json', saved['configuration'])
        del data, result
        state['stages']['preprocessing'] = 'complete'
        progress('diagnostics_and_saved_selection')
        diagnostics = diagnostics_from_run(pre, after, DiagnosticConfig(**{
            **config['diagnostics'], 'neighbors': tuple(config['diagnostics']['neighbors'])}))
        prior_execution = read(stages['execution']/'execution.json')
        successful = prior_execution['attempts'][-1]
        if successful['status'] != 'complete':
            raise InputError('No saved successful reducer attempt.')
        plan = deepcopy(successful['plan'])
        selected_dimensions = prior_execution['output_shape'][1]
        plan['n_components'] = selected_dimensions
        catalog = read(stages['selection']/'selection.json').get('available_methods', [plan['method'], *plan['alternatives']])
        evidence = planning_evidence(after, selected_dimensions, ResourceLimits(**config['resources']), diagnostics, available_methods=catalog)
        validate_selection(response_for(plan), evidence)
        selection = out/'selection'
        selection.mkdir()
        write(selection/'diagnostics.json', diagnostics)
        write(selection/'selection_evidence.json', evidence)
        selected = deepcopy(read(stages['selection']/'selection.json'))
        selected.update(plan=plan, backend='saved_plan_replay', planner_calls_attempted=0,
                        validation_history=[], input_profile_sha256=digest(after),
                        feasibility_checks=evidence['eligibility'])
        write(selection/'selection.json', selected)
        provenance = {'mode': 'saved_plan_replay', 'source_plan': prior_execution['original_plan'],
                      'saved_successful_plan': successful['plan'], 'replayed_plan': plan,
                      'saved_dimension_mode': prior_execution.get('dimension_mode', 'fixed'),
                      'saved_dimension_selection': successful.get('dimension_selection'),
                      'source_fallback_occurred': prior_execution['fallback_occurred'],
                      'source_execution_notices': prior_execution['notices'],
                      'source_attempts': prior_execution['attempts'],
                      'explanation': 'Original explanations are historical. Replay fixes the saved successful method and chosen dimensions; failed attempts and candidate searches are not repeated. Configuration origins describe the source run.'}
        write(pre/'replay_provenance.json', provenance)
        state['stages']['diagnostics_and_saved_selection'] = 'complete'
        progress('execution')

        def saved_worker(matrix, requested, directory, timeout, threads):
            actual = deepcopy(requested)
            # Randomized PCA's chosen prefixes depend on the fitted decomposition size.
            decomposition = successful.get('dimension_selection', {}).get('decomposition_dimensions', selected_dimensions)
            if actual['method'] == 'pca':
                actual['n_components'] = decomposition
            details = run_worker(matrix, actual, directory, timeout, threads)
            if details['status'] == 'complete' and actual['n_components'] != selected_dimensions:
                y = np.load(directory/'embedding.npy', allow_pickle=False)[:, :selected_dimensions]
                np.save(directory/'embedding.npy', y, allow_pickle=False)
                for key in ('explained_variance_ratio', 'singular_values'):
                    details['metrics'][key] = details['metrics'][key][:selected_dimensions]
                details['selected_dimensions'] = selected_dimensions
                details['replay_decomposition_dimensions'] = decomposition
                write(directory/'worker_result.json', details)
            return details

        execution = out/'execution'
        executed = execute(pre, selection, execution, timeout=config['execution']['timeout'],
                           threads=config['execution']['threads'], allow_fallback=False, worker=saved_worker)
        if executed['status'] != 'execution_complete':
            raise InputError('Saved reducer execution failed. Replay stops without new AI calls or fallback.')
        state['stages']['execution'] = 'complete'
        progress('evaluation')
        evaluated = evaluate(pre, execution, out/'evaluation', config=EvaluationConfig(**config['evaluation']),
                             color_column=config['report']['color_column'])
        state['stages']['evaluation'] = 'complete'
        progress('comparison')
        filename = 'measurements.sparse.npz' if after['storage'].startswith('sparse') else 'measurements.npy'
        current_path, old_path = pre/'preprocessed'/filename, stages['preprocessing']/'preprocessed'/filename
        if filename.endswith('.npz'):
            a, b = sparse.load_npz(current_path), sparse.load_npz(old_path)
            structure = a.shape == b.shape and np.array_equal(a.indptr, b.indptr) and np.array_equal(a.indices, b.indices)
            preprocessing = array_comparison(a.data, b.data, rtol, atol) if structure else {'matches': False, 'reason': 'Sparse structure differs'}
        else:
            preprocessing = array_comparison(np.load(current_path, mmap_mode='r'), np.load(old_path, mmap_mode='r'), rtol, atol)
        old_eval = read(stages['evaluation']/'evaluation.json')
        embedding = embedding_comparison(np.load(execution/'embedding.npy'), np.load(stages['execution']/'embedding.npy'), rtol, atol)
        metrics = {key: metric_comparison(evaluated[key], old_eval[key], rtol, atol)
                   for key in ('embedding', 'view', 'method_metrics')}
        alignment = {}
        for filename in ('observations.csv', 'features.csv', 'labels.csv'):
            a, b = pre/'preprocessed'/filename, stages['preprocessing']/'preprocessed'/filename
            alignment[filename] = a.exists() == b.exists() and (not a.exists() or
                pd.read_csv(a, dtype=str, keep_default_na=False).equals(pd.read_csv(b, dtype=str, keep_default_na=False)))
        comparison = {'preprocessing': preprocessing, 'embedding': embedding, 'metrics_match': metrics,
                      'effective_parameters_match': executed['attempts'][-1].get('effective_parameters') == successful.get('effective_parameters'),
                      'metadata_match': alignment, 'reference_versions': prior_execution['versions'],
                      'replay_versions': executed['versions'], 'reference_python': prior_execution['python'],
                      'replay_python': executed['python'],
                      'matches': preprocessing['matches'] and embedding['geometry_matches'] and all(metrics.values()) and all(alignment.values())}
        comparison['matches'] = comparison['matches'] and comparison['effective_parameters_match']
        write(out/'comparison.json', comparison)
        state['comparison_matches'] = comparison['matches']
        state['stages']['comparison'] = 'complete'
        progress('report')
        _, records = collect(pre, selection, execution, out/'evaluation')
        fingerprint = digest({'records': records, 'ledger': decision_ledger(records)})
        old_response_path = stages['report']/'narrative_response.json'
        exact = old_response_path.exists() and json.loads(read(old_response_path)['plan_json'])['evidence_digest'] == fingerprint
        report = generate_report(pre, selection, execution, out/'evaluation', out/'report', name=config['report']['name'],
                                 replay=old_response_path if exact else None, evidence_only=not exact)
        state['narrative_reused'] = bool(exact)
        state['narrative_reason'] = ('Exact evidence fingerprint matches.' if exact else
            'Recomputed records differ from the original narrative evidence (including timings/provenance). Current report is evidence-only; historical narrative was not applied to new results.')
        if old_response_path.exists() and not exact:
            shutil.copyfile(old_response_path, out/'historical_narrative_response.json')
        report_path = out/'report'/report['report']
        text = report_path.read_text(encoding='utf-8')
        report_path.write_text('# Offline saved-plan replay\n\n'+state['narrative_reason']+'\n\n'
                              'Numerical comparison within configured tolerances: '+str(comparison['matches'])+
                              '. See [comparison](../comparison.json) and [replay record](../replay.json).\n\n'+text, encoding='utf-8')
        state['stages']['report'] = 'complete'
        state.update(status='replay_complete', current_stage=None, report=report_path.relative_to(out).as_posix())
    except Exception as exc:
        state.update(status='replay_failed', error_type=type(exc).__name__, error=str(exc))
    write(out/'replay.json', state)
    return state
