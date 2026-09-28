"""Metrics on a fixed sample for within-method dimension selection."""
import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import shortest_path
from scipy.spatial.distance import pdist
from sklearn.manifold import trustworthiness
from sklearn.metrics import pairwise_distances
from sklearn.neighbors import NearestNeighbors


def normalized_distance_error(reference, embedded):
    denominator = float(np.sum(reference**2))
    if denominator <= 0:
        raise ValueError('Reference distances have zero energy.')
    return float(np.sqrt(np.sum((reference - embedded)**2) / denominator))


def measure(X, Y, plan, config):
    n = X.shape[0]
    m = min(n, config['evaluation_samples'])
    indices = np.sort(np.random.default_rng(0).choice(n, m, replace=False)) if m < n else np.arange(n)
    if m < 4:
        raise ValueError('At least four observations are required for automatic manifold dimension evaluation.')
    method = plan['method']
    summary = {'evaluation_sample_size': m, 'evaluation_sample_positions': indices.tolist()}
    if plan['method'] in ('kernel_pca', 'laplacian_eigenmaps', 'diffusion_maps', 'tsne', 'umap'):
        original = pairwise_distances(X[indices], metric='euclidean')
        if not np.isfinite(original).all() or not np.any(original > 0):
            raise ValueError('No finite nonconstant sampled geometry for dimension evaluation.')
        k_eval = min(config['evaluation_neighbors'], (m - 1)//2)
        summary.update(evaluation_neighbors=k_eval,
                       trustworthiness=float(trustworthiness(original, Y[indices], n_neighbors=k_eval, metric='precomputed')))
        return summary
    embedded = pdist(Y[indices])
    if method == 'mds':
        distances = pairwise_distances(X[indices], metric='euclidean')
        reference = distances[np.triu_indices(m, 1)]
        summary['normalized_distance_error'] = normalized_distance_error(reference, embedded)
    elif method == 'isomap':
        neighbors = NearestNeighbors(n_neighbors=plan['parameters']['n_neighbors'], algorithm='brute', metric='euclidean', n_jobs=1).fit(X)
        graph = neighbors.kneighbors_graph(mode='distance')
        # Same directed=False shortest-path convention as sklearn Isomap; explicit
        # zero-weight edges are retained. Full graph, sampled endpoints only.
        distances = shortest_path(graph, method='D', directed=False, indices=indices)[:, indices]
        if not np.isfinite(distances).all():
            raise ValueError('Disconnected geodesic distances during dimension evaluation.')
        reference = distances[np.triu_indices(m, 1)]
        summary['normalized_distance_error'] = normalized_distance_error(reference, embedded)
    else:
        original = pairwise_distances(X[indices], metric='euclidean')
        k_eval = min(config['evaluation_neighbors'], (m - 1) // 2)
        summary['evaluation_neighbors'] = k_eval
        summary['trustworthiness'] = float(trustworthiness(original, Y[indices], n_neighbors=k_eval, metric='precomputed'))
        k = plan['parameters']['n_neighbors']
        model = NearestNeighbors(n_neighbors=k + 1, metric='euclidean', algorithm='brute', n_jobs=1).fit(X)
        all_neighbors = model.kneighbors(X[indices], return_distance=False)
        residual = 0.
        for position, choices in zip(indices, all_neighbors):
            choices = choices[choices != position][:k]
            offsets = X[choices] - X[position]
            if sparse.issparse(offsets):
                offsets = offsets.toarray()
            gram = offsets @ offsets.T
            trace = float(np.trace(gram))
            gram.flat[::k + 1] += plan['parameters']['reg'] * (trace if trace > 0 else 1.)
            weights = np.linalg.solve(gram, np.ones(k))
            weights /= weights.sum()
            residual += float(np.sum((Y[position] - weights @ Y[choices])**2))
        energy = float(np.sum((Y[indices] - Y.mean(0))**2))
        if energy <= 0:
            raise ValueError('Zero embedding energy for reconstruction evaluation.')
        summary['normalized_reconstruction'] = residual / energy
    if any(not np.isfinite(value) for value in summary.values() if isinstance(value, float)):
        raise ValueError('Nonfinite dimension-selection metrics.')
    return summary
