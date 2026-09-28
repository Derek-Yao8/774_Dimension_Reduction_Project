# System design

## Decision and execution flow

Python loads the dataset, separates explicit labels and identifiers, and measures
shape, missingness, numeric/categorical feature types, sparsity and constants.
Codex receives a compact profile and caller context and proposes a preprocessing
plan. Python validates its fields and executes supported operations in a fixed
order: feature removal, infinity/missing handling or encoding, count
normalization, log1p, constant removal and scaling. Counts must be confirmed by
context; sparse input is not manually centered. Labels are display metadata,
not reduction features or evaluation targets.

After shared preprocessing, bounded diagnostics measure exact duplicates,
feature variance, Euclidean distance distributions and neighborhood connectivity.
Codex assesses each candidate's scientific suitability separately from Python's
resource and storage eligibility. Every suitable eligible method runs sequentially
in an isolated subprocess with validated parameters. Methods are PCA, RBF Kernel
PCA, metric MDS, Isomap, standard LLE, normalized Laplacian Eigenmaps, Gaussian
Diffusion Maps, Barnes-Hut t-SNE and UMAP. GPLVM is not implemented.

Each successful embedding receives numerical evaluation and plots. One report
request combines the evidence and actual PNGs. The response must reference known
evidence, match its fingerprint, and assess each supplied image exactly once.
The report uses connected paragraphs, with explicit reasons and limitations and
section-level evidence links. Raw selection records are supporting files rather
than repeated in the main narrative. The model cannot execute arbitrary analysis
code through the planner adapter.

## Quantitative and qualitative evaluation

Common geometry metrics are trustworthiness, nearest-neighbor overlap, distance
Spearman correlation, and scale-aligned distance error relative to preprocessed
Euclidean measurements. Method-specific diagnostics include PCA retained
variance, MDS stress, t-SNE KL divergence and graph diagnostics where supported.
Different objectives are not interchangeable. Scores use seeded samples under
the evaluation budget; they do not measure held-out prediction or biological
validity. Full embedding and plotted coordinate-view scores are distinguished.

Visual interpretation describes concentrations, overlap, gaps, elongation and
isolated points, relating these observations to measured evidence. Numeric labels
do not establish cell or tissue identities. Sampling, unequal axis scales,
overplotting and nonlinear intergroup distances constrain interpretation.
Unreadable images are disclosed. Image hashes establish artifact identity, not
the factual accuracy of model observations. Low scores do not force a winner or
trigger replacement.

## Resource controls and recovery

Defaults allow 1,000,000,000 estimated working-array bytes and 5,000 observations
for non-PCA methods. These are conservative screens, not hard process RAM limits.
For dense input with n observations and p features, the screen uses D=8np and
P=8n² bytes: all methods require 3D within the budget, MDS/Isomap require 6P+D,
and Kernel PCA/Laplacian Eigenmaps/Diffusion Maps/t-SNE/UMAP require 8P+D.
Sparse contracts impose additional restrictions; sparse LLE is unsupported.
No automatic fitting subsample bypasses the observation gate.

Execution defaults to 600 seconds per attempt and two threads, with estimator
constraints sometimes requiring one job. Diagnostics and evaluation each default
to 512 sampled observations and 128,000,000 working bytes. Evaluation uses five
neighbors and plots at most 10,000 observations. These are configurable
implementation settings rather than scientific acceptance thresholds.

The default model-request cap is five across stages and resumes; a normal run
uses three requests. One failure-only fallback request is allowed across the
method set. Failures, replacements and warnings are explicit. Other methods can
continue after a branch fails; partial completion is distinguished from success.
No fallback is triggered solely by poor metrics or an iteration-limit flag.

Checkpoints verify unchanged inputs/settings and artifact hashes before resume.
Numerical saved-plan replay is implemented but no replay bundles are submitted.
It requires a complete saved run and matching raw data, recomputes successful
branches without new AI calls, and fixes recorded dimensions. It does not repeat
failed methods or automatic searches. Report-only refresh also requires a complete
run; the compact submitted report folders alone are not checkpoint bundles.

## Scope and limitations

Fixed 2D is default. Optional dimension search is bounded within each selected
method and uses configurable method-specific criteria; it does not rank methods.
The default all-suitable workflow includes image interpretation even when only
one method executes. Explicit single-method mode and standalone report generation
use a separate text-only reporting path.

Scientific judgments and visual descriptions remain fallible. The system lacks
a general iterative scientific investigation loop, broad hyperparameter/seed
sensitivity studies, fitted-model persistence and a general out-of-sample
transform interface. The exact model is not pinned or recorded in the supplied
run events. Dependency and model changes may affect fresh results. Neither test
coverage nor successful execution establishes scientific optimality.
