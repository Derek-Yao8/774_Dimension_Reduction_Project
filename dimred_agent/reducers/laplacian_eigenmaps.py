"""Normalized Laplacian Eigenmaps on an unweighted symmetric union kNN graph."""
import numpy as np
from sklearn.neighbors import kneighbors_graph
from sklearn.manifold import spectral_embedding
from scipy.sparse.csgraph import connected_components


def fit(X, plan, seed):
    k = plan['parameters']['n_neighbors']
    graph = kneighbors_graph(X, k, mode='connectivity', metric='euclidean', include_self=False, n_jobs=1)
    graph = graph.maximum(graph.T).tocsr()
    components = connected_components(graph, directed=False, return_labels=False)
    if components != 1:
        raise ValueError(f'Laplacian graph has {components} components; no automatic bridging.')
    Y = spectral_embedding(graph, n_components=plan['n_components'], eigen_solver='arpack',
                           random_state=seed, eigen_tol=0.0, norm_laplacian=True, drop_first=True)
    degree = np.asarray(graph.sum(axis=1)).ravel()
    LY = degree[:, None]*Y - graph@Y
    values = np.sum(Y*LY, axis=0)/np.sum(degree[:, None]*Y**2, axis=0)
    residual = np.linalg.norm(LY-degree[:, None]*Y*values, axis=0)
    return Y, {'laplacian_eigenvalues': values.tolist(), 'generalized_eigen_residual_max': float(residual.max()),
               'graph_components': int(components)}, {
                   'n_components': plan['n_components'], 'n_neighbors': k, 'affinity': 'binary_union_knn',
                   'metric': 'euclidean', 'eigen_solver': 'arpack', 'norm_laplacian': True,
                   'drop_first': True, 'random_state': seed, 'n_jobs': 1}
