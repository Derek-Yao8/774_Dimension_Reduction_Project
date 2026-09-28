"""Execute an explicit preprocessing plan; no AI selection yet."""
import argparse
import json
from pathlib import Path

from dimred_agent import load_dataset, profile_dataset
from dimred_agent.preprocessing import PreprocessingPlan, preprocess
from dimred_agent.profile import render_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--split", choices=["train", "val", "test"])
    parser.add_argument("--orientation", choices=["rows", "columns"])
    parser.add_argument("--label-column")
    parser.add_argument("--id-column")
    args = parser.parse_args()
    plan = PreprocessingPlan.from_dict(json.loads(args.plan.read_text(encoding="utf-8")))
    dataset = load_dataset(args.dataset, split=args.split, orientation=args.orientation,
                           label_column=args.label_column, id_column=args.id_column)
    result = preprocess(dataset, plan)
    result.save(args.out)
    profile = profile_dataset(result.dataset)
    (args.out / "profile.json").write_text(json.dumps(profile, indent=2, allow_nan=False), encoding="utf-8")
    (args.out / "profile.md").write_text(render_summary(profile), encoding="utf-8")
    print(f"Preprocessed {dataset.X.shape} -> {result.dataset.X.shape}; saved to {args.out.resolve()}")


if __name__ == "__main__":
    main()
