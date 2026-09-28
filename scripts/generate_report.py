"""Generate an auditable report using one Codex call, or replay saved narrative offline."""
import argparse
import json
from dimred_agent.reporting import generate_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('preprocessing_run', 'selection_run', 'execution_run', 'evaluation_run'):
        parser.add_argument(name)
    parser.add_argument('--out', required=True)
    parser.add_argument('--name', default='generated_report')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--replay', help='Saved narrative_response.json; no AI calls, exact evidence must match.')
    group.add_argument('--evidence-only', action='store_true', help='Render records without AI synthesis; clearly labeled.')
    args = parser.parse_args()
    result = generate_report(**vars(args))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
