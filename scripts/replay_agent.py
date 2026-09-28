"""Recompute a completed workflow using saved plans with zero model calls."""
import argparse
import json
from dimred_agent.replay import replay_pipeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_run')
    parser.add_argument('--out', required=True)
    parser.add_argument('--dataset', help='Optional relocated dataset with the same content fingerprint.')
    parser.add_argument('--rtol', type=float, default=1e-5)
    parser.add_argument('--atol', type=float, default=1e-8)
    args = parser.parse_args()
    try:
        result = replay_pipeline(args.source_run, args.out, dataset=args.dataset, rtol=args.rtol, atol=args.atol)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'input_error', 'error': str(exc)}))
        return 2
    print(json.dumps(result))
    return (0 if result.get('comparison_matches') else 3) if result['status'] == 'replay_complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
