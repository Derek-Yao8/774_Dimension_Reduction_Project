"""Numerical contracts and complete offline round trips for added reducers."""
import json
import numpy as np
import pytest
from scipy import sparse
from scipy.spatial.distance import cdist
from sklearn.neighbors import kneighbors_graph
from dimred_agent.reducers import REDUCERS, fit_reducer
from dimred_agent.reduction_planner import METHODS
from dimred_agent.execution import read
from test_pipeline import run_pipeline
from dimred_agent.replay import replay_pipeline
from dimred_agent.codex_planner import CodexPlanner
from test_execution import plan_for
from test_pipeline import Planner, data
from test_reduction_planner import ready

ADDED = ('kernel_pca', 'laplacian_eigenmaps', 'diffusion_maps', 'tsne', 'umap')


def fast(plan):
    if plan['method'] == 'tsne':
        plan['parameters']['max_iter'] = 300
    if plan['method'] == 'umap':
        plan['parameters']['n_epochs'] = 50
    return plan


def test_registry_consistency():
    assert set(REDUCERS) == set(METHODS)


@pytest.mark.parametrize('method', ADDED)
def test_dense_sparse_seeded_and_serializable(method):
    x = np.random.default_rng(4).normal(size=(40, 5))
    plan = fast(plan_for(x, method))
    for matrix in (x, sparse.csr_matrix(x)):
        y, details = fit_reducer(matrix, plan)
        repeated, _ = fit_reducer(matrix, plan)
        assert y.shape == (40, 2) and np.isfinite(y).all()
        np.testing.assert_allclose(y, repeated, atol=1e-7)
        json.dumps(details, allow_nan=False)


def test_kernel_pca_matches_centered_kernel_eigendecomposition():
    x = np.random.default_rng(9).normal(size=(40, 5))
    plan = plan_for(x, 'kernel_pca')
    plan['parameters']['gamma'] = .3
    y, details = fit_reducer(x, plan)
    k = np.exp(-.3 * cdist(x, x, 'sqeuclidean'))
    h = np.eye(len(x)) - np.ones((len(x), len(x)))/len(x)
    values, vectors = np.linalg.eigh(h@k@h)
    expected = vectors[:, -2:] * np.sqrt(values[-2:])
    np.testing.assert_allclose(y@y.T, expected@expected.T, atol=1e-8)
    assert 'explained_variance_ratio' not in details['metrics']


def test_diffusion_coordinates_satisfy_markov_eigenproblem():
    x = np.random.default_rng(3).normal(size=(35, 4))
    plan = plan_for(x, 'diffusion_maps')
    plan['parameters'] = {'epsilon': 3., 'alpha': .5, 'diffusion_time': 2}
    y, details = fit_reducer(x, plan)
    k = np.exp(-cdist(x, x, 'sqeuclidean')/3.)
    q = k.sum(axis=1)**.5
    k = k/q[:, None]/q[None, :]
    degree = k.sum(axis=1)
    p = k/degree[:, None]
    values = np.asarray(details['metrics']['diffusion_eigenvalues'])
    psi = y/values**2
    np.testing.assert_allclose(p@psi, psi*values, atol=1e-9)
    np.testing.assert_allclose(psi.T@((degree/degree.sum())[:, None]*psi), np.eye(2), atol=1e-9)


def test_graph_failures_are_explicit():
    x = np.r_[np.zeros((10, 4)), np.ones((10, 4))*100]
    plan = plan_for(x, 'laplacian_eigenmaps')
    plan['parameters']['n_neighbors'] = 4
    with pytest.raises(ValueError, match='components|connected'):
        fit_reducer(x, plan)
    plan = plan_for(x, 'diffusion_maps')
    plan['parameters']['epsilon'] = .01
    with pytest.raises(ValueError, match='Disconnected'):
        fit_reducer(x, plan)


def test_laplacian_coordinates_satisfy_generalized_eigenproblem():
    x = np.random.default_rng(8).normal(size=(40, 5))
    plan = plan_for(x, 'laplacian_eigenmaps')
    y, details = fit_reducer(x, plan)
    graph = kneighbors_graph(x, plan['parameters']['n_neighbors'], mode='connectivity', include_self=False)
    graph = graph.maximum(graph.T)
    degree = np.asarray(graph.sum(axis=1)).ravel()
    values = np.asarray(details['metrics']['laplacian_eigenvalues'])
    np.testing.assert_allclose(degree[:, None]*y - graph@y, degree[:, None]*y*values, atol=1e-8)
    np.testing.assert_allclose(y.T@(degree[:, None]*y), np.eye(2), atol=1e-8)


class MethodPlanner(Planner):
    def __init__(self, method):
        super().__init__()
        self.method = method

    def propose(self, prompt, directory):
        if directory.parent.name == 'selection':
            self.calls += 1
            response = ready(read(directory.parent/'selection_evidence.json'), self.method)
            response['plan_json'] = json.dumps(fast(json.loads(response['plan_json'])))
            return response
        return super().propose(prompt, directory)


@pytest.mark.parametrize('method', ADDED)
@pytest.mark.parametrize('auto', [False, True])
def test_pipeline_reports_and_no_ai_replay(tmp_path, monkeypatch, method, auto):
    source = tmp_path/'source'
    result = run_pipeline(data(tmp_path), source, overrides={
        'loader': {'orientation': 'rows'}, 'report': {'mode': 'evidence_only'},
        'dimension_mode': 'auto' if auto else 'fixed',
        'dimension_search': {'candidates': [2, 3], 'max_fits': 2}}, planner=MethodPlanner(method))
    assert result['status'] == 'pipeline_complete', result
    assert read(source/'execution/execution.json')['attempts'][0]['plan']['method'] == method
    def forbidden(*args, **kwargs):
        raise AssertionError('Replay attempted an AI call')
    monkeypatch.setattr(CodexPlanner, '__init__', forbidden)
    replay = replay_pipeline(source, tmp_path/'replay')
    assert replay['status'] == 'replay_complete', replay
    assert replay['comparison_matches'] and replay['model_calls_attempted'] == 0
