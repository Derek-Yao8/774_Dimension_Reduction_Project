from dataclasses import asdict
import json
import numpy as np
import pandas as pd
import pytest
from dimred_agent.data import InputError
from dimred_agent.pipeline import run_pipeline as actual_run_pipeline, resolve_config
from dimred_agent.execution import read
from dimred_agent.preprocessing import PreprocessingPlan
from dimred_agent.reporting import HEADINGS
from dimred_agent.codex_planner import PlannerError
from test_reduction_planner import ready


def run_pipeline(*args, **kwargs):
    """Existing tests explicitly exercise the retained single-method contract."""
    if not kwargs.get('resume'):
        kwargs['overrides'] = {'method_policy':'single', **kwargs.get('overrides', {})}
    return actual_run_pipeline(*args, **kwargs)


@pytest.mark.parametrize('permanent', [False, True])
def test_checkpoint_lock_retry_preserves_previous_record(tmp_path, monkeypatch, permanent):
    from pathlib import Path
    from dimred_agent.pipeline import replace_checkpoint
    pending, target = tmp_path/'pending.json', tmp_path/'pipeline.json'
    pending.write_text('new')
    target.write_text('old')
    original = Path.replace
    calls = []
    def locked(path, destination):
        calls.append(1)
        if permanent or len(calls) <= 2:
            assert target.read_text() == 'old'
            raise PermissionError('Simulated checkpoint lock')
        return original(path, destination)
    monkeypatch.setattr(Path, 'replace', locked)
    monkeypatch.setattr('dimred_agent.pipeline.time.sleep', lambda delay: None)
    if permanent:
        with pytest.raises(PermissionError):
            replace_checkpoint(pending, target)
        assert len(calls) == 6 and target.read_text() == 'old'
        assert pending.read_text() == 'new'
    else:
        replace_checkpoint(pending, target)
        assert len(calls) == 3 and target.read_text() == 'new'


class Planner:
    backend = 'test_planner'
    def __init__(self, clarify=False):
        self.calls = 0
        self.clarify = clarify

    def propose(self, prompt, directory):
        self.calls += 1
        if self.clarify:
            return {'status': 'needs_clarification', 'questions': ['Are these counts?'], 'explanation': 'Units missing', 'plan_json': ''}
        if 'Plan fields/defaults:' in prompt:
            return {'status': 'ready', 'questions': [], 'explanation': 'Complete numeric input',
                    'plan_json': json.dumps(asdict(PreprocessingPlan(reason='Preserve complete numeric values; no count transforms.')))}
        if 'Fingerprint:' in prompt:
            fingerprint = prompt.split('Fingerprint: ')[1].split('\n')[0]
            return {'status': 'ready', 'questions': [], 'explanation': 'Report test', 'plan_json': json.dumps({
                'evidence_digest': fingerprint,
                'sections': [{'heading': h, 'claims': [{'text': 'Recorded PCA plan.', 'evidence_refs': ['selection.plan']}]} for h in HEADINGS]})}
        evidence = read(directory.parent/'selection_evidence.json')
        return ready(evidence, 'pca')


def data(tmp_path):
    path = tmp_path/'data.csv'
    pd.DataFrame(np.random.default_rng(0).normal(size=(30, 5)), columns=list('abcde')).to_csv(path, index=False)
    return path


def test_full_workflow_and_resume(tmp_path):
    path = data(tmp_path)
    planner = Planner()
    out = tmp_path/'agent'
    result = run_pipeline(path, out, context='Continuous numeric measurements; no labels.',
                          overrides={'loader': {'orientation': 'rows'}, 'execution': {'threads': 2}}, planner=planner)
    assert result['status'] == 'pipeline_complete'
    assert planner.calls == 3
    assert len(result['model_requests']) == 3
    assert len(result['stages']) == 7
    assert result['configuration']['origins']['execution.threads']['origin'] == 'caller configuration'
    assert result['configuration']['origins']['dimensions']['origin'] == 'application default'
    ledger = read(out/'report/decision_ledger.json')
    assert next(i for i in ledger if i['choice'] == 'selection.n_components')['authority'].startswith('application default')
    assert (out/result['report']).exists()
    again = run_pipeline(path, out, resume=True, planner=planner)
    assert again['status'] == 'pipeline_complete' and planner.calls == 3
    # A modified completed artifact must not be silently reused.
    (out/'evaluation/metrics.csv').write_text('tampered', encoding='utf-8')
    with pytest.raises(InputError, match='Checkpoint artifacts'):
        run_pipeline(path, out, resume=True, planner=planner)


def test_clarification_stops_downstream(tmp_path):
    path = data(tmp_path)
    planner = Planner(clarify=True)
    result = run_pipeline(path, tmp_path/'agent', overrides={'loader': {'orientation': 'rows'}}, planner=planner)
    assert result['status'] == 'needs_clarification'
    assert result['detail']['questions'] == ['Are these counts?']
    assert planner.calls == 1 and 'execution' not in result['stages']
    with pytest.raises(InputError, match='Changed scientific context'):
        run_pipeline(path, tmp_path/'agent', context='New answer', resume=True, planner=planner)


def test_budget_stops_before_next_call(tmp_path):
    planner = Planner()
    result = run_pipeline(data(tmp_path), tmp_path/'agent', overrides={
        'loader': {'orientation': 'rows'}, 'max_model_calls': 1}, planner=planner)
    assert result['status'] == 'pipeline_failed' and planner.calls == 1
    assert result['current_stage'] == 'selection'
    assert 'execution' not in result['stages']


def test_automatic_and_evidence_only(tmp_path):
    planner = Planner()
    result = run_pipeline(data(tmp_path), tmp_path/'agent', overrides={
        'loader': {'orientation': 'rows'}, 'dimension_mode': 'auto',
        'report': {'mode': 'evidence_only'}}, planner=planner)
    assert result['status'] == 'pipeline_complete' and planner.calls == 2
    assert read(tmp_path/'agent/execution/execution.json')['dimension_mode'] == 'auto'
    assert read(tmp_path/'agent/report/report_generation.json')['status'] == 'evidence_report_complete'


def test_config_rejects_unknowns_and_changed_inputs(tmp_path):
    for settings in ([], {'dimensions': True}, {'report': {'mode': 'other'}}, {'typo': 2}):
        with pytest.raises((InputError, TypeError)):
            resolve_config(settings)
    path = data(tmp_path)
    run_pipeline(path, tmp_path/'agent', overrides={'loader': {'orientation': 'rows'}}, planner=Planner(clarify=True))
    path.write_text('changed', encoding='utf-8')
    with pytest.raises(InputError, match='Input changed'):
        run_pipeline(path, tmp_path/'agent', resume=True)


def test_late_failure_resume_reuses_numerical_stages(tmp_path):
    class Unavailable:
        def propose(self, prompt, directory):
            raise PlannerError('Simulated temporary report backend failure')

    path, out, planner = data(tmp_path), tmp_path/'agent', Planner()
    result = run_pipeline(path, out, overrides={'loader': {'orientation': 'rows'}}, planner=planner, reporter=Unavailable())
    assert result['status'] == 'pipeline_failed' and result['current_stage'] == 'report'
    assert planner.calls == 2
    old_hashes = result['stages']['execution']['files']
    result = run_pipeline(path, out, resume=True, planner=planner)
    assert result['status'] == 'pipeline_complete' and planner.calls == 3
    assert result['stages']['execution']['files'] == old_hashes
    assert result['stages']['report']['output'] == 'report_attempt_2'
    assert (out/'report/report_generation.json').exists()


def test_no_eligible_method_does_not_request_selection(tmp_path):
    planner = Planner()
    result = run_pipeline(data(tmp_path), tmp_path/'agent', overrides={
        'loader': {'orientation': 'rows'}, 'resources': {'max_working_bytes': 1}}, planner=planner)
    assert result['status'] == 'pipeline_failed' and planner.calls == 1
    assert result['detail']['status'] == 'no_eligible_method'
