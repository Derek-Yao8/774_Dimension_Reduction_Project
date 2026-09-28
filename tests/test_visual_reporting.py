import json
from pathlib import Path
import subprocess

from PIL import Image
import pytest

from dimred_agent.codex_planner import CodexPlanner, PlannerError
from dimred_agent.data import InputError
from dimred_agent.execution import write, read, sha256
from dimred_agent.pipeline import _BudgetedPlanner
from dimred_agent.reporting import HEADINGS
from dimred_agent.visual_reporting import prepare_visual_inputs, validate_visual_narrative, render_visuals


def fixture(tmp_path):
    evaluation, execution, report = [tmp_path/p for p in ('eval','exec','report')]
    for p in (evaluation,execution,report): p.mkdir()
    Image.new('RGB',(30,20),'white').save(evaluation/'embedding.png')
    write(execution/'execution.json',dict(embedding_sha256='coordinates',final_method='pca'))
    write(evaluation/'evaluation.json',dict(embedding_sha256='coordinates',
        execution_sha256=sha256(execution/'execution.json'),plot={'n_plotted':20,'sample_positions':[0,1]}))
    evidence={'pca.embedding':{'sample_size':10}}
    entries,paths=prepare_visual_inputs({'pca':{'execution':str(execution),'evaluation':str(evaluation)}},report,evidence)
    return evidence, entries, paths, report


def response(entries):
    return dict(status='ready',questions=[],explanation='Fixture',plan_json=json.dumps({
        'evidence_digest':'fingerprint',
        'sections':[dict(heading=h,claims=[dict(text='Recorded data.',evidence_refs=['pca.embedding'])]) for h in HEADINGS],
        'visual_interpretations':[dict(image_id=e['image_id'],status='inspected', observations=['A synthetic blank canvas.'],
            relation_to_metrics='Blank fixture does not validate scores.',limitations=['Synthetic image only.'],
            evidence_refs=[e['image_id'],e['metrics_ref']]) for e in entries]}))


def test_visual_image_identity_and_readable_render(tmp_path):
    evidence, entries, paths, report=fixture(tmp_path)
    assert entries[0]['sha256']==sha256(paths[0])
    assert entries[0]['pixel_size']==[30,20]
    assert 'sample_positions' not in entries[0]['plot']
    narrative=validate_visual_narrative(response(entries),evidence,'fingerprint',entries)
    text='\n'.join(render_visuals(narrative,entries))
    assert '(visual_inputs/pca.png)' in text
    for field in ('observations', 'limitations'):
        assert all(paragraph in text for paragraph in narrative['visual_interpretations'][0][field])
    assert narrative['visual_interpretations'][0]['relation_to_metrics'] in text


@pytest.mark.parametrize('fault',['missing','duplicate','unknown','wrong_metric','unreadable_with_claims','no_limit','no_observation'])
def test_incomplete_or_misattributed_visual_claims_rejected(tmp_path,fault):
    evidence,entries,_,_=fixture(tmp_path)
    r=response(entries);payload=json.loads(r['plan_json']);items=payload['visual_interpretations']
    if fault=='missing':items.clear()
    elif fault=='duplicate':items.append(items[0])
    elif fault=='unknown':items[0]['image_id']='umap.visual'
    elif fault=='wrong_metric':items[0]['evidence_refs']=['pca.visual']
    elif fault=='unreadable_with_claims':items[0]['status']='unreadable'
    elif fault=='no_limit':items[0]['limitations']=[]
    else:items[0]['observations']=[]
    r['plan_json']=json.dumps(payload)
    with pytest.raises(InputError):validate_visual_narrative(r,evidence,'fingerprint',entries)


def test_unreadable_is_explicit_not_fabricated(tmp_path):
    evidence,entries,_,_=fixture(tmp_path)
    r=response(entries);payload=json.loads(r['plan_json'])
    payload['visual_interpretations'][0].update(status='unreadable',observations=[],limitations=['Unable to resolve plotted marks.'])
    r['plan_json']=json.dumps(payload)
    result=validate_visual_narrative(r,evidence,'fingerprint',entries)
    assert 'unreadable' in '\n'.join(render_visuals(result,entries))


def test_corrupt_or_mismatched_plot_input_stops(tmp_path):
    _,_,_,report=fixture(tmp_path)
    evaluation=tmp_path/'eval'; execution=tmp_path/'exec'
    write(evaluation/'evaluation.json',dict(embedding_sha256='wrong',execution_sha256=sha256(execution/'execution.json'),plot={}))
    with pytest.raises(InputError,match='linkage'):
        prepare_visual_inputs({'pca':{'execution':str(execution),'evaluation':str(evaluation)}},report,{})


def test_cli_passes_ordered_images_and_records_hashes(tmp_path,monkeypatch):
    image=tmp_path/'plot with spaces.png';Image.new('RGB',(2,2)).save(image)
    monkeypatch.setattr(CodexPlanner,'check_auth',lambda self:None)
    captured=[]
    def fake(command,**kwargs):
        captured.append(command)
        output=Path(command[command.index('--output-last-message')+1]);write(output,{'test':'response'})
        return subprocess.CompletedProcess(command,0,'','')
    monkeypatch.setattr(subprocess,'run',fake)
    result=CodexPlanner(executable='codex').propose('Inspect this plot.',tmp_path/'call',images=[image])
    assert result=={'test':'response'}
    assert '--image='+str(image.resolve()) in captured[0]
    assert captured[0][-2:]==['--','-']
    assert read(tmp_path/'call/image_attachments.json')[0]['sha256']==sha256(image)
    with pytest.raises(PlannerError,match='missing'):
        CodexPlanner(executable='codex').propose('x',tmp_path/'missing_call',images=[tmp_path/'absent.png'])
    assert len(captured)==1


def test_budget_forwards_images_without_extra_requests(tmp_path):
    calls=[]
    class Delegate:
        def propose(self,prompt,directory,*,images=()):calls.append(images);return {'done':True}
    state={'model_requests':[],'configuration':{'settings':{'max_model_calls':1}}}
    adapter=_BudgetedPlanner(state,lambda:None,'report',180,Delegate())
    image=tmp_path/'example.png'
    adapter.propose('p',tmp_path,images=[image])
    assert calls==[[image]] and len(state['model_requests'])==1
    with pytest.raises(PlannerError,match='budget'):adapter.propose('p',tmp_path,images=[image])
    assert len(calls)==1
