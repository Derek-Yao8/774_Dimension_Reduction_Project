"""Regenerate a readable multi-method report from verified completed stages."""
import argparse
import json
from pathlib import Path

from dimred_agent.codex_planner import CodexPlanner
from dimred_agent.data import InputError
from dimred_agent.execution import read, write
from dimred_agent.multi_method import set_report
from dimred_agent.pipeline import files_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pipeline_run')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    source, target = Path(args.pipeline_run).resolve(), Path(args.out).resolve()
    state = read(source/'pipeline.json')
    if state['status'] not in ('pipeline_complete', 'pipeline_partial'):
        raise InputError('A finished source pipeline is required.')
    config = state['configuration']['settings']
    if config.get('method_policy') != 'all_suitable':
        raise InputError('An all-suitable source pipeline is required.')
    if target.exists() or source == target or source in target.parents:
        raise InputError('Use a new output directory outside the saved pipeline.')
    for stage in state['stages'].values():
        if stage.get('status') != 'complete' or files_snapshot(source/stage['output']) != stage['files']:
            raise InputError('Source checkpoint verification failed: '+stage['output'])
    result = set_report(source/state['stages']['preprocessing']['output'],
                        source/state['stages']['selection']['output'],
                        state['method_results'], target, config, state,
                        CodexPlanner(timeout=config['report']['timeout']))
    write(target/'revision_provenance.json', {
        'source_pipeline': str(source), 'source_report': str(source/state['report']),
        'source_checkpoints_verified': True,
        'scope': 'Report-only revision; numerical results and original pipeline are unchanged.',
        'model_calls_attempted': result['model_calls_attempted'],
        'budget_scope': 'One separate report request; does not mutate the source pipeline request ledger.'})
    print(json.dumps(result))


if __name__ == '__main__':
    main()
