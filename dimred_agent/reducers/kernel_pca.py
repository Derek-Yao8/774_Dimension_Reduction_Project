"""RBF Kernel PCA; kernel eigenvalues are not original-feature variance ratios."""
import numpy as np
from sklearn.decomposition import KernelPCA
from .kernel_utils import median_squared_distance


def fit(X, plan, seed):
    gamma = plan['parameters']['gamma']
    sample_size = 0
    if gamma == 'median':
        median, sample_size = median_squared_distance(X, seed)
        gamma = 1.0/median
    if not np.isfinite(gamma) or gamma <= 0:
        raise ValueError('RBF gamma must be finite and positive.')
    model = KernelPCA(n_components=plan['n_components'], kernel='rbf', gamma=gamma,
                      eigen_solver='arpack', random_state=seed, n_jobs=1,
                      fit_inverse_transform=False, tol=0, max_iter=1000)
    Y = model.fit_transform(X)
    return Y, {'kernel_eigenvalues': model.eigenvalues_.tolist(), 'effective_gamma': float(gamma),
               'bandwidth_sample_size': sample_size}, model.get_params()
