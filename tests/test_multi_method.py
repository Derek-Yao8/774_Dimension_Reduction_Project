import json
import pytest
from dimred_agent.pipeline import run_pipeline, defaults
from dimred_agent.multi_method import validate_multi
from dimred_agent.reduction_planner import METHODS, planning_evidence, parameter_templates
from dimred_agent.execution import read, write
from dimred_agent.data import InputError
from dimred_agent.codex_planner import CodexPlanner, PlannerError
from dimred_agent.replay import replay_pipeline
from dimred_agent.reporting import HEADINGS, digest
from test_pipeline import data, Planner
from test_reduction_planner import profile


def response(evidence, selected):
    params = parameter_templates(evidence)
    params['tsne']['max_iter'] = 300
    params['umap']['n_epochs'] = 50
    assessments = {m:dict(suitable=m in selected, scientific_reason='Suitable for the stated exploratory objective.' if m in selected else 'Not suitable for this test objective.',
        feasibility_reason='See resource eligibility.', parameters=params[m] if m in selected and evidence['eligibility'][m]['eligible'] else {},
        limitations=['Not evidence of optimality.']) for m in evidence['available_methods']}
    return dict(status='ready', questions=[], explanation='Set of methods, no ranking.',
                plan_json=json.dumps(dict(reason='Explore each suitable representation.',assessments=assessments)))


class MultiPlanner(Planner):
    def __init__(self, selected=('pca','kernel_pca')):
        super().__init__()
        self.selected = selected

    def propose(self, prompt, directory, *, images=()):
        if 'Select ALL scientifically' in prompt:
            self.calls += 1
            return response(read(directory.parent/'selection_evidence.json'), self.selected)
        if 'Write a consolidated analysis report' in prompt:
            self.calls += 1
            visual = read(directory.parent/'visual_inputs.json')
            assert len(images) == len(visual)
            assert all(p.is_file() for p in images)
            return dict(status='ready', questions=[], explanation='Individual results.', plan_json=json.dumps({
                'evidence_digest':digest(json.loads((directory.parent/'evidence.json').read_text())),
                'visual_interpretations':[dict(image_id=e['image_id'],status='inspected',
                    observations=['Synthetic fixture observation, not live visual reasoning.'],
                    relation_to_metrics='See recorded sample metrics.', limitations=['No biological validation.'],
                    evidence_refs=[e['image_id'],e['metrics_ref']]) for e in visual],
                'sections':[dict(heading=h,claims=[dict(text='The recorded set was selected.',evidence_refs=['selection_set'])]) for h in HEADINGS]}))
        return super().propose(prompt,directory)


def test_set_contract_and_new_default():
    evidence = planning_evidence(profile())
    assert defaults()['method_policy'] == 'all_suitable'
    bundle = validate_multi(response(evidence,('pca','umap')),evidence)
    assert set(bundle['plans']) == {'pca','umap'}
    evidence['eligibility']['umap']['eligible'] = False
    assert list(validate_multi(response(evidence,('pca','umap')),evidence)['plans']) == ['pca']
    assert validate_multi(response(evidence,()),evidence)['plans'] == {}


@pytest.mark.parametrize('fault', ['missing','nonbool','extra_parameter'])
def test_invalid_set_rejected(fault):
    evidence = planning_evidence(profile())
    proposed = response(evidence,('pca',))
    plan = json.loads(proposed['plan_json'])
    if fault == 'missing':
        del plan['assessments']['umap']
    elif fault == 'nonbool':
        plan['assessments']['pca']['suitable'] = 'yes'
    else:
        plan['assessments']['pca']['parameters']['unknown'] = 1
    proposed['plan_json'] = json.dumps(plan)
    with pytest.raises(InputError):
        validate_multi(proposed,evidence)


def test_all_nine_full_workflow_and_offline_replay(tmp_path,monkeypatch):
    planner = MultiPlanner(tuple(METHODS))
    source = tmp_path/'source'
    run = run_pipeline(data(tmp_path),source,overrides={'loader':{'orientation':'rows'},
        'execution':{'allow_fallback':False}},planner=planner)
    assert run['status']=='pipeline_complete', run.get('detail')
    assert len(run['method_results'])==9 and planner.calls==3
    report_text = (source/run['report']).read_text()
    assert 'Complete selection and exclusion record' not in report_text
    assert 'Initial configuration and provenance' not in report_text
    assert 'Supporting records' in report_text
    assert '## Visual interpretation' in report_text
    assert read(source/'report/report_generation.json')['visual_interpretation']=='complete'
    assert len(read(source/'report/visual_inputs.json'))==9
    evidence = read(source/'report/evidence.json')
    assert len(evidence['selection_set']['assessments']) == 9
    assert evidence['configuration'] == run['configuration']
    samples = [read(source/('evaluation_'+m)/'evaluation.json')['embedding']['sample_positions'] for m in METHODS]
    assert all(s==samples[0] for s in samples)
    again = run_pipeline(data(tmp_path),source,resume=True,planner=planner)
    assert again['status']=='pipeline_complete' and planner.calls==3
    def forbidden(*args,**kwargs):
        raise AssertionError('No live model calls allowed')
    monkeypatch.setattr(CodexPlanner,'__init__',forbidden)
    replay = replay_pipeline(source,tmp_path/'replay')
    assert replay['status']=='replay_complete', replay
    assert replay['comparison_matches'] and replay['model_calls_attempted']==0


def test_failed_method_continues_and_report_resume(tmp_path,monkeypatch):
    import dimred_agent.multi_method as multi
    real = multi.execute
    def execute(pre,selection,target,**kwargs):
        if selection.name=='kernel_pca':
            target.mkdir()
            record=dict(status='execution_failed',final_method=None,fallback_planner_calls=0,
                        attempts=[],fallback_occurred=False,notices=['Injected failure'])
            write(target/'execution.json',record)
            return record
        return real(pre,selection,target,**kwargs)
    monkeypatch.setattr(multi,'execute',execute)
    class Unavailable:
        def propose(self,*args,**kwargs):
            raise PlannerError('Temporary report failure')
    raw, source, planner = data(tmp_path),tmp_path/'source',MultiPlanner(('kernel_pca','pca','mds'))
    run = run_pipeline(raw,source,overrides={'loader':{'orientation':'rows'}},planner=planner,reporter=Unavailable())
    assert run['status']=='pipeline_failed' and run['current_stage']=='report'
    assert run['stages']['evaluation_mds']['status']=='complete'
    hashes = run['stages']['execution_pca']['files']
    run = run_pipeline(raw,source,resume=True,planner=planner)
    assert run['status']=='pipeline_partial'
    assert run['method_results']['kernel_pca']['status']=='execution_failed'
    assert run['stages']['execution_pca']['files']==hashes
    replay = replay_pipeline(source,tmp_path/'replay')
    assert replay['comparison_matches']
    assert replay['methods']['kernel_pca']['status']=='historical_failure_not_rerun'


def test_one_fallback_budget_across_set_and_evaluation_failure(tmp_path,monkeypatch):
    import dimred_agent.multi_method as multi
    real = multi.execute
    seen = []
    def execute(pre,selection,target,**kwargs):
        seen.append((selection.name,kwargs['allow_fallback'],kwargs['excluded_fallback_methods']))
        if selection.name=='pca':
            target.mkdir()
            record=dict(status='execution_failed',final_method=None,fallback_planner_calls=1,
                        attempts=[],fallback_occurred=False,notices=['Injected exhausted fallback'])
            write(target/'execution.json',record)
            return record
        return real(pre,selection,target,**kwargs)
    monkeypatch.setattr(multi,'execute',execute)
    def fail_evaluation(*args,**kwargs):
        raise ValueError('Injected evaluation failure')
    monkeypatch.setattr(multi,'evaluate',fail_evaluation)
    run=run_pipeline(data(tmp_path),tmp_path/'run',overrides={'loader':{'orientation':'rows'},
        'report':{'mode':'evidence_only'}},planner=MultiPlanner())
    assert run['status']=='pipeline_partial'
    assert seen[0][1] and not seen[1][1]
    assert all(set(s[2])=={'pca','kernel_pca'} for s in seen)
    assert run['method_results']['kernel_pca']['status']=='evaluation_failed'


def test_no_suitable_methods_stops_before_fitting(tmp_path):
    run=run_pipeline(data(tmp_path),tmp_path/'run',overrides={'loader':{'orientation':'rows'}},planner=MultiPlanner(()))
    assert run['status']=='pipeline_failed'
    assert run['detail']['status']=='no_suitable_methods'
    assert not any(k.startswith('execution') for k in run['stages'])


def test_multi_automatic_dimensions_replay(tmp_path):
    source=tmp_path/'source'
    run=run_pipeline(data(tmp_path),source,overrides={'loader':{'orientation':'rows'},
        'dimension_mode':'auto','dimension_search':{'candidates':[2,3],'max_fits':2,'variance_target':.1},
        'report':{'mode':'evidence_only'}},planner=MultiPlanner())
    assert run['status']=='pipeline_complete', run.get('detail')
    assert read(source/'execution_pca/execution.json')['output_shape'][1]==1
    assert read(source/'execution_kernel_pca/execution.json')['output_shape'][1] in (2,3)
    replay=replay_pipeline(source,tmp_path/'replay')
    assert replay['comparison_matches'], replay
