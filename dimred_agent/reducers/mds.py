"""Metric Euclidean MDS, one random initialization; no preliminary reducer."""
from scipy import sparse
from sklearn.manifold import MDS


def fit(X, plan, seed):
    model = MDS(n_components=plan['n_components'], **plan['parameters'],
                metric_mds=True, metric='euclidean', n_init=1, init='random',
                random_state=seed, n_jobs=1, normalized_stress=False)
    Y = model.fit_transform(X.toarray() if sparse.issparse(X) else X)
    return Y, {'raw_stress': float(model.stress_), 'iterations': int(model.n_iter_),
               'iteration_limit_reached': bool(model.n_iter_ >= plan['parameters']['max_iter'])}, model.get_params()
