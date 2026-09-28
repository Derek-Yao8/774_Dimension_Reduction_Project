"""Shared fitting interface for the registered reducers."""
import warnings
import numpy as np
from sklearn.exceptions import ConvergenceWarning
from threadpoolctl import threadpool_limits
from . import pca, mds, isomap, lle
from . import kernel_pca, laplacian_eigenmaps, diffusion_maps, tsne, umap
from importlib.metadata import version

REDUCERS = {module.__name__.rsplit('.', 1)[-1]: module for module in
            (pca, mds, isomap, lle, kernel_pca, laplacian_eigenmaps, diffusion_maps, tsne, umap)}


def fit_reducer(X, plan, seed=0, threads=2):
    with threadpool_limits(limits=threads), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        np.random.seed(seed)  # Isomap's ARPACK initializer uses NumPy's global RNG.
        Y, metrics, parameters = REDUCERS[plan['method']].fit(X, plan, seed)
    if any(issubclass(w.category, ConvergenceWarning) for w in caught):
        raise ValueError('Solver issued a convergence warning: ' + '; '.join(str(w.message) for w in caught))
    if Y.shape != (X.shape[0], plan['n_components']) or not np.isfinite(Y).all():
        raise ValueError('Reducer returned wrong-shaped or nonfinite coordinates.')
    if not np.any(np.ptp(Y, axis=0) > 0):
        raise ValueError('Reducer returned a completely collapsed embedding.')
    dependencies = {name: version(name) for name in ('umap-learn', 'numba', 'pynndescent', 'llvmlite')} if plan['method'] == 'umap' else {}
    return Y, {'metrics': metrics, 'effective_parameters': parameters, 'dependency_versions': dependencies,
               'warnings': [str(w.message) for w in caught]}
