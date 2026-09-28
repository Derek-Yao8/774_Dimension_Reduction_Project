"""Standard LLE on dense data."""
from scipy import sparse
from sklearn.manifold import LocallyLinearEmbedding
from .isomap import check_graph


def fit(X, plan, seed):
    if sparse.issparse(X):
        raise ValueError('Sparse LLE is unsupported; no implicit densification.')
    check_graph(X, plan['parameters']['n_neighbors'])
    model = LocallyLinearEmbedding(n_components=plan['n_components'], **plan['parameters'],
                                  method='standard', eigen_solver='arpack', random_state=seed,
                                  n_jobs=1, neighbors_algorithm='brute', tol=1e-6, max_iter=1000)
    Y = model.fit_transform(X)
    return Y, {'reconstruction_error': float(model.reconstruction_error_)}, model.get_params()
