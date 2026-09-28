"""Gaussian alpha-normalized diffusion maps via the symmetric Markov conjugate."""
import numpy as np
from scipy.linalg import eigh
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.metrics import pairwise_distances
from .kernel_utils import median_squared_distance


def fit(X, plan, seed):
    params = plan['parameters']
    epsilon = params['epsilon']
    sample_size = 0
    if epsilon == 'median':
        epsilon, sample_size = median_squared_distance(X, seed)
    if not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError('Diffusion epsilon must be finite and positive.')
    distances = pairwise_distances(X, metric='euclidean', squared=True)
    if not np.isfinite(distances).all():
        raise ValueError('Nonfinite diffusion distances.')
    K = np.exp(-distances/epsilon)
    del distances
    np.fill_diagonal(K, 1.0)
    if connected_components(csr_matrix(K > 0), directed=False, return_labels=False) != 1:
        raise ValueError('Disconnected diffusion kernel after underflow; increase epsilon.')
    q = K.sum(axis=1)**params['alpha']
    K /= q[:, None]
    K /= q[None, :]
    degree = K.sum(axis=1)
    root = np.sqrt(degree)
    S = K/root[:, None]/root[None, :]
    del K
    n, d = X.shape[0], plan['n_components']
    values, vectors = eigh(S, subset_by_index=[n-d-1, n-1], check_finite=True)
    values, vectors = values[::-1], vectors[:, ::-1]
    if values[1] >= 1-1e-10:
        raise ValueError('Diffusion kernel is numerically disconnected; increase epsilon.')
    eigenvalues = np.maximum(values[1:], 0)
    psi = vectors[:, 1:]/root[:, None]*np.sqrt(degree.sum())
    Y = psi * eigenvalues**params['diffusion_time']
    residual = np.linalg.norm(S@vectors-vectors*values, axis=0)
    return Y, {'diffusion_eigenvalues': eigenvalues.tolist(), 'stationary_eigenvalue': float(values[0]),
               'symmetric_eigen_residual_max': float(residual.max()), 'effective_epsilon': float(epsilon),
               'bandwidth_sample_size': sample_size}, {
                   'n_components': d, 'epsilon': float(epsilon), 'alpha': params['alpha'],
                   'diffusion_time': params['diffusion_time'], 'kernel': 'exp(-squared_distance/epsilon)',
                   'self_affinity': 1.0, 'normalization': 'stationary_L2', 'eigen_solver': 'scipy_eigh',
                   'drop_stationary': True, 'random_state': seed}
