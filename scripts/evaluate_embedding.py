"""Evaluate and plot a saved embedding without model calls or refitting."""
import argparse
import json
from dimred_agent.evaluation import EvaluationConfig, evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('preprocessing_run')
    parser.add_argument('execution_run')
    parser.add_argument('--out', required=True)
    parser.add_argument('--color-column')
    for name, field in EvaluationConfig.__dataclass_fields__.items():
        parser.add_argument('--'+name.replace('_', '-'), type=int, default=field.default)
    args = parser.parse_args()
    config = EvaluationConfig(**{key: getattr(args, key) for key in EvaluationConfig.__dataclass_fields__})
    result = evaluate(args.preprocessing_run, args.execution_run, args.out, config=config, color_column=args.color_column)
    print(json.dumps({'status': result['status'], 'metrics': result['embedding']['metrics']}))


if __name__ == '__main__':
    main()
