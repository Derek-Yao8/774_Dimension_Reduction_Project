import json
import time
import numpy as np
import pytest
from scipy import sparse
from dimred_agent.data import InputError
from dimred_agent.dimension_selection import DimensionConfig, select_candidate, search_dimensions
from dimred_agent.dimension_metrics import measure, normalized_distance_error
from dimred_agent.execution import execute
from test_execution import inputs


@pytest.mark.parametrize('kwargs', [{'variance_target':0}, {'max_fits':True}, {'candidates':(3,2)},
                                    {'complexity_penalty':float('nan')}, {'evaluation_samples':2}, {'total_seconds':0}])
def test_invalid_configuration(kwargs):
    with pytest.raises(InputError):
        DimensionConfig(**kwargs)


def test_pca_smallest_threshold_or_explicit_unmet():
    records=[{'status':'complete','dimensions':d,'cumulative_variance':v} for d,v in [(1,.6),(2,.91),(3,1.)]]
    chosen,reached=select_candidate(records,'pca',DimensionConfig(),3)
    assert chosen['dimensions']==2 and reached
    chosen,reached=select_candidate(records[:1],'pca',DimensionConfig(),3)
    assert chosen['dimensions']==1 and not reached


def test_nonlinear_criterion_and_complexity_tradeoff():
    records=[{'status':'complete','dimensions':d,'loss':v,'normalized_distance_error':v} for d,v in [(2,.2),(3,.199)]]
    chosen,reached=select_candidate(records,'mds',DimensionConfig(),3)
    assert chosen['dimensions']==2 and not reached
    records.append({'status':'complete','dimensions':5,'loss':.05,'normalized_distance_error':.05})
    assert select_candidate(records,'mds',DimensionConfig(),5)[0]['dimensions']==5


def test_lle_requires_both_targets():
    records=[{'status':'complete','dimensions':2,'trustworthiness':.99,'normalized_reconstruction':.2,'loss':.03},
             {'status':'complete','dimensions':3,'trustworthiness':.98,'normalized_reconstruction':.05,'loss':.025}]
    chosen,reached=select_candidate(records,'lle',DimensionConfig(),3)
    assert chosen['dimensions']==3 and reached


def test_distance_formula_and_lle_identity():
    assert normalized_distance_error(np.array([3.,4.]),np.array([0.,0.]))==1
    x=np.random.default_rng(0).normal(size=(20,3))
    plan={'method':'lle','parameters':{'n_neighbors':5,'reg':.001}}
    config={'evaluation_samples':20,'evaluation_neighbors':3}
    result=measure(x,x,plan,config)
    assert result['trustworthiness']==pytest.approx(1)
    assert 0 <= result['normalized_reconstruction'] < .1


@pytest.mark.parametrize('method', ['pca','mds','isomap','lle'])
def test_real_auto_execution_for_each_method(tmp_path,method):
    pre,sel,_=inputs(tmp_path,method)
    result=execute(pre,sel,tmp_path/'out',allow_fallback=False,
                   dimension_config=DimensionConfig(max_dimensions=3,candidates=(1,2,3),total_seconds=60))
    assert result['status']=='execution_complete'
    assert 1 <= result['selected_dimensions'] <= 3
    audit=json.loads((tmp_path/'out/dimension_selection.json').read_text())
    assert audit['fit_count'] <= (1 if method=='pca' else 3)
    assert result['fallback_planner_calls']==0
    assert result['output_shape']==[35,result['selected_dimensions']]
    view=json.loads((tmp_path/'out/visualization_view.json').read_text())
    assert view['view_dimensions']==min(2,result['selected_dimensions'])


def test_time_and_memory_budgets_do_not_trigger_ai(tmp_path, monkeypatch):
    pre,sel,profile=inputs(tmp_path)
    from dimred_agent.execution import load_inputs
    matrix,ids,selection,evidence,_=load_inputs(pre,sel)
    called=[]
    monkeypatch.setattr('dimred_agent.execution.run_worker',lambda *a,**k:called.append(1))
    result=search_dimensions(matrix,selection['plan'],tmp_path/'time',60,1,DimensionConfig(),evidence,deadline=time.monotonic()-1)
    assert result['error_type']=='TimeBudget' and called==[]
    evidence['resource_limits']['max_working_bytes']=1
    result=search_dimensions(matrix,selection['plan'],tmp_path/'memory',60,1,DimensionConfig(),evidence)
    assert result['error_type']=='DimensionBudget' and called==[]


def test_failed_candidate_then_success_and_fit_cap(tmp_path, monkeypatch):
    pre,sel,_=inputs(tmp_path,'mds')
    from dimred_agent.execution import load_inputs
    matrix,ids,selection,evidence,_=load_inputs(pre,sel)
    calls=[]
    def fake(matrix,plan,directory,timeout,threads,evaluation=None):
        calls.append(plan['n_components'])
        directory.mkdir()
        if len(calls)==1:
            return {'status':'failed','error':'injected','error_type':'ValueError'}
        np.save(directory/'embedding.npy',np.arange(35*plan['n_components']).reshape(35,-1))
        return {'status':'complete','metrics':{},'effective_parameters':{},'dimension_metrics':{'normalized_distance_error':.4}}
    monkeypatch.setattr('dimred_agent.execution.run_worker',fake)
    result=search_dimensions(matrix,selection['plan'],tmp_path/'search',60,1,
                             DimensionConfig(candidates=(1,2,3),max_fits=2),evidence)
    assert calls==[1,2]
    assert result['status']=='complete' and result['selected_dimensions']==2
    assert not result['dimension_selection']['target_reached']
    assert result['dimension_selection']['stop_reason']=='fit_budget'
