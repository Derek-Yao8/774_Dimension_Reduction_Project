"""One entry point for inspection through reporting, with verified checkpoints."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
import time
from pathlib import Path

from .data import InputError, load_dataset
from .profile import profile_dataset, render_summary
from .codex_planner import CodexPlanner, PlannerError, run_planner
from .diagnostics import DiagnosticConfig, diagnostics_from_run
from .reduction_planner import ResourceLimits, run_reduction_planner
from .dimension_selection import DimensionConfig
from .execution import execute, read, write, sha256
from .evaluation import EvaluationConfig, evaluate
from .reporting import generate_report


def replace_checkpoint(temporary, target):
    """Keep atomic replacement while allowing short-lived Windows file locks."""
    for attempt in range(6):
        try:
            temporary.replace(target)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(.05 * 2**attempt)


def defaults():
    return json.loads(json.dumps({
        'loader': {'split': None, 'orientation': None, 'label_column': None, 'id_column': None},
        'method_policy': 'all_suitable',
        'dimensions': 2, 'dimension_mode': 'fixed', 'dimension_search': asdict(DimensionConfig()),
        'preprocessing_attempts': 2, 'selection_attempts': 1,
        'max_model_calls': 5, 'planner_timeout': 180,
        'resources': asdict(ResourceLimits()), 'diagnostics': asdict(DiagnosticConfig()),
        'execution': {'timeout': 600, 'threads': 2, 'allow_fallback': True},
        'evaluation': asdict(EvaluationConfig()),
        'report': {'name': 'generated_report', 'mode': 'codex', 'timeout': 180, 'color_column': None},
    }))


def resolve_config(overrides=None):
    """Retain explicit overrides even when their value equals the default."""
    origins = {}

    def merge(base, supplied, prefix=''):
        if not isinstance(supplied, dict) or set(supplied) - set(base):
            raise InputError('Unknown settings or non-object configuration at '+(prefix or 'root'))
        result = {}
        for key, value in base.items():
            path = prefix+key
            if isinstance(value, dict):
                result[key] = merge(value, supplied.get(key, {}), path+'.')
            else:
                result[key] = supplied.get(key, value)
                origins[path] = {'value': result[key], 'origin': 'caller configuration' if key in supplied else 'application default'}
        return result

    config = merge(defaults(), {} if overrides is None else overrides)
    if config['method_policy'] not in ('single', 'all_suitable'):
        raise InputError('method_policy must be single or all_suitable.')
    for key in ('dimensions', 'max_model_calls', 'planner_timeout', 'preprocessing_attempts', 'selection_attempts'):
        if type(config[key]) is not int or config[key] < 1:
            raise InputError(key+' must be a positive integer.')
    if config['preprocessing_attempts'] > 2 or config['selection_attempts'] > 2:
        raise InputError('Planning attempts must be 1 or 2.')
    if config['dimension_mode'] not in ('fixed', 'auto'):
        raise InputError('dimension_mode must be fixed or auto.')
    for key in ('timeout', 'threads'):
        if type(config['execution'][key]) is not int or config['execution'][key] < 1:
            raise InputError('Execution '+key+' must be a positive integer.')
    if type(config['execution']['allow_fallback']) is not bool:
        raise InputError('allow_fallback must be boolean.')
    if config['report']['mode'] not in ('codex', 'evidence_only'):
        raise InputError('Report mode must be codex or evidence_only.')
    if type(config['report']['timeout']) is not int or config['report']['timeout'] < 1:
        raise InputError('Report timeout must be positive.')
    name = config['report']['name']
    if not isinstance(name, str) or not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
        raise InputError('Invalid report name.')
    for key, value in config['loader'].items():
        if value is not None and not isinstance(value, str):
            raise InputError('Loader '+key+' must be a string or null.')
    if config['loader']['split'] not in (None, 'train', 'val', 'test') or config['loader']['orientation'] not in (None, 'rows', 'columns'):
        raise InputError('Invalid split or orientation.')
    if config['report']['color_column'] is not None and not isinstance(config['report']['color_column'], str):
        raise InputError('color_column must be a string or null.')
    ResourceLimits(**config['resources'])
    DiagnosticConfig(**{**config['diagnostics'], 'neighbors': tuple(config['diagnostics']['neighbors'])})
    DimensionConfig(**{**config['dimension_search'], 'candidates': tuple(config['dimension_search']['candidates'])})
    EvaluationConfig(**config['evaluation'])
    return config, origins


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def files_snapshot(path):
    return {p.relative_to(path).as_posix(): sha256(p) for p in sorted(path.rglob('*')) if p.is_file()}


def input_snapshot(path):
    if path.is_file():
        return {'kind': 'file', 'sha256': sha256(path)}
    if path.is_dir():
        return {'kind': 'directory', 'files': files_snapshot(path)}
    raise InputError('Dataset path does not exist.')


class _Stop(Exception):
    pass


class _BudgetedPlanner:
    def __init__(self, state, persist, stage, timeout, delegate=None):
        self.state, self.persist, self.stage = state, persist, stage
        self.timeout, self.delegate = timeout, delegate
        self.backend = getattr(delegate, 'backend', 'injected_planner') if delegate is not None else 'codex_cli_chatgpt'

    def propose(self, prompt, directory, *, images=()):
        if len(self.state['model_requests']) >= self.state['configuration']['settings']['max_model_calls']:
            raise PlannerError('Pipeline model-request budget exhausted; no further request was made.')
        entry = {'stage': self.stage, 'backend': self.backend, 'started_at': timestamp(), 'status': 'attempted'}
        self.state['model_requests'].append(entry)
        self.persist()
        try:
            if self.delegate is None:
                self.delegate = CodexPlanner(timeout=self.timeout)
            response = self.delegate.propose(prompt, directory, images=images) if images else self.delegate.propose(prompt, directory)
            entry['status'] = 'returned'
            return response
        except Exception as exc:
            entry.update(status='failed', error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            entry['finished_at'] = timestamp()
            self.persist()


def run_pipeline(dataset, out, *, context=None, overrides=None, resume=False, planner=None, reporter=None):
    """Run all stages. Resume reuses verified completed artifacts, not numerical replay."""
    dataset, out = Path(dataset).resolve(), Path(out).resolve()
    if dataset.is_dir() and (dataset == out or dataset in out.parents):
        raise InputError('Output must be outside the input dataset directory.')
    if context is not None and not isinstance(context, str):
        raise InputError('Context must be text.')
    if resume:
        state = read(out/'pipeline.json')
        config, origins = resolve_config({'method_policy': 'single', **state['configuration']['settings']})
        if str(dataset) != state['dataset']:
            raise InputError('Resume requires the original dataset path.')
        if overrides is not None and resolve_config({'method_policy':config['method_policy'], **overrides})[0] != config:
            raise InputError('Resume cannot change settings; start a new run.')
        if context is not None and context != state['configuration']['context']:
            raise InputError('Changed scientific context requires a new run so earlier decisions are reconsidered.')
        if input_snapshot(dataset) != state['input_snapshot']:
            raise InputError('Input changed since the checkpoint; start a new run.')
        for stage in state['stages'].values():
            if stage.get('status') == 'complete':
                if files_snapshot(out/stage['output']) != stage['files']:
                    raise InputError('Checkpoint artifacts changed: '+stage['output'])
        context = state['configuration']['context']
    else:
        config, origins = resolve_config(overrides)
        if out.exists():
            raise InputError('Choose a new pipeline directory or explicitly resume.')
        source = input_snapshot(dataset)
        context = context or ''
        out.mkdir(parents=True)
        state = {'schema_version': '1.0', 'status': 'running', 'dataset': str(dataset),
                 'input_snapshot': source, 'created_at': timestamp(), 'stages': {}, 'model_requests': [],
                 'configuration': {'settings': config, 'origins': origins, 'context': context,
                                   'context_origin': 'caller supplied' if context else 'not supplied',
                                   'scope': 'Configuration provenance; scientific choices remain in stage plans.'}}

    def persist():
        state['updated_at'] = timestamp()
        temporary = out/'pipeline.pending.json'
        write(temporary, state)
        replace_checkpoint(temporary, out/'pipeline.json')

    def stage(name, action, expected):
        previous = state['stages'].get(name, {})
        if previous.get('status') == 'complete':
            print('REUSE: '+name, flush=True)
            return out/previous['output']
        history = previous.get('attempts', [])
        folder = name if not history else f'{name}_attempt_{len(history)+1}'
        target = out/folder
        attempt = {'output': folder, 'started_at': timestamp(), 'status': 'running'}
        history.append(attempt)
        entry = {'status': 'running', 'output': folder, 'attempts': history}
        state['stages'][name] = entry
        state.update(status='running', current_stage=name)
        persist()
        print('START: '+name, flush=True)
        try:
            result = action(target)
            if result.get('status') != expected:
                entry['status'] = attempt['status'] = result.get('status', 'failed')
                state.update(status='needs_clarification' if result.get('status') == 'needs_clarification' else 'pipeline_failed',
                             detail=result)
                raise _Stop()
            entry.update(status='complete', files=files_snapshot(target))
            attempt['status'] = 'complete'
            print('COMPLETE: '+name, flush=True)
        except _Stop:
            raise
        except Exception as exc:
            entry['status'] = attempt['status'] = 'failed'
            state.update(status='pipeline_failed', detail={'error_type': type(exc).__name__, 'error': str(exc)})
            raise _Stop() from exc
        finally:
            attempt['finished_at'] = timestamp()
            persist()
        return target

    context_for_planning = context + '\nApplication output configuration: ' + json.dumps({
        'dimensions': config['dimensions'], 'dimension_mode': config['dimension_mode'],
        'note': 'Auto mode will choose dimensions locally after method selection; fixed mode preserves the requested dimension.'})
    loaded = None

    def inspect(target):
        nonlocal loaded
        loaded = load_dataset(dataset, **config['loader'])
        profile = profile_dataset(loaded)
        target.mkdir()
        write(target/'profile.json', profile)
        (target/'profile.md').write_text(render_summary(profile), encoding='utf-8')
        return {'status': 'inspection_complete'}

    def preprocess_stage(target):
        nonlocal loaded
        if loaded is None:
            loaded = load_dataset(dataset, **config['loader'])
        result = run_planner(loaded, target, context=context_for_planning,
                             max_attempts=config['preprocessing_attempts'],
                             planner=_BudgetedPlanner(state, persist, 'preprocessing', config['planner_timeout'], planner))
        if result['status'] == 'preprocessing_complete':
            write(target/'workflow_config.json', state['configuration'])
        loaded = None
        return result

    try:
        persist()
        stage('inspection', inspect, 'inspection_complete')
        pre = stage('preprocessing', preprocess_stage, 'preprocessing_complete')
        profile = read(pre/'preprocessed/profile.json')

        def diagnose(target):
            result = diagnostics_from_run(pre, profile, DiagnosticConfig(**{
                **config['diagnostics'], 'neighbors': tuple(config['diagnostics']['neighbors'])}))
            target.mkdir()
            write(target/'diagnostics.json', result)
            return {'status': 'diagnostics_saved'}

        diagnostics = stage('diagnostics', diagnose, 'diagnostics_saved')
        if config['method_policy'] == 'all_suitable':
            from .multi_method import run_branches
            run_branches(pre, profile, diagnostics, out, config, state, stage, persist,
                         context_for_planning, planner, reporter)
            return state
        selection = stage('selection', lambda target: run_reduction_planner(
            profile, target, context=context_for_planning, dimensions=config['dimensions'],
            limits=ResourceLimits(**config['resources']), diagnostics=read(diagnostics/'diagnostics.json'),
            max_attempts=config['selection_attempts'],
            planner=_BudgetedPlanner(state, persist, 'selection', config['planner_timeout'], planner)), 'selection_complete')
        dimensions = DimensionConfig(**{**config['dimension_search'], 'candidates': tuple(config['dimension_search']['candidates'])}) if config['dimension_mode'] == 'auto' else None
        execution = stage('execution', lambda target: execute(
            pre, selection, target, **config['execution'], dimension_config=dimensions,
            planner=_BudgetedPlanner(state, persist, 'fallback', config['planner_timeout'], planner)), 'execution_complete')
        evaluation = stage('evaluation', lambda target: evaluate(
            pre, execution, target, config=EvaluationConfig(**config['evaluation']),
            color_column=config['report']['color_column']), 'evaluation_complete')
        evidence_only = config['report']['mode'] == 'evidence_only'
        report = stage('report', lambda target: generate_report(
            pre, selection, execution, evaluation, target, name=config['report']['name'], evidence_only=evidence_only,
            planner=_BudgetedPlanner(state, persist, 'report', config['report']['timeout'], reporter if reporter is not None else planner)),
            'evidence_report_complete' if evidence_only else 'report_complete')
        state.update(status='pipeline_complete', current_stage=None, detail=None,
                     report=(report/(config['report']['name']+'.md')).relative_to(out).as_posix(),
                     report_mode=config['report']['mode'])
        print('PIPELINE COMPLETE: '+str(out/state['report']), flush=True)
    except _Stop:
        print('PIPELINE STOPPED: '+state['status']+' at '+str(state.get('current_stage')), flush=True)
    except KeyboardInterrupt:
        state['status'] = 'interrupted'
        raise
    finally:
        persist()
    return state
