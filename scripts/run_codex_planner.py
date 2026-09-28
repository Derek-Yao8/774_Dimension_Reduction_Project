"""Profile -> Codex plan -> validation -> local preprocessing."""
import argparse
import json
from dimred_agent import load_dataset
from dimred_agent.codex_planner import run_planner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset")
    parser.add_argument("--out", required=True)
    parser.add_argument("--context", default="")
    parser.add_argument("--split", choices=["train", "val", "test"])
    parser.add_argument("--orientation", choices=["rows", "columns"])
    parser.add_argument("--label-column")
    parser.add_argument("--id-column")
    args = parser.parse_args()
    data = load_dataset(args.dataset, split=args.split, orientation=args.orientation,
                        label_column=args.label_column, id_column=args.id_column)
    outcome = run_planner(data, args.out, context=args.context)
    print(json.dumps(outcome, indent=2))
    return 0 if outcome["status"] == "preprocessing_complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
