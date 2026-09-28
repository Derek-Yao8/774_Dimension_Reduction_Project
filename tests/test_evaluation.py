import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from dimred_agent.evaluation import EvaluationConfig, sampled_metrics, evaluate
from dimred_agent.execution import write, sha256
from dimred_agent.data import InputError


def test_identity_scale_and_shuffle():
    X = np.random.default_rng(14).normal(size=(40, 4))
    config = EvaluationConfig()
    identity = sampled_metrics(X, X, config)['metrics']
    assert identity['trustworthiness'] == pytest.approx(1)
    assert identity['neighbor_overlap'] == 1
    assert identity['normalized_distance_error'] == pytest.approx(0, abs=1e-8)
    scaled = sampled_metrics(sparse.csr_matrix(X), X*3, config)['metrics']
    assert scaled['normalized_distance_error'] == pytest.approx(2)
    assert scaled['scale_aligned_distance_error'] == pytest.approx(0, abs=1e-8)
    assert sampled_metrics(X, X[::-1], config)['metrics']['trustworthiness'] < .9


def test_budget_degenerate_and_determinism():
    X = np.random.default_rng(1).normal(size=(40, 3))
    config = EvaluationConfig(max_samples=15)
    assert sampled_metrics(X, X, config) == sampled_metrics(X, X, config)
    assert sampled_metrics(X, X, EvaluationConfig(max_working_bytes=1))['skipped']
    assert sampled_metrics(X, np.zeros_like(X), config)['skipped']
    assert sampled_metrics(X[:2], X[:2], config)['skipped']
    with pytest.raises(InputError):
        EvaluationConfig(neighbors=0)


def fixture_run(tmp_path, labels=True):
    pre, run = tmp_path/'pre', tmp_path/'run'
    (pre/'preprocessed').mkdir(parents=True)
    run.mkdir()
    X = np.random.default_rng(7).normal(size=(30, 4))
    np.save(pre/'preprocessed/measurements.npy', X)
    np.save(run/'embedding.npy', X[:, :3])
    obs = pd.DataFrame({'observation_id': [f'id_{i}' for i in range(len(X))]})
    obs.to_csv(pre/'preprocessed/observations.csv', index=False)
    obs.to_csv(run/'observations.csv', index=False)
    if labels:
        obs.assign(label=['a', 'b']*15).to_csv(pre/'preprocessed/labels.csv', index=False)
    write(pre/'preprocessed/profile.json', {'storage': 'dense'})
    write(run/'execution.json', {'status': 'execution_complete', 'input_sha256': sha256(pre/'preprocessed/measurements.npy'),
          'embedding_sha256': sha256(run/'embedding.npy'), 'output_shape': [30, 3], 'final_method': 'pca',
          'attempts': [{'metrics': {'explained_variance_ratio': [.4, .3, .2]}}], 'notices': [], 'fallback_occurred': False})
    return pre, run


@pytest.mark.parametrize('labels', [True, False])
def test_saved_pipeline(tmp_path, labels):
    pre, run = fixture_run(tmp_path, labels)
    out = tmp_path/'out'
    result = evaluate(pre, run, out)
    assert result['status'] == 'evaluation_complete'
    assert result['plot']['color_status'] == ('categorical' if labels else 'uncolored')
    assert result['embedding']['metrics'] != result['view']['metrics']
    assert (out/'embedding.png').stat().st_size > 1000
    assert (out/'embedding.svg').exists()
    with pytest.raises(InputError):
        evaluate(pre, run, out)


def test_stale_and_misaligned(tmp_path):
    pre, run = fixture_run(tmp_path)
    obs = pd.read_csv(run/'observations.csv').iloc[::-1]
    obs.to_csv(run/'observations.csv', index=False)
    with pytest.raises(InputError, match='aligned'):
        evaluate(pre, run, tmp_path/'bad')
    np.save(run/'embedding.npy', np.ones((30, 3)))
    with pytest.raises(InputError, match='fingerprint'):
        evaluate(pre, run, tmp_path/'bad')
