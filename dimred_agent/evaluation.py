"""Offline, bounded evaluation of saved embeddings in preprocessed feature space."""
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from importlib.metadata import version

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import spearmanr
from sklearn.manifold import trustworthiness
from sklearn.metrics import pairwise_distances
from threadpoolctl import threadpool_limits

from .data import InputError
from .execution import read, write, sha256


@dataclass(frozen=True)
class EvaluationConfig:
    max_samples: int = 512
    max_working_bytes: int = 128_000_000
    neighbors: int = 5
    seed: int = 0
    max_plot_samples: int = 10000
    max_categories: int = 20
    threads: int = 2

    def __post_init__(self):
        for name, value in asdict(self).items():
            if type(value) is not int or value < (0 if name == 'seed' else 1):
                raise InputError(f'{name} must be an integer in the supported positive range (seed may be zero).')


def sampled_metrics(X, Y, config):
    """Compare all coordinates of Y against Euclidean geometry of X on one sample."""
    n, p = X.shape
    m = min(n, config.max_samples)
    # Conservative working-array estimate; input storage/library overhead excluded.
    while m and 32*m*p + 128*m*m + 32*m*Y.shape[1] > config.max_working_bytes:
        m //= 2
    result = {'sample_size': m, 'sample_positions': [], 'metrics': {}, 'skipped': {}}
    if m < 3:
        result['skipped']['geometry'] = 'Fewer than 3 observations fit the sample/resource budget.'
        return result
    indices = np.sort(np.random.default_rng(config.seed).choice(n, m, replace=False))
    result['sample_positions'] = indices.tolist()
    k = min(config.neighbors, (m-1)//2)
    result['neighbors'] = k
    A = pairwise_distances(X[indices], metric='euclidean')
    B = pairwise_distances(Y[indices], metric='euclidean')
    if not np.isfinite(A).all() or not np.isfinite(B).all():
        result['skipped']['geometry'] = 'Pairwise distances overflowed; scores are undefined.'
        return result
    a, b = A[np.triu_indices(m, 1)], B[np.triu_indices(m, 1)]
    if np.max(a) == 0 or np.max(b) == 0:
        result['skipped']['geometry'] = 'Input sample or embedding sample has no nonzero distances.'
        return result
    scores = result['metrics']
    scores['trustworthiness'] = float(trustworthiness(A, Y[indices], n_neighbors=k, metric='precomputed'))
    # Normalize before sums to avoid overflow; raw error preserves coordinate scale.
    scale = max(float(a.max()), float(b.max()))
    aa, bb = a/scale, b/scale
    scores['normalized_distance_error'] = float(np.linalg.norm(aa-bb)/np.linalg.norm(aa))
    alpha = float(np.dot(aa, bb)/np.dot(bb, bb))
    scores['scale_aligned_distance_error'] = float(np.linalg.norm(aa-alpha*bb)/np.linalg.norm(aa))
    result['distance_scale_factor'] = alpha
    if np.ptp(a) and np.ptp(b):
        scores['distance_spearman'] = float(spearmanr(a, b).statistic)
    else:
        result['skipped']['distance_spearman'] = 'Constant pairwise distances.'
    np.fill_diagonal(A, np.inf)
    np.fill_diagonal(B, np.inf)
    na = np.argsort(A, axis=1, kind='stable')[:, :k]
    nb = np.argsort(B, axis=1, kind='stable')[:, :k]
    scores['neighbor_overlap'] = float(np.mean([len(set(x) & set(y))/k for x, y in zip(na, nb)]))
    for key in list(scores):
        if not np.isfinite(scores[key]):
            del scores[key]
            result['skipped'][key] = 'Numerically undefined score.'
    return result


def render_plot(Y, ids, labels, out, method, config, color_column=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    positions = np.sort(np.random.default_rng(config.seed).choice(len(Y), min(len(Y), config.max_plot_samples), replace=False))
    view = Y[positions, :2]
    ordinate = view[:, 1] if view.shape[1] > 1 else np.zeros(len(view))
    fig, ax = plt.subplots(figsize=(9, 6), layout='constrained')
    info = {'sample_positions': positions.tolist(), 'sample_size': len(positions),
            'representation_dimensions': Y.shape[1], 'view_dimensions': min(2, Y.shape[1]),
            'color_column': color_column, 'color_status': 'uncolored',
            'description': 'First coordinates of the saved embedding; no new 2D fit.'}
    if color_column is None and labels is not None and len(labels.columns) == 2:
        color_column = labels.columns[1]
        info['color_column'] = color_column
    if color_column is not None:
        if labels is None or color_column not in labels.columns[1:]:
            plt.close(fig)
            raise InputError('Requested color column is not available in labels or observation metadata.')
        values = labels[color_column].iloc[positions].replace('', '(missing)')
        categories = sorted(values.unique())
        if len(categories) <= config.max_categories:
            for j, category in enumerate(categories):
                mask = values.to_numpy() == category
                ax.scatter(view[mask, 0], ordinate[mask], s=7, alpha=.55,
                           color=plt.get_cmap('tab20')(j % 20), label=str(category))
            ax.legend(title=color_column, loc='center left', bbox_to_anchor=(1, .5), markerscale=2)
            info['color_status'] = 'categorical'
        else:
            info['color_status'] = 'skipped: category count exceeds configured limit'
    if info['color_status'] != 'categorical':
        ax.scatter(view[:, 0], ordinate, s=7, alpha=.5, color='#286b91')
    ax.set(xlabel='Component 1' if method == 'pca' else 'Coordinate 1',
           ylabel=('Component 2' if method == 'pca' else 'Coordinate 2') if Y.shape[1] > 1 else 'Display baseline (not a dimension)',
           title=f'{method.upper()} | first {min(2, Y.shape[1])} of {Y.shape[1]} dimensions\n{len(positions):,} of {len(Y):,} observations')
    ax.spines[['top', 'right']].set_visible(False)
    fig.savefig(out / 'embedding.png', dpi=160)
    fig.savefig(out / 'embedding.svg')
    plt.close(fig)
    frame = pd.DataFrame(view, columns=[f'dimension_{i+1}' for i in range(view.shape[1])])
    frame.insert(0, 'observation_id', ids.iloc[positions].to_numpy())
    frame.to_csv(out / 'plotted_coordinates.csv', index=False)
    return info


def evaluate(preprocessing_run, execution_run, out, *, config=None, color_column=None):
    config = config or EvaluationConfig()
    pre, run, out = Path(preprocessing_run)/'preprocessed', Path(execution_run), Path(out)
    if out.exists():
        raise InputError('Choose a new evaluation output directory.')
    record = read(run/'execution.json')
    if record['status'] != 'execution_complete':
        raise InputError('Evaluation requires completed execution.')
    profile = read(pre/'profile.json')
    matrix = pre/('measurements.sparse.npz' if profile['storage'].startswith('sparse') else 'measurements.npy')
    if sha256(matrix) != record['input_sha256'] or sha256(run/'embedding.npy') != record['embedding_sha256']:
        raise InputError('Matrix or embedding fingerprint does not match execution.')
    X = sparse.load_npz(matrix) if matrix.suffix == '.npz' else np.load(matrix, mmap_mode='r', allow_pickle=False)
    Y = np.load(run/'embedding.npy', mmap_mode='r', allow_pickle=False)
    obs = pd.read_csv(pre/'observations.csv', dtype=str, keep_default_na=False)
    saved_obs = pd.read_csv(run/'observations.csv', dtype=str, keep_default_na=False)
    ids = obs.iloc[:, 0]
    if not ids.equals(saved_obs.iloc[:, 0]) or ids.duplicated().any():
        raise InputError('Observation identifiers are not aligned.')
    if Y.ndim != 2 or Y.shape[0] != X.shape[0] or len(ids) != len(Y) or list(Y.shape) != record['output_shape'] or not np.isfinite(Y).all():
        raise InputError('Invalid embedding shape, alignment or values.')
    labels = None
    if (pre/'labels.csv').exists():
        labels = pd.read_csv(pre/'labels.csv', dtype=str, keep_default_na=False)
        if not labels.iloc[:, 0].equals(ids):
            raise InputError('Labels are not aligned with observations.')
    if color_column is not None and color_column in obs.columns[1:]:
        labels = obs
    if color_column is not None and (labels is None or color_column not in labels.columns[1:]):
        raise InputError('Unknown color column.')
    out.mkdir(parents=True)
    report = {'status': 'running', 'config': asdict(config), 'method': record['final_method'],
              'representation_dimensions': Y.shape[1], 'input_sha256': record['input_sha256'],
              'embedding_sha256': record['embedding_sha256'], 'execution_sha256': sha256(run/'execution.json'),
              'versions': {name: version(name) for name in ('numpy', 'scipy', 'scikit-learn', 'matplotlib')},
              'fallback_occurred': record['fallback_occurred'], 'execution_notices': record['notices'],
              'limitations': ['Metrics compare Euclidean distances in preprocessed feature space, not raw data or biological truth.',
                  'Neighborhoods are within the recorded sample, not the full dataset; ties can affect ranks.',
                  'Scores are descriptive in-sample evidence, not held-out validation or proof of an optimal plan.',
                  'Memory estimate bounds working arrays heuristically; input storage and library overhead are excluded.',
                  'First-coordinate plots can hide structure. Labels color plots only and do not influence scores.',
                  'Euclidean distortion need not match nonlinear methods objectives; no universal pass/fail threshold.']}
    if record['final_method'] in ('kernel_pca', 'laplacian_eigenmaps', 'diffusion_maps', 'tsne', 'umap'):
        report['limitations'].append('Nonlinear axes and eigenvalues are not original-feature explained variance. t-SNE/UMAP visual grouping and intercluster spacing are not biological validation or faithful global distances.')
    write(out/'evaluation.json', report)
    try:
        with threadpool_limits(limits=config.threads):
            report['embedding'] = sampled_metrics(X, Y, config)
            report['view'] = (sampled_metrics(X, Y[:, :2], replace(config, max_samples=max(1, report['embedding']['sample_size'])))
                              if Y.shape[1] > 2 else report['embedding'])
            report['method_metrics'] = record['attempts'][-1].get('metrics', {})
            report['method_metrics_source'] = 'Successful execution fit; method-specific quantities are not comparable across methods.'
            report['plot'] = render_plot(Y, ids, labels, out, record['final_method'], config, color_column)
    except Exception as exc:
        report.update(status='evaluation_failed', error_type=type(exc).__name__, error=str(exc))
        write(out/'evaluation.json', report)
        raise
    rows = [{'scope': scope, 'metric': key, 'value': value} for scope in ('embedding', 'view') for key, value in report[scope]['metrics'].items()]
    pd.DataFrame(rows, columns=['scope', 'metric', 'value']).to_csv(out/'metrics.csv', index=False)
    text = '# Embedding evaluation\n\n' + f"Method: {report['method']}; representation: {Y.shape[1]} dimensions.\n\n"
    text += '![Embedding](embedding.png)\n\n'
    for scope in ('embedding', 'view'):
        text += f"## {scope.capitalize()}\n\nSample size: {report[scope]['sample_size']}\n\n"
        text += '\n'.join(f'- {k}: {v:.6g}' for k, v in report[scope]['metrics'].items()) + '\n\n'
        text += '\n'.join(f'- Skipped {k}: {v}' for k, v in report[scope]['skipped'].items()) + '\n\n'
    text += '## Execution metrics\n\n' + str(report['method_metrics']) + '\n\n## Limitations\n\n'
    text += '\n'.join('- '+s for s in report['limitations'])
    text += '\n\n## Execution notices\n\n' + '\n\n'.join(record['notices'])
    text += '\n\nThis deterministic evaluation summary is not the final AI analysis report.\n'
    (out/'evaluation_summary.md').write_text(text, encoding='utf-8')
    report['status'] = 'evaluation_complete'
    write(out/'evaluation.json', report)
    return report
