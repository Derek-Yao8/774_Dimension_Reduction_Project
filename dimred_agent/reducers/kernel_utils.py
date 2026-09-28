"""Deterministic, bounded bandwidth heuristic shared by Gaussian methods."""
import numpy as np
from sklearn.metrics import pairwise_distances


def median_squared_distance(X, seed, max_samples=512):
    m = min(X.shape[0], max_samples)
    positions = np.sort(np.random.default_rng(seed).choice(X.shape[0], m, replace=False))
    distances = pairwise_distances(X[positions], metric='euclidean', squared=True)
    values = distances[np.triu_indices(m, 1)]
    if not np.isfinite(values).all():
        raise ValueError('Bandwidth sample has nonfinite squared distances.')
    positive = values[values > 0]
    if not len(positive):
        raise ValueError('No positive sampled distances for median bandwidth.')
    return float(np.median(positive)), m
