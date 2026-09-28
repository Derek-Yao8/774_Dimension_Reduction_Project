"""Run a dataset through inspection, planning, reduction, evaluation and reporting."""
import argparse
import json
from pathlib import Path
from dimred_agent.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset')
    parser.add_argument('--out', required=True)
    parser.add_argument('--context', default=None, help='Scientific context and initial analysis instructions.')
    parser.add_argument('--config', type=Path, help='JSON setting overrides; omitted values use documented defaults.')
    parser.add_argument('--resume', action='store_true', help='Reuse verified completed stages with unchanged inputs/settings.')
    parser.add_argument('--split', choices=['train', 'val', 'test'])
    parser.add_argument('--orientation', choices=['rows', 'columns'])
    parser.add_argument('--label-column')
    parser.add_argument('--id-column')
    parser.add_argument('--dimensions', type=int)
    parser.add_argument('--method-policy', choices=['single', 'all_suitable'])
    parser.add_argument('--dimension-mode', choices=['fixed', 'auto'])
    parser.add_argument('--report-name')
    args = parser.parse_args()
    try:
        settings = json.loads(args.config.read_text(encoding='utf-8')) if args.config else {}
        if not isinstance(settings, dict):
            raise ValueError('Configuration must be a JSON object.')
        for key in ('split', 'orientation', 'label_column', 'id_column'):
            if getattr(args, key) is not None:
                settings.setdefault('loader', {})[key] = getattr(args, key)
        for key in ('dimensions', 'dimension_mode', 'method_policy'):
            if getattr(args, key) is not None:
                settings[key] = getattr(args, key)
        if args.report_name:
            settings.setdefault('report', {})['name'] = args.report_name
        result = run_pipeline(args.dataset, args.out, context=args.context, overrides=settings or None, resume=args.resume)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'input_error', 'error': str(exc)}))
        return 2
    print(json.dumps({'status': result['status'], 'stage': result.get('current_stage'),
                      'model_request_attempts': len(result['model_requests']), 'report': result.get('report'),
                      'detail': result.get('detail')}))
    return 0 if result['status'] == 'pipeline_complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
