# Dimension Reduction Analyst

A Python agent for exploratory dimension reduction of supported datasets. Given
a dataset and scientific context, it inspects the data, obtains validated Codex
preprocessing and method plans, executes every scientifically suitable and
computationally feasible method, evaluates successful embeddings, and writes one
combined report. Methods are not ranked and no winner is selected. Output is
fixed at two dimensions by default; automatic dimension selection is optional.

## Installation on macOS

Use Python 3.11 or newer; the supplied dependency snapshot was tested with Python
3.13.2 on macOS arm64 (Apple Silicon). In Terminal, open the repository folder
and create a local environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-macos-tested.txt
python -m pip install -e .
```

Dependency availability can differ across Python versions and architectures.
`pyproject.toml` defines the supported
dependency ranges; use `python -m pip install -e ".[dev]"` for a compatible
installation when the exact snapshot is unavailable.

Fresh AI decisions require a compatible Codex CLI, ChatGPT authentication,
network access and available Codex allowance. Run `codex login` before analysis.
The adapter requires support for `exec`, `--ignore-user-config`, `--ephemeral`,
`--output-schema`, `--json`, and `--image`. It has no API-key fallback and does
not pin an underlying model. Plot images and structured evidence are supplied
to Codex for report generation. Reading the submitted reports needs no login.

## Analyze a dataset

```sh
python scripts/run_agent.py /absolute/path/data.csv --orientation rows --out outputs/analysis --context "Describe the measurements, units, and analysis objective."
```

Use a new output directory. Optional `--id-column` and `--label-column` identify
metadata that must not be fitted as features. Supported loaders include numeric
NumPy arrays, delimited tables, MedMNIST NPZ, 10x Matrix Market directories and
AnnData H5AD. Ambiguous orientation or missing scientific context may require
clarification. Arbitrary formats and arbitrary preprocessing are not supported.

See [usage and configuration](docs/usage.md) and [system design](docs/system.md).

## Submitted analyses

- [generated_report_1: PathMNIST](results/pathmnist/generated_report_1.md)
- [generated_report_2: PBMC](results/pbmc/generated_report_2.md)

PathMNIST uses 10,004 validation images with 2,352 flattened RGB features. PBMC
uses all 2,700 cells and 16,634 nonconstant genes after count normalization and
log1p. No additional cell-quality filtering or variable-gene selection is used.
The experiments use fixed 2D and no new train/test split. PathMNIST executes PCA;
PBMC executes PCA, MDS, t-SNE and UMAP. All successful embeddings are evaluated.
See [experiment settings and findings](docs/experiments.md) for commands and scope.

Keep each report folder intact: figures, metrics and linked evidence are included.
Raw datasets and full numerical replay checkpoints are not bundled. Fresh runs
make new model decisions and need not reproduce the exact submitted selections
or wording. Source data identifiers and settings are recorded with the results.

## Validation

```sh
python -m pytest -q
```

All 178 tests pass in the tested macOS environment (one SciPy deprecation warning).
Tests cover input handling, preprocessing, response validation, all nine methods,
evaluation, image reporting, bounded failures, checkpoints and numerical replay.
Controlled planner responses test software behavior; they are not independent
evidence of scientific judgment quality. See the limitations in the system guide.

The separate manually prepared course report is not included in this repository.
