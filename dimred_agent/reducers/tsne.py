"""Seeded Barnes-Hut t-SNE without an implicit PCA initialization."""
import numpy as np
from sklearn.manifold import TSNE


def fit(X, plan, seed):
    model = TSNE(n_components=plan['n_components'], **plan['parameters'], init='random',
                 method='barnes_hut', metric='euclidean', angle=0.5, random_state=seed, n_jobs=1)
    Y = model.fit_transform(X)
    if not np.isfinite(model.kl_divergence_) or model.kl_divergence_ >= np.finfo(float).max/2:
        raise ValueError('t-SNE did not produce a finite post-exaggeration objective.')
    return Y, {'kl_divergence': float(model.kl_divergence_), 'n_iter': int(model.n_iter_),
               'iteration_limit_reached': bool(model.n_iter_ >= plan['parameters']['max_iter']-1)}, model.get_params()
