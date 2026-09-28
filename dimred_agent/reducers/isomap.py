"""Isomap with no automatic repair of disconnected neighbor graphs."""
from sklearn.manifold import Isomap
from sklearn.neighbors import kneighbors_graph
from scipy.sparse.csgraph import connected_components


def check_graph(X, k):
    graph = kneighbors_graph(X, k, mode='connectivity', metric='euclidean', include_self=False, n_jobs=1)
    count = connected_components(graph.maximum(graph.T), directed=False, return_labels=False)
    if count != 1:
        raise ValueError(f'Full-data neighborhood graph has {count} components at k={k}; automatic bridging is disabled.')


def fit(X, plan, seed):
    check_graph(X, plan['parameters']['n_neighbors'])
    model = Isomap(n_components=plan['n_components'], **plan['parameters'],
                   eigen_solver='arpack', metric='euclidean', path_method='D',
                   neighbors_algorithm='brute', n_jobs=1, tol=0, max_iter=1000)
    Y = model.fit_transform(X)
    return Y, {'reconstruction_error': float(model.reconstruction_error())}, model.get_params()
