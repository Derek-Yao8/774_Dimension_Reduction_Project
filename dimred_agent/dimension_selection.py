"""Bounded within-method dimension selection; never makes AI calls."""
from copy import deepcopy
from dataclasses import asdict, dataclass
import math
import time
import numpy as np
from .data import InputError


@dataclass(frozen=True)
class DimensionConfig:
    max_dimensions: int = 20
    candidates: tuple = (2, 3, 5, 10, 20)
    max_fits: int = 5
    total_seconds: int = 600
    variance_target: float = .90
    distance_error_target: float = .10
    trustworthiness_target: float = .95
    reconstruction_target: float = .10
    reconstruction_weight: float = .10
    complexity_penalty: float = .01
    min_improvement: float = .005
    plateau_patience: int = 2
    evaluation_samples: int = 256
    evaluation_neighbors: int = 5

    def __post_init__(self):
        for key in ('max_dimensions', 'max_fits', 'total_seconds', 'plateau_patience', 'evaluation_samples', 'evaluation_neighbors'):
            if type(getattr(self, key)) is not int or getattr(self, key) < 1:
                raise InputError(f'{key} must be a positive integer.')
        if self.evaluation_samples < 4:
            raise InputError('evaluation_samples must be at least 4.')
        if (not isinstance(self.candidates, tuple) or not self.candidates
                or any(type(d) is not int or d < 1 for d in self.candidates)
                or tuple(sorted(set(self.candidates))) != self.candidates):
            raise InputError('Candidate dimensions must be positive, unique and increasing.')
        for key in ('variance_target', 'distance_error_target', 'trustworthiness_target', 'reconstruction_target'):
            value = getattr(self, key)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1:
                raise InputError(f'{key} must be in (0,1].')
        for key in ('reconstruction_weight', 'complexity_penalty', 'min_improvement'):
            value = getattr(self, key)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise InputError(f'{key} must be finite and nonnegative.')


def select_candidate(records, method, config, cap):
    """Pure selection rule, independently testable without fitting."""
    valid = [r for r in records if r['status'] == 'complete']
    if not valid:
        return None, False
    if method == 'pca':
        passing = [r for r in valid if r['cumulative_variance'] >= config.variance_target]
        return (min(passing, key=lambda r: r['dimensions']) if passing else max(valid, key=lambda r: r['dimensions'])), bool(passing)
    def meets(r):
        if method in ('kernel_pca', 'laplacian_eigenmaps', 'diffusion_maps', 'tsne', 'umap'):
            return r['trustworthiness'] >= config.trustworthiness_target
        if method == 'lle':
            return r['trustworthiness'] >= config.trustworthiness_target and r['normalized_reconstruction'] <= config.reconstruction_target
        return r['normalized_distance_error'] <= config.distance_error_target
    passing = [r for r in valid if meets(r)]
    if passing:
        return min(passing, key=lambda r: r['dimensions']), True
    return min(valid, key=lambda r: (r['loss'] + config.complexity_penalty * r['dimensions'] / cap, r['dimensions'])), False


def search_dimensions(matrix, plan, directory, timeout, threads, config, evidence, deadline=None):
    from .execution import run_worker, write
    directory.mkdir()
    n, p = evidence['n_observations'], evidence['n_features']
    cap = min(config.max_dimensions, n - 1, p - 1)
    if plan['method'] in ('lle', 'laplacian_eigenmaps'):
        cap = min(cap, plan['parameters']['n_neighbors'] - 1)
    if plan['method'] == 'tsne':
        cap = min(cap, 3)
    requested = [cap] if plan['method'] == 'pca' else [d for d in config.candidates if d <= cap]
    deadline = deadline if deadline is not None else time.monotonic() + config.total_seconds
    records, successes = [], {}
    audit = {'config': asdict(config), 'method': plan['method'], 'dimension_cap': cap,
             'candidate_records': records, 'fit_count': 0, 'evaluation_seed': 0,
             'excluded_candidates': [d for d in config.candidates if d > cap],
             'limitations': ['Criteria are configurable heuristics, not proof of optimal dimensionality.',
                            'Candidate metrics guide selection and are not independent held-out evaluation.',
                            'Only dimensions listed/evaluated within budget are compared; other parameters remain fixed.']}
    stop = 'candidate_limit'
    for d in requested:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stop = 'time_budget'
            break
        if audit['fit_count'] >= config.max_fits:
            stop = 'fit_budget'
            break
        # Additional coordinate/solver and evaluation buffers, on top of existing
        # coarse working-array screens. This is not a hard OS memory guarantee.
        m = min(n, config.evaluation_samples)
        dense = n * p * 8
        baseline = 3 * dense if evidence['storage'] == 'dense' else 0
        if plan['method'] in ('mds', 'isomap'):
            baseline = max(baseline, dense + 6 * n * n * 8)
        if plan['method'] in ('kernel_pca', 'laplacian_eigenmaps', 'diffusion_maps', 'tsne', 'umap'):
            baseline = max(baseline, dense + 8 * n * n * 8)
        estimated = baseline + 4 * (n + p) * d * 8 + 8 * m * m * 8
        if plan['method'] == 'lle':
            estimated += m * p * 8 + m * n * 8
        if estimated > evidence['resource_limits']['max_working_bytes']:
            records.append({'dimensions': d, 'status': 'skipped', 'reason': 'working_memory_screen', 'estimated_bytes': estimated})
            continue
        candidate = deepcopy(plan)
        candidate['n_components'] = d
        target = directory / f'dim_{d}'
        evaluation = None if plan['method'] == 'pca' else asdict(config)
        audit['fit_count'] += 1
        result = run_worker(matrix, candidate, target, min(timeout, remaining), threads, evaluation=evaluation)
        if result['status'] != 'complete':
            records.append({'dimensions': d, **result})
            audit['stop_reason'] = 'candidate_failed'
            write(directory / 'dimension_selection.json', audit)
            if result.get('error_type') in ('ImportError', 'ModuleNotFoundError', 'PermissionError', 'FileNotFoundError'):
                return result
            if time.monotonic() >= deadline:
                stop = 'time_budget'
                break
            continue
        Y = np.load(target / 'embedding.npy', allow_pickle=False)
        if plan['method'] == 'pca':
            cumulative = np.cumsum(result['metrics']['explained_variance_ratio'])
            for j, value in enumerate(cumulative):
                records.append({'dimensions': j + 1, 'status': 'complete', 'cumulative_variance': float(value)})
                successes[j + 1] = (target, result)
            stop = 'pca_decomposition_cap'
            break
        score = result['dimension_metrics']
        record = {'dimensions': d, 'status': 'complete', **score}
        if plan['method'] == 'lle':
            record['loss'] = 1 - score['trustworthiness'] + config.reconstruction_weight * score['normalized_reconstruction']
        elif 'trustworthiness' in score:
            record['loss'] = 1 - score['trustworthiness']
        else:
            record['loss'] = score['normalized_distance_error']
        records.append(record)
        successes[d] = (target, result)
        chosen, reached = select_candidate(records, plan['method'], config, cap)
        write(directory / 'dimension_selection.json', audit)
        if reached:
            stop = 'target_reached'
            break
        valid = [r for r in records if r['status'] == 'complete']
        if len(valid) > config.plateau_patience:
            changes = [valid[i - 1]['loss'] - valid[i]['loss'] for i in range(len(valid) - config.plateau_patience, len(valid))]
            if all(0 <= change < config.min_improvement for change in changes):
                stop = 'diminishing_improvement'
                break
    chosen, reached = select_candidate(records, plan['method'], config, cap)
    audit.update(stop_reason='target_reached' if reached else stop, target_reached=reached,
                 selected_dimensions=chosen['dimensions'] if chosen else None)
    write(directory / 'dimension_selection.json', audit)
    if chosen is None:
        computational_failure = any(r['status'] == 'failed' for r in records)
        return {'status': 'failed', 'error_type': 'TimeBudget' if stop == 'time_budget' else ('DimensionFitsFailed' if computational_failure else 'DimensionBudget'),
                'error': 'No usable dimension candidate within the configured constraints.', 'dimension_selection': audit}
    selected_d = chosen['dimensions']
    target, result = successes[selected_d]
    result = deepcopy(result)
    Y = np.load(target / 'embedding.npy', allow_pickle=False)[:, :selected_d]
    np.save(directory / 'embedding.npy', Y, allow_pickle=False)
    if plan['method'] == 'pca':
        for key in ('explained_variance_ratio', 'singular_values'):
            result['metrics'][key] = result['metrics'][key][:selected_d]
        audit['decomposition_dimensions'] = result['effective_parameters']['n_components']
        write(directory / 'dimension_selection.json', audit)
    result.update(selected_dimensions=selected_d, dimension_selection=audit)
    return result
