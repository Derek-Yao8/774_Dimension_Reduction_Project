# Usage and configuration

Run commands from the repository root with its Python environment active.
`python scripts/run_agent.py --help` lists command-line options. Initial scientific
context should identify measurement units, orientation, count semantics where
appropriate, and required exclusions or scope constraints.

## Settings

Use `--config /path/settings.json` for JSON overrides. Unknown fields are rejected;
omitted fields use application defaults. For example, save this as `settings.json`:

```json
{
  "dimensions": 2,
  "dimension_mode": "fixed",
  "method_policy": "all_suitable",
  "resources": {"max_working_bytes": 1000000000, "max_manifold_observations": 5000},
  "execution": {"timeout": 600, "threads": 2, "allow_fallback": true},
  "report": {"timeout": 300, "name": "generated_report"}
}
```

CLI overrides include `--split`, `--orientation`, `--label-column`, `--id-column`,
`--dimensions`, `--dimension-mode`, `--method-policy` and `--report-name`.
The example uses a 300-second report timeout; the application default is 180
seconds. The exact default configuration is defined by `defaults()` in
`dimred_agent/pipeline.py`. There are no dataset-specific hardcoded method plans.

For optional local dimension search, use `--dimension-mode auto`. Default
candidates are 2, 3, 5, 10 and 20, subject to method/data bounds, at most five fits
and a 600-second search budget. The default PCA target is 90% retained variance;
other criteria are defined in `DimensionConfig`. Unmet criteria are disclosed.

## Resume and outputs

```sh
python scripts/run_agent.py /absolute/path/data.csv --out outputs/analysis --resume
```

Use the same input and saved configuration/context. Checkpoint verification
rejects changed evidence rather than silently reusing it. A completed run contains
plans, embeddings, evaluation, figures, a combined report and stage checkpoints.
Paths in saved scientific evidence identify original inputs; they are not files
that must exist merely to read the submitted reports.

Fresh analysis requires Codex. Setting `report.mode` to `evidence_only` suppresses
the report model call, not the preprocessing and selection calls. Lower-level
commands expose ingestion, preprocessing, selection, execution and evaluation;
each script's `--help` documents its arguments. Use the integrated entry point
for the default complete workflow.
