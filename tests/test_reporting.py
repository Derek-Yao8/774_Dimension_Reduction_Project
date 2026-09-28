import json
import pytest
from dimred_agent.data import InputError
from dimred_agent.execution import execute, read, write
from dimred_agent.evaluation import evaluate
from dimred_agent.reporting import generate_report, HEADINGS, validate_narrative
from test_execution import inputs


class Reporter:
    def __init__(self):
        self.calls = 0

    def propose(self, prompt, directory):
        self.calls += 1
        fingerprint = prompt.split('Fingerprint: ')[1].split('\n')[0]
        return {'status': 'ready', 'explanation': 'Test synthesis', 'questions': [],
                'plan_json': json.dumps({'evidence_digest': fingerprint, 'sections': [
                    {'heading': heading, 'claims': [{'text': 'The recorded method is PCA.', 'evidence_refs': ['selection.plan']}]}
                    for heading in HEADINGS]})}


def setup(tmp_path):
    pre, sel, profile = inputs(tmp_path)
    write(pre/'input_profile.json', profile)
    write(pre/'preprocessed/preprocessing.json', {'plan': {'reason': 'fixture'}})
    selected = read(sel/'selection.json')
    selected['feasibility_checks'] = {'pca': {'eligible': True, 'reasons': []}}
    write(sel/'selection.json', selected)
    write(sel/'selection_evidence.json', {'fixture': True})
    run, assessed = tmp_path/'execution', tmp_path/'evaluation'
    execute(pre, sel, run, allow_fallback=False)
    evaluate(pre, run, assessed)
    return pre, sel, run, assessed


def test_report_replay_and_exact_sources(tmp_path):
    paths = setup(tmp_path)
    reporter = Reporter()
    out = tmp_path/'report'
    result = generate_report(*paths, out, planner=reporter, name='generated_report_1')
    assert result['status'] == 'report_complete' and reporter.calls == 1
    text = (out/'generated_report_1.md').read_text(encoding='utf-8')
    assert 'Verbatim decision-time records' in text
    assert 'Caller-vs-default provenance' in text
    assert (out/'evidence/selection.json').read_bytes() == (paths[1]/'selection.json').read_bytes()
    replay = generate_report(*paths, tmp_path/'replayed', replay=out/'narrative_response.json', planner=reporter)
    assert replay['model_calls_attempted'] == 0 and reporter.calls == 1
    # Any record change invalidates narrative replay, even when not shown to model.
    original = read(paths[0]/'input_profile.json')
    original['report_test_note'] = 'changed'
    write(paths[0]/'input_profile.json', original)
    with pytest.raises(InputError, match='fingerprint'):
        generate_report(*paths, tmp_path/'stale', replay=out/'narrative_response.json')
    assert read(tmp_path/'stale/report_generation.json')['status'] == 'report_failed'


def test_evidence_only_and_chain_mismatch(tmp_path):
    paths = setup(tmp_path)
    reporter = Reporter()
    result = generate_report(*paths, tmp_path/'offline', evidence_only=True, planner=reporter)
    assert result['status'] == 'evidence_report_complete' and reporter.calls == 0
    assessed = read(paths[3]/'evaluation.json')
    assessed['execution_sha256'] = 'wrong'
    write(paths[3]/'evaluation.json', assessed)
    with pytest.raises(InputError, match='does not match'):
        generate_report(*paths, tmp_path/'wrong', planner=reporter)
    assert reporter.calls == 0


def test_unknown_refs_and_incomplete_narrative():
    response = Reporter().propose('Fingerprint: abc\n', None)
    with pytest.raises(InputError, match='unknown evidence'):
        validate_narrative(response, {}, 'abc')
    narrative = json.loads(response['plan_json'])
    narrative['sections'].pop()
    response['plan_json'] = json.dumps(narrative)
    with pytest.raises(InputError, match='required narrative sections'):
        validate_narrative(response, {'selection.plan': {}}, 'abc')
