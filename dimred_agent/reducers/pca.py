"""Centered PCA; sparse data stays sparse with ARPACK."""
from sklearn.decomposition import PCA


def fit(X, plan, seed):
    model = PCA(n_components=plan['n_components'], **plan['parameters'],
                whiten=False, random_state=seed, copy=True,
                tol=0.0, iterated_power=7, n_oversamples=10,
                power_iteration_normalizer='QR')
    Y = model.fit_transform(X)
    return Y, {'explained_variance_ratio': model.explained_variance_ratio_.tolist(),
               'singular_values': model.singular_values_.tolist()}, model.get_params()
