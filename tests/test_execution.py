import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from scipy.spatial.distance import pdist
from dimred_agent.data import Dataset, InputError
from dimred_agent.profile import profile_dataset
from dimred_agent.reducers import fit_reducer
from dimred_agent.execution import execute, run_worker, write, sha256
from dimred_agent.reduction_planner import planning_evidence
from test_reduction_planner import ready, Fake


def plan_for(x, method):
    profile = profile_dataset(Dataset(x, pd.DataFrame(index=range(len(x))), pd.DataFrame(index=range(x.shape[1]))))
    plan = json.loads(ready(planning_evidence(profile), method)['plan_json'])
    if method in ('isomap', 'lle'):
        plan['parameters']['n_neighbors'] = 8
    return plan


def test_pca_matches_independent_svd_dense_and_sparse():
    x = np.random.default_rng(2).normal(size=(40, 6)) + 10
    plan = plan_for(x, 'pca')
    plan['parameters']['svd_solver'] = 'arpack'
    u, s, _ = np.linalg.svd(x - x.mean(0), full_matrices=False)
    expected = u[:, :2] * s[:2]
    for matrix in (x, sparse.csr_matrix(x)):
        Y, details = fit_reducer(matrix, plan)
        np.testing.assert_allclose(Y @ Y.T, expected @ expected.T, atol=1e-9)
        np.testing.assert_allclose(details['metrics']['explained_variance_ratio'], s[:2]**2 / (s**2).sum(), atol=1e-10)


@pytest.mark.parametrize('method', ['mds', 'isomap', 'lle'])
def test_manifold_execution_and_reproducibility(method):
    x = np.random.default_rng(7).normal(size=(35, 4))
    original = x.copy()
    plan = plan_for(x, method)
    Y, details = fit_reducer(x, plan)
    repeat, _ = fit_reducer(x, plan)
    assert Y.shape == (35, 2) and np.isfinite(Y).all()
    np.testing.assert_allclose(pdist(Y), pdist(repeat), atol=1e-7)
    np.testing.assert_array_equal(x, original)
    if method == 'mds':
        assert details['metrics']['raw_stress'] == pytest.approx(np.sum((pdist(x)-pdist(Y))**2), rel=1e-6)


def test_disconnected_graph_is_not_silently_bridged():
    x = np.r_[np.zeros((10, 4)), np.ones((10, 4))*100]
    plan = plan_for(x, 'isomap')
    with pytest.raises(ValueError, match='components'):
        fit_reducer(x, plan)


def inputs(tmp_path, method='pca'):
    x = np.random.default_rng(7).normal(size=(35, 4))
    pre, sel = tmp_path/'pre', tmp_path/'sel'
    folder = pre/'preprocessed'
    folder.mkdir(parents=True)
    sel.mkdir()
    np.save(folder/'measurements.npy', x)
    pd.DataFrame({'observation_id': [f'cell_{i}' for i in range(len(x))]}).to_csv(folder/'observations.csv', index=False)
    profile = profile_dataset(Dataset(x, pd.DataFrame(index=range(len(x))), pd.DataFrame(index=range(4))))
    profile['provenance']['preprocessing_plan'] = {'reason': 'fixture'}
    write(folder/'profile.json', profile)
    write(pre/'run.json', {'status':'preprocessing_complete','plan':{'reason':'fixture'},'output_shape':list(x.shape)})
    write(sel/'diagnostics.json', {'status':'complete','input_shape':list(x.shape),'source_sha256':sha256(folder/'measurements.npy')})
    plan = plan_for(x, method)
    write(sel/'selection.json', {'status':'selection_complete','plan':plan,'random_state':0,
                                'resource_limits':{'max_working_bytes':1000000000,'max_manifold_observations':5000},
                                'input_profile_sha256':hashlib.sha256(json.dumps(profile,sort_keys=True,allow_nan=False).encode()).hexdigest()})
    return pre, sel, profile


def test_actual_subprocess_outputs_and_ids(tmp_path):
    pre, sel, _ = inputs(tmp_path)
    result = execute(pre, sel, tmp_path/'out', allow_fallback=False, timeout=60)
    assert result['status'] == 'execution_complete'
    assert result['fallback_planner_calls'] == 0
    assert pd.read_csv(tmp_path/'out/embedding.csv').observation_id.tolist() == [f'cell_{i}' for i in range(35)]


def failure(*args):
    return {'status':'failed','error_type':'TestFailure','error':'deliberately injected solver failure'}


def test_one_fallback_disclosed_and_success(tmp_path, capsys):
    pre, sel, profile = inputs(tmp_path, 'isomap')
    planner = Fake([ready(planning_evidence(profile), 'pca')])
    calls=[]
    def worker(matrix, plan, directory, timeout, threads):
        calls.append(plan['method'])
        if len(calls)==1:
            return failure()
        return run_worker(matrix, plan, directory, timeout, threads)
    result = execute(pre, sel, tmp_path/'out', planner=planner, worker=worker)
    assert calls == ['isomap','pca']
    assert result['fallback_occurred'] and result['final_method']=='pca'
    assert 'FALLBACK SELECTED' in capsys.readouterr().out
    assert 'FALLBACK SUCCEEDED' in (tmp_path/'out/execution_summary.md').read_text()
    assert 'deliberately injected' in planner.prompts[0]


def test_failed_fallback_stops_and_offline_never_calls(tmp_path):
    pre, sel, profile = inputs(tmp_path)
    planner = Fake([ready(planning_evidence(profile), 'mds')])
    result = execute(pre, sel, tmp_path/'out', planner=planner, worker=failure)
    assert result['status']=='execution_failed' and len(result['attempts'])==2
    assert len(planner.prompts)==1
    offline = Fake([])
    result = execute(pre, sel, tmp_path/'offline', planner=offline, worker=failure, allow_fallback=False)
    assert len(result['attempts'])==1 and offline.prompts==[]


def test_stale_matrix_stops_before_worker(tmp_path):
    pre, sel, _ = inputs(tmp_path)
    np.save(pre/'preprocessed/measurements.npy', np.ones((35,4)))
    with pytest.raises(InputError, match='fingerprint'):
        execute(pre, sel, tmp_path/'out', worker=lambda *args: pytest.fail('should not run'))


def test_timeout_is_recorded(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('test', 1)
    monkeypatch.setattr(subprocess, 'run', timeout)
    result = run_worker(Path('unused'), {}, tmp_path/'attempt', 1, 1)
    assert result['status']=='failed' and result['error_type']=='Timeout'


def test_no_eligible_fallback_or_environment_retries(tmp_path):
    pre, sel, _ = inputs(tmp_path)
    selection=json.loads((sel/'selection.json').read_text())
    selection['resource_limits']['max_manifold_observations']=1
    write(sel/'selection.json',selection)
    planner=Fake([])
    result=execute(pre,sel,tmp_path/'out',planner=planner,worker=failure)
    assert result['status']=='execution_failed' and planner.prompts==[]
    assert 'FALLBACK UNAVAILABLE' in result['notices'][-1]
    def missing(*args):
        return {'status':'failed','error_type':'ModuleNotFoundError','error':'missing dependency'}
    result=execute(pre,sel,tmp_path/'env',planner=planner,worker=missing)
    assert len(result['attempts'])==1 and planner.prompts==[]
