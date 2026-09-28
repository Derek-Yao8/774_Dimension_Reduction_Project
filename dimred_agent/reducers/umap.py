"""Seeded, single-thread UMAP. Imported lazily to avoid JIT costs for other methods."""
from scipy.sparse.csgraph import connected_components


def fit(X, plan, seed):
    from umap import UMAP
    model = UMAP(n_components=plan['n_components'], **plan['parameters'],
                 metric='euclidean', init='random', random_state=seed, transform_seed=seed,
                 n_jobs=1, low_memory=True, spread=1.0)
    Y = model.fit_transform(X)
    count = connected_components(model.graph_, directed=False, return_labels=False)
    return Y, {'graph_components': int(count), 'graph_edges_directed': int(model.graph_.nnz),
               'disconnected_layout_caution': bool(count > 1)}, model.get_params()
