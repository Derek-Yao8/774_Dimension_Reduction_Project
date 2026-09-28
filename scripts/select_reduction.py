"""Choose one reduction plan from a completed preprocessing run; no embedding yet."""
import argparse
import json
from pathlib import Path
from dimred_agent.data import InputError
from dimred_agent.reduction_planner import ResourceLimits, run_reduction_planner
from dimred_agent.diagnostics import DiagnosticConfig, diagnostics_from_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preprocessing_run", type=Path)
    parser.add_argument("--out", required=True)
    parser.add_argument("--context", default="")
    parser.add_argument("--dimensions", type=int, default=2)
    parser.add_argument("--max-working-bytes", type=int, default=1_000_000_000,
                        help="Local working-array screening budget, not a hard RAM cap.")
    parser.add_argument("--max-manifold-observations", type=int, default=5000)
    parser.add_argument("--max-planning-attempts", type=int, choices=[1, 2], default=1,
                        help="Codex proposal limit; 2 permits one validation correction.")
    parser.add_argument("--preview", action="store_true", help="Save feasibility evidence without calling Codex.")
    parser.add_argument("--no-diagnostics", action="store_true", help="Explicitly skip geometry measurements.")
    parser.add_argument("--diagnostic-max-samples", type=int, default=512)
    parser.add_argument("--diagnostic-max-working-bytes", type=int, default=128_000_000)
    parser.add_argument("--diagnostic-seed", type=int, default=0)
    parser.add_argument("--diagnostic-neighbors", type=int, nargs="+", default=[5, 15, 30])
    args = parser.parse_args()
    try:
        if Path(args.out).exists():
            raise InputError("Choose a new output directory.")
        limits = ResourceLimits(args.max_working_bytes, args.max_manifold_observations)
        config = DiagnosticConfig(args.diagnostic_max_samples, args.diagnostic_max_working_bytes,
                                  args.diagnostic_seed, tuple(args.diagnostic_neighbors))
        run = json.loads((args.preprocessing_run / "run.json").read_text(encoding="utf-8"))
        if run.get("status") != "preprocessing_complete":
            raise InputError("A successfully completed preprocessing run is required.")
        profile = json.loads((args.preprocessing_run / "preprocessed/profile.json").read_text(encoding="utf-8"))
        if run["output_shape"] != [profile["n_observations"], profile["n_features"]] or run["plan"] != profile["provenance"].get("preprocessing_plan"):
            raise InputError("Preprocessing record and profile disagree.")
        diagnostics = (None if args.no_diagnostics else diagnostics_from_run(args.preprocessing_run, profile, config))
        outcome = run_reduction_planner(profile, args.out, context=args.context, dimensions=args.dimensions,
                                        limits=limits, diagnostics=diagnostics,
                                        max_attempts=args.max_planning_attempts, preview=args.preview)
    except (InputError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "input_error", "error": str(exc)}))
        return 2
    print(json.dumps(outcome, indent=2))
    return 0 if outcome["status"] in ("selection_complete", "preview_only") else 2


if __name__ == "__main__":
    raise SystemExit(main())
