"""Execute a saved selection; live fallback is allowed only after failure."""
import argparse
import json
from pathlib import Path
from dimred_agent.execution import execute
from dimred_agent.dimension_selection import DimensionConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('preprocessing_run')
    parser.add_argument('selection_run')
    parser.add_argument('--out', required=True)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--offline', action='store_true', help='Disable new AI fallback; stop on failure.')
    parser.add_argument('--dimension-mode', choices=['auto', 'fixed'], default='fixed',
                        help='Default: fixed, preserving the saved dimension (normally 2). Auto selects dimensions locally.')
    parser.add_argument('--dimension-config', type=Path, help='JSON overrides for automatic dimension-search settings.')
    args = parser.parse_args()
    try:
        settings = json.loads(args.dimension_config.read_text(encoding='utf-8')) if args.dimension_config else {}
        if not isinstance(settings, dict):
            raise ValueError('Dimension configuration must be a JSON object.')
        if args.dimension_mode == 'fixed' and args.dimension_config:
            raise ValueError('Dimension configuration is only used in auto mode.')
        if 'candidates' in settings:
            settings['candidates'] = tuple(settings['candidates'])
        config = DimensionConfig(**settings) if args.dimension_mode == 'auto' else None
        result = execute(args.preprocessing_run, args.selection_run, args.out, timeout=args.timeout,
                         threads=args.threads, allow_fallback=not args.offline, dimension_config=config)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'input_or_io_error', 'error': str(exc)}))
        return 2
    print(json.dumps({'status': result['status'], 'final_method': result['final_method'],
                      'fallback_occurred': result['fallback_occurred']}))
    return 0 if result['status'] == 'execution_complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
