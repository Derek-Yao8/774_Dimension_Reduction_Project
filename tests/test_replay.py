import shutil
import numpy as np
import pytest
from dimred_agent.codex_planner import CodexPlanner
from dimred_agent.data import InputError
from dimred_agent.execution import read
from test_pipeline import run_pipeline
from dimred_agent.replay import replay_pipeline, embedding_comparison
from test_pipeline import data, Planner
from test_reduction_planner import ready


def forbidden(*args, **kwargs):
    raise AssertionError('Replay must never construct a live planner or make a model call.')


@pytest.mark.parametrize('auto', [False, True])
def test_raw_replay_no_model_and_changed_report_evidence(tmp_path, monkeypatch, auto):
    raw = data(tmp_path)
    source = tmp_path/'source'
    result = run_pipeline(raw, source, overrides={
        'loader': {'orientation': 'rows'}, 'dimension_mode': 'auto' if auto else 'fixed',
        'dimension_search': {'variance_target': .1}}, planner=Planner())
    assert result['status'] == 'pipeline_complete'
    # Relocation is allowed when raw content is identical.
    moved = tmp_path/'relocated.csv'
    shutil.copyfile(raw, moved)
    monkeypatch.setattr(CodexPlanner, '__init__', forbidden)
    monkeypatch.setattr(CodexPlanner, 'propose', forbidden)
    replayed = replay_pipeline(source, tmp_path/'replayed', dataset=moved)
    assert replayed['status'] == 'replay_complete', replayed
    assert replayed['model_calls_attempted'] == 0 and replayed['comparison_matches']
    assert read(tmp_path/'replayed/comparison.json')['effective_parameters_match']
    assert replayed['narrative_reused'] is False
    assert (tmp_path/'replayed/historical_narrative_response.json').exists()
    assert read(tmp_path/'replayed/report/report_generation.json')['mode'] == 'evidence_only'
    assert read(tmp_path/'replayed/preprocessing/run.json')['backend'] == 'saved_plan_replay'
    if auto:
        source_run = read(source/'execution/execution.json')
        new_run = read(tmp_path/'replayed/execution/execution.json')
        assert source_run['output_shape'] == new_run['output_shape']
        assert new_run['attempts'][0]['effective_parameters']['n_components'] == source_run['attempts'][0]['effective_parameters']['n_components']


def test_source_or_raw_tampering_rejected(tmp_path):
    raw = data(tmp_path)
    source = tmp_path/'source'
    run_pipeline(raw, source, overrides={'loader': {'orientation': 'rows'}, 'report': {'mode': 'evidence_only'}}, planner=Planner())
    raw.write_text('changed', encoding='utf-8')
    with pytest.raises(InputError, match='Raw dataset fingerprint'):
        replay_pipeline(source, tmp_path/'bad')
    (source/'selection/selection.json').write_text('{}', encoding='utf-8')
    with pytest.raises(InputError, match='checkpoint files changed'):
        replay_pipeline(source, tmp_path/'bad2')


def test_rotation_reflection_and_real_distortion():
    x = np.random.default_rng(3).normal(size=(50, 3))
    q, _ = np.linalg.qr(np.random.default_rng(4).normal(size=(3, 3)))
    result = embedding_comparison(x@q+10, x, 1e-5, 1e-8)
    assert result['geometry_matches'] and not result['coordinates']['matches']
    assert not embedding_comparison(x*2, x, 1e-5, 1e-8)['geometry_matches']


def test_failed_replay_never_falls_back(tmp_path, monkeypatch):
    raw, source = data(tmp_path), tmp_path/'source'
    run_pipeline(raw, source, overrides={'loader': {'orientation': 'rows'}, 'report': {'mode': 'evidence_only'}}, planner=Planner())
    monkeypatch.setattr(CodexPlanner, '__init__', forbidden)
    monkeypatch.setattr('dimred_agent.replay.run_worker', lambda *args, **kwargs: {
        'status': 'failed', 'error_type': 'TestFailure', 'error': 'Intentional failure'})
    result = replay_pipeline(source, tmp_path/'replayed')
    assert result['status'] == 'replay_failed' and result['model_calls_attempted'] == 0
    execution = read(tmp_path/'replayed/execution/execution.json')
    assert not execution['fallback_occurred'] and execution['fallback_planner_calls'] == 0


def test_replays_successful_fallback_and_discloses_original(tmp_path, monkeypatch):
    from dimred_agent.execution import execute, run_worker
    class FallbackPlanner(Planner):
        def propose(self, prompt, directory):
            if directory.name == 'fallback_planning':
                self.calls += 1
                return ready(read(directory.parent.parent/'selection/selection_evidence.json'), 'pca')
            if directory.parent.name == 'selection':
                self.calls += 1
                return ready(read(directory.parent/'selection_evidence.json'), 'mds')
            return super().propose(prompt, directory)

    def worker(matrix, plan, directory, timeout, threads):
        if plan['method'] == 'mds':
            return {'status': 'failed', 'error_type': 'TestFailure', 'error': 'Injected MDS failure'}
        return run_worker(matrix, plan, directory, timeout, threads)

    monkeypatch.setattr('dimred_agent.pipeline.execute', lambda *args, **kwargs: execute(*args, **kwargs, worker=worker))
    source = tmp_path/'source'
    run = run_pipeline(data(tmp_path), source, overrides={'loader': {'orientation': 'rows'},
                       'report': {'mode': 'evidence_only'}}, planner=FallbackPlanner())
    assert run['status'] == 'pipeline_complete'
    assert read(source/'execution/execution.json')['fallback_occurred']
    monkeypatch.setattr(CodexPlanner, '__init__', forbidden)
    result = replay_pipeline(source, tmp_path/'replayed')
    assert result['status'] == 'replay_complete' and result['comparison_matches']
    history = read(tmp_path/'replayed/preprocessing/replay_provenance.json')
    assert history['source_fallback_occurred'] and history['replayed_plan']['method'] == 'pca'
    assert not read(tmp_path/'replayed/execution/execution.json')['fallback_occurred']
