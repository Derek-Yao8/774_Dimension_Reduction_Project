# generated_report_1

Generation mode: evidence_only.

This is an automated analysis report, not the manually prepared course report.

Evidence links point to bundled JSON records. JSON fragments identify fields. Recorded reasons are planner explanations, not independent proof. Citation validation checks references and fingerprints, not scientific truth.

Verification scope: before requesting or replaying the narrative, Python rehashed the processed matrix and saved embedding, checked selection/execution/evaluation linkage and preprocessing consistency, and rejected mismatches. The narrative model itself did not inspect files, view plot images or rerun computations. Statements in the narrative about lack of independent verification apply to that model review, not to these automated file-integrity checks.

![Saved embedding visualization](embedding.png)

This method belongs to a jointly selected set. Other-method assessments below may describe co-selected methods, not exclusions. No ranking is implied.

## Visualization scope

    {
      "sample_size": 10000,
      "representation_dimensions": 2,
      "view_dimensions": 2,
      "color_column": "label_0",
      "color_status": "categorical",
      "description": "First coordinates of the saved embedding; no new 2D fit."
    }

## Narrative status

Evidence-only rendering: no new AI synthesis. Do not label this an AI-generated narrative.

## Verbatim decision-time records

These statements were written before fitting. Unknown quantities here may be measured in the later evaluation.

### Preprocessing explanation

    "Retain all observations and pixel features in their shared intensity units. No count transformations or reduction are needed at this stage."

### Full preprocessing plan and rationale

    {
      "reason": "Keep the original RGB intensities without scaling or centering to preserve their common 0–255 units and relative variation. The user confirms these are not counts, so count normalization and log1p are unnecessary. No missing, infinite, all-missing, or constant features are reported, so retain error policies and omit imputation, feature drops, and constant removal. All features are numeric; labels remain metadata. Retain all 10,004 observations without a new split. Output dimensionality is configured separately; this plan performs no dimensionality reduction. All resource limits remain at their defaults.",
      "schema_version": "1.0",
      "drop_features": [],
      "infinity": "error",
      "missing": "error",
      "all_missing": "error",
      "categorical": "error",
      "remove_constants": false,
      "count_data_confirmed": false,
      "normalize_total": null,
      "log1p": false,
      "scale": "none",
      "center": false,
      "max_categories": 100,
      "max_output_features": 100000,
      "max_dense_bytes": 1000000000,
      "ambiguity_resolutions": []
    }

### Method-selection explanation

    "Member of a jointly selected set; alternatives are assessments, not necessarily exclusions."

### Full selected plan, scientific reasons, feasibility reasons, alternatives and limitations

    {
      "method": "pca",
      "n_components": 2,
      "parameters": {
        "svd_solver": "randomized"
      },
      "reason": "PCA is a scientifically appropriate, computationally eligible variance-preserving baseline for the unchanged numeric representation. Execute it with estimator centering, no whitening, two dimensions, and seed 0. Scientific suitability and resource eligibility are assessed separately below. Diagnostics cover only 512 sampled observations; they do not establish full-data geometry, connectivity, conditioning, or achievable two-dimensional fidelity. No method is ranked, and no sampling, preprocessing changes, label use, or resource-limit changes are authorized.",
      "scientific_reason": "Centered PCA directly addresses variance-preserving linear summarization of the fixed numeric representation without requiring a manifold assumption. The sampled feature variances show variation but do not establish a covariance spectrum or the adequacy of two components.",
      "feasibility_reason": "Recorded eligibility is true for dense input with 10004 observations and 2352 features. Randomized SVD is supported and appropriate for computing two components without a full decomposition; use seed 0. The estimator performs centering despite preprocessing center=false.",
      "limitations": [
        "Two components may retain little total variance; no covariance spectrum is available.",
        "The unchanged feature scales define the variance objective.",
        "Randomized SVD is approximate, and eligibility is not a hard memory or runtime guarantee."
      ],
      "alternatives": {
        "mds": {
          "scientific_reason": "Metric Euclidean MDS is suitable for exploring how well the fixed Euclidean dissimilarities can be represented in two dimensions. Sampled distances are nondegenerate, with coefficient of variation approximately 0.381; this does not establish low-dimensional distance fidelity.",
          "feasibility_reason": "Ineligible: 10004 observations exceed the 5000 manifold limit, and the conservative dense/pairwise working-array screen exceeds the 1000000000-byte limit. No automatic sampling is allowed."
        },
        "isomap": {
          "scientific_reason": "Isomap needs meaningful local Euclidean edges whose shortest paths approximate relevant manifold distances. Connected union graphs at k=5,15,30 on the 512-row sample establish sampled connectivity only; there is no evidence validating geodesic geometry or excluding shortcut edges. This is insufficient justification for imposing a geodesic distance objective.",
          "feasibility_reason": "Also ineligible: the 5000-observation manifold limit and conservative dense/pairwise working-array limit are exceeded."
        },
        "lle": {
          "scientific_reason": "Standard LLE assumes informative, stable local linear reconstruction weights. No local rank, reconstruction residual, or conditioning diagnostics are available. The absence of exact duplicates in the sample and sampled graph connectivity do not establish these prerequisites.",
          "feasibility_reason": "Dense storage is supported, but the method is ineligible because 10004 observations exceed the 5000 manifold observation limit."
        },
        "kernel_pca": {
          "scientific_reason": "RBF Kernel PCA is suitable as an exploratory nonlinear similarity representation of the unchanged Euclidean input. Positive, variable sampled distances support a nondegenerate Gaussian similarity construction, without establishing a nonlinear manifold or superiority to a linear projection.",
          "feasibility_reason": "Ineligible: the manifold observation limit and conservative new-method pairwise/workspace screen are exceeded."
        },
        "laplacian_eigenmaps": {
          "scientific_reason": "Normalized Laplacian Eigenmaps is suitable for exploratory preservation of Euclidean graph adjacency. Connected sampled union graphs at all three tested neighbor counts provide limited support for this graph-based exploration, without proving meaningful biological neighborhoods. A connected full-data union binary graph remains a mandatory execution prerequisite.",
          "feasibility_reason": "Ineligible: the manifold observation limit and conservative new-method pairwise/workspace screen are exceeded, even though sparse graphs can be used. Full-data connectivity has not been verified."
        },
        "diffusion_maps": {
          "scientific_reason": "Gaussian Diffusion Maps is suitable as an exploratory representation of multistep Euclidean similarity. The nondegenerate sampled distances support constructing Gaussian affinities, but do not establish a physical diffusion process, biological trajectory, or intrinsic manifold.",
          "feasibility_reason": "Ineligible: the manifold observation limit and conservative new-method pairwise/workspace screen are exceeded."
        },
        "tsne": {
          "scientific_reason": "t-SNE is suitable for exploratory visualization of local Euclidean similarities. The sampled median nearest-neighbor distance is about half the median pairwise distance, providing limited evidence of local distance contrast. Its suitability does not depend on preserving global Euclidean distances.",
          "feasibility_reason": "Two output dimensions are supported by Barnes-Hut t-SNE, but the method is ineligible under both the manifold observation limit and conservative new-method pairwise/workspace screen."
        },
        "umap": {
          "scientific_reason": "UMAP is suitable for exploratory visualization of local Euclidean neighborhood relationships. Sampled local distance contrast and connected sampled graphs support exploration, while leaving full-data neighborhood meaning and connectivity uncertain. Low global Euclidean distortion is not its objective.",
          "feasibility_reason": "Ineligible: the manifold observation limit and conservative new-method pairwise/workspace screen are exceeded, even when sparse graphs are used."
        }
      }
    }

### Feasibility screens

    {
      "pca": {
        "eligible": true,
        "reasons": []
      },
      "mds": {
        "eligible": false,
        "reasons": [
          "Configured manifold observation limit is 5000; no automatic sampling.",
          "Conservative dense/pairwise working-array screen exceeds configured working-byte limit."
        ]
      },
      "isomap": {
        "eligible": false,
        "reasons": [
          "Configured manifold observation limit is 5000; no automatic sampling.",
          "Conservative dense/pairwise working-array screen exceeds configured working-byte limit."
        ]
      },
      "lle": {
        "eligible": false,
        "reasons": [
          "Configured manifold observation limit is 5000; no automatic sampling."
        ]
      },
      "kernel_pca": {
        "eligible": false,
        "reasons": [
          "Configured manifold observation limit is 5000; no automatic sampling.",
          "Conservative new-method pairwise/workspace screen exceeds configured working-byte limit (even when the implementation can use sparse graphs)."
        ]
      },
      "laplacian_eigenmaps": {
        "eligible": false,
        "reasons": [
          "Configured manifold observation limit is 5000; no automatic sampling.",
          "Conservative new-method pairwise/workspace screen exceeds configured working-byte limit (even when the implementation can use sparse graphs)."
        ]
      },
      "diffusion_maps": {
        "eligible": false,
        "reasons": [
          "Configured manifold observation limit is 5000; no automatic sampling.",
          "Conservative new-method pairwise/workspace screen exceeds configured working-byte limit (even when the implementation can use sparse graphs)."
        ]
      },
      "tsne": {
        "eligible": false,
        "reasons": [
          "Configured manifold observation limit is 5000; no automatic sampling.",
          "Conservative new-method pairwise/workspace screen exceeds configured working-byte limit (even when the implementation can use sparse graphs)."
        ]
      },
      "umap": {
        "eligible": false,
        "reasons": [
          "Configured manifold observation limit is 5000; no automatic sampling.",
          "Conservative new-method pairwise/workspace screen exceeds configured working-byte limit (even when the implementation can use sparse graphs)."
        ]
      }
    }

## Complete decision and configuration ledger

An aggregate rationale is not a guaranteed field-level justification. Unrecorded provenance and unsupported values are explicitly flagged.

### preprocessing.drop_features

Value:

    []

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.infinity

Value:

    "error"

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.missing

Value:

    "error"

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.all_missing

Value:

    "error"

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.categorical

Value:

    "error"

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.remove_constants

Value:

    false

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.count_data_confirmed

Value:

    false

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.normalize_total

Value:

    null

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.log1p

Value:

    false

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.scale

Value:

    "none"

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.center

Value:

    false

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.max_categories

Value:

    100

Decision authority: Application-enforced resource setting.

Planner was prohibited from changing this resource setting; its numeric value is an implementation policy, not a measured optimum.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.max_output_features

Value:

    100000

Decision authority: Application-enforced resource setting.

Planner was prohibited from changing this resource setting; its numeric value is an implementation policy, not a measured optimum.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.max_dense_bytes

Value:

    1000000000

Decision authority: Application-enforced resource setting.

Planner was prohibited from changing this resource setting; its numeric value is an implementation policy, not a measured optimum.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### preprocessing.ambiguity_resolutions

Value:

    []

Decision authority: Saved preprocessing planner proposal.

See the verbatim aggregate preprocessing rationale. A separate field-level reason/evidence mapping was not recorded; support for this individual value is not independently verified.

Evidence: [preprocessing.plan](evidence/preprocessing.json#/plan), [input_profile](evidence/input_profile.json)

### selection.method

Value:

    "pca"

Decision authority: Saved method planner proposal within Python eligibility constraints.

See verbatim scientific and feasibility reasons. No comparative optimization establishes this value as best.

Evidence: [selection.plan](evidence/selection.json#/plan), [selection.feasibility_checks](evidence/selection.json#/feasibility_checks), [selection.resource_limits](evidence/selection.json#/resource_limits)

### selection.n_components

Value:

    2

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [selection.plan](evidence/selection.json#/plan), [selection.feasibility_checks](evidence/selection.json#/feasibility_checks), [selection.resource_limits](evidence/selection.json#/resource_limits), [workflow_config.origins](evidence/workflow_config.json#/origins)

### selection.svd_solver

Value:

    "randomized"

Decision authority: Saved method planner proposal within Python eligibility constraints.

See verbatim scientific and feasibility reasons. No comparative optimization establishes this value as best.

Evidence: [selection.plan](evidence/selection.json#/plan), [selection.feasibility_checks](evidence/selection.json#/feasibility_checks), [selection.resource_limits](evidence/selection.json#/resource_limits)

### execution.attempt_1.copy

Value:

    true

Decision authority: Executor or library setting; not a separately recorded Codex decision.

Effective value is recorded by the fitted estimator. For parameters outside the plan, no individual scientific tuning justification was recorded.

Evidence: [execution.attempts](evidence/execution.json#/attempts)

### execution.attempt_1.iterated_power

Value:

    7

Decision authority: Executor or library setting; not a separately recorded Codex decision.

Effective value is recorded by the fitted estimator. For parameters outside the plan, no individual scientific tuning justification was recorded.

Evidence: [execution.attempts](evidence/execution.json#/attempts)

### execution.attempt_1.n_components

Value:

    2

Decision authority: Executor or library setting; not a separately recorded Codex decision.

Effective value is recorded by the fitted estimator. For parameters outside the plan, no individual scientific tuning justification was recorded.

Evidence: [execution.attempts](evidence/execution.json#/attempts)

### execution.attempt_1.n_oversamples

Value:

    10

Decision authority: Executor or library setting; not a separately recorded Codex decision.

Effective value is recorded by the fitted estimator. For parameters outside the plan, no individual scientific tuning justification was recorded.

Evidence: [execution.attempts](evidence/execution.json#/attempts)

### execution.attempt_1.power_iteration_normalizer

Value:

    "QR"

Decision authority: Executor or library setting; not a separately recorded Codex decision.

Effective value is recorded by the fitted estimator. For parameters outside the plan, no individual scientific tuning justification was recorded.

Evidence: [execution.attempts](evidence/execution.json#/attempts)

### execution.attempt_1.random_state

Value:

    0

Decision authority: Executor or library setting; not a separately recorded Codex decision.

Effective value is recorded by the fitted estimator. For parameters outside the plan, no individual scientific tuning justification was recorded.

Evidence: [execution.attempts](evidence/execution.json#/attempts)

### execution.attempt_1.svd_solver

Value:

    "randomized"

Decision authority: Copied from saved method plan.

Effective value is recorded by the fitted estimator. For parameters outside the plan, no individual scientific tuning justification was recorded.

Evidence: [execution.attempts](evidence/execution.json#/attempts)

### execution.attempt_1.tol

Value:

    0.0

Decision authority: Executor or library setting; not a separately recorded Codex decision.

Effective value is recorded by the fitted estimator. For parameters outside the plan, no individual scientific tuning justification was recorded.

Evidence: [execution.attempts](evidence/execution.json#/attempts)

### execution.attempt_1.whiten

Value:

    false

Decision authority: Executor or library setting; not a separately recorded Codex decision.

Effective value is recorded by the fitted estimator. For parameters outside the plan, no individual scientific tuning justification was recorded.

Evidence: [execution.attempts](evidence/execution.json#/attempts)

### selection.max_working_bytes

Value:

    1000000000

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [selection.resource_limits](evidence/selection.json#/resource_limits), [workflow_config.origins](evidence/workflow_config.json#/origins)

### selection.max_manifold_observations

Value:

    5000

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [selection.resource_limits](evidence/selection.json#/resource_limits), [workflow_config.origins](evidence/workflow_config.json#/origins)

### evaluation.max_samples

Value:

    512

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [evaluation.config](evidence/evaluation.json#/config), [workflow_config.origins](evidence/workflow_config.json#/origins)

### evaluation.max_working_bytes

Value:

    128000000

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [evaluation.config](evidence/evaluation.json#/config), [workflow_config.origins](evidence/workflow_config.json#/origins)

### evaluation.neighbors

Value:

    5

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [evaluation.config](evidence/evaluation.json#/config), [workflow_config.origins](evidence/workflow_config.json#/origins)

### evaluation.seed

Value:

    0

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [evaluation.config](evidence/evaluation.json#/config), [workflow_config.origins](evidence/workflow_config.json#/origins)

### evaluation.max_plot_samples

Value:

    10000

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [evaluation.config](evidence/evaluation.json#/config), [workflow_config.origins](evidence/workflow_config.json#/origins)

### evaluation.max_categories

Value:

    20

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [evaluation.config](evidence/evaluation.json#/config), [workflow_config.origins](evidence/workflow_config.json#/origins)

### evaluation.threads

Value:

    2

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [evaluation.config](evidence/evaluation.json#/config), [workflow_config.origins](evidence/workflow_config.json#/origins)

### diagnostics.max_samples

Value:

    512

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [diagnostics.config](evidence/diagnostics.json#/config), [workflow_config.origins](evidence/workflow_config.json#/origins)

### diagnostics.max_working_bytes

Value:

    128000000

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [diagnostics.config](evidence/diagnostics.json#/config), [workflow_config.origins](evidence/workflow_config.json#/origins)

### diagnostics.seed

Value:

    0

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [diagnostics.config](evidence/diagnostics.json#/config), [workflow_config.origins](evidence/workflow_config.json#/origins)

### diagnostics.neighbors

Value:

    [
      5,
      15,
      30
    ]

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [diagnostics.config](evidence/diagnostics.json#/config), [workflow_config.origins](evidence/workflow_config.json#/origins)

### execution.threads

Value:

    2

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [execution.threads](evidence/execution.json#/threads), [workflow_config.origins](evidence/workflow_config.json#/origins)

### execution.timeout_seconds_per_attempt

Value:

    600

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [execution.timeout_seconds_per_attempt](evidence/execution.json#/timeout_seconds_per_attempt), [workflow_config.origins](evidence/workflow_config.json#/origins)

### execution.seed

Value:

    0

Decision authority: Execution configuration.

Resource/reproducibility/failure policy. Caller-vs-default provenance and a per-value rationale were not saved.

Evidence: [execution.seed](evidence/execution.json#/seed)

### execution.allow_fallback

Value:

    true

Decision authority: application default (recorded by workflow coordinator).

Exact value and caller/default provenance were saved before planning. This does not establish scientific optimality.

Evidence: [execution.allow_fallback](evidence/execution.json#/allow_fallback), [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.loader.split

Value:

    "val"

Decision authority: caller configuration.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.loader.orientation

Value:

    null

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.loader.label_column

Value:

    null

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.loader.id_column

Value:

    null

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.method_policy

Value:

    "all_suitable"

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimensions

Value:

    2

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_mode

Value:

    "fixed"

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.max_dimensions

Value:

    20

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.candidates

Value:

    [
      2,
      3,
      5,
      10,
      20
    ]

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.max_fits

Value:

    5

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.total_seconds

Value:

    600

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.variance_target

Value:

    0.9

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.distance_error_target

Value:

    0.1

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.trustworthiness_target

Value:

    0.95

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.reconstruction_target

Value:

    0.1

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.reconstruction_weight

Value:

    0.1

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.complexity_penalty

Value:

    0.01

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.min_improvement

Value:

    0.005

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.plateau_patience

Value:

    2

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.evaluation_samples

Value:

    256

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.dimension_search.evaluation_neighbors

Value:

    5

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.preprocessing_attempts

Value:

    2

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.selection_attempts

Value:

    1

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.max_model_calls

Value:

    5

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.planner_timeout

Value:

    180

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.resources.max_working_bytes

Value:

    1000000000

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.resources.max_manifold_observations

Value:

    5000

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.diagnostics.max_samples

Value:

    512

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.diagnostics.max_working_bytes

Value:

    128000000

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.diagnostics.seed

Value:

    0

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.diagnostics.neighbors

Value:

    [
      5,
      15,
      30
    ]

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.execution.timeout

Value:

    600

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.execution.threads

Value:

    2

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.execution.allow_fallback

Value:

    true

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.evaluation.max_samples

Value:

    512

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.evaluation.max_working_bytes

Value:

    128000000

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.evaluation.neighbors

Value:

    5

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.evaluation.seed

Value:

    0

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.evaluation.max_plot_samples

Value:

    10000

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.evaluation.max_categories

Value:

    20

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.evaluation.threads

Value:

    2

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.report.name

Value:

    "generated_report_1"

Decision authority: caller configuration.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.report.mode

Value:

    "codex"

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.report.timeout

Value:

    300

Decision authority: caller configuration.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

### workflow.report.color_column

Value:

    null

Decision authority: application default.

Initial configuration; unused method/mode-specific settings are retained for reproducibility, not claimed to have been applied.

Evidence: [workflow_config.origins](evidence/workflow_config.json#/origins)

## Post-execution observations

These results assess the output; they were not known when the original method was chosen.

### Every execution attempt, effective parameters, warnings and errors

    [
      {
        "plan": {
          "method": "pca",
          "n_components": 2,
          "parameters": {
            "svd_solver": "randomized"
          },
          "reason": "PCA is a scientifically appropriate, computationally eligible variance-preserving baseline for the unchanged numeric representation. Execute it with estimator centering, no whitening, two dimensions, and seed 0. Scientific suitability and resource eligibility are assessed separately below. Diagnostics cover only 512 sampled observations; they do not establish full-data geometry, connectivity, conditioning, or achievable two-dimensional fidelity. No method is ranked, and no sampling, preprocessing changes, label use, or resource-limit changes are authorized.",
          "scientific_reason": "Centered PCA directly addresses variance-preserving linear summarization of the fixed numeric representation without requiring a manifold assumption. The sampled feature variances show variation but do not establish a covariance spectrum or the adequacy of two components.",
          "feasibility_reason": "Recorded eligibility is true for dense input with 10004 observations and 2352 features. Randomized SVD is supported and appropriate for computing two components without a full decomposition; use seed 0. The estimator performs centering despite preprocessing center=false.",
          "limitations": [
            "Two components may retain little total variance; no covariance spectrum is available.",
            "The unchanged feature scales define the variance objective.",
            "Randomized SVD is approximate, and eligibility is not a hard memory or runtime guarantee."
          ],
          "alternatives": {
            "mds": {
              "scientific_reason": "Metric Euclidean MDS is suitable for exploring how well the fixed Euclidean dissimilarities can be represented in two dimensions. Sampled distances are nondegenerate, with coefficient of variation approximately 0.381; this does not establish low-dimensional distance fidelity.",
              "feasibility_reason": "Ineligible: 10004 observations exceed the 5000 manifold limit, and the conservative dense/pairwise working-array screen exceeds the 1000000000-byte limit. No automatic sampling is allowed."
            },
            "isomap": {
              "scientific_reason": "Isomap needs meaningful local Euclidean edges whose shortest paths approximate relevant manifold distances. Connected union graphs at k=5,15,30 on the 512-row sample establish sampled connectivity only; there is no evidence validating geodesic geometry or excluding shortcut edges. This is insufficient justification for imposing a geodesic distance objective.",
              "feasibility_reason": "Also ineligible: the 5000-observation manifold limit and conservative dense/pairwise working-array limit are exceeded."
            },
            "lle": {
              "scientific_reason": "Standard LLE assumes informative, stable local linear reconstruction weights. No local rank, reconstruction residual, or conditioning diagnostics are available. The absence of exact duplicates in the sample and sampled graph connectivity do not establish these prerequisites.",
              "feasibility_reason": "Dense storage is supported, but the method is ineligible because 10004 observations exceed the 5000 manifold observation limit."
            },
            "kernel_pca": {
              "scientific_reason": "RBF Kernel PCA is suitable as an exploratory nonlinear similarity representation of the unchanged Euclidean input. Positive, variable sampled distances support a nondegenerate Gaussian similarity construction, without establishing a nonlinear manifold or superiority to a linear projection.",
              "feasibility_reason": "Ineligible: the manifold observation limit and conservative new-method pairwise/workspace screen are exceeded."
            },
            "laplacian_eigenmaps": {
              "scientific_reason": "Normalized Laplacian Eigenmaps is suitable for exploratory preservation of Euclidean graph adjacency. Connected sampled union graphs at all three tested neighbor counts provide limited support for this graph-based exploration, without proving meaningful biological neighborhoods. A connected full-data union binary graph remains a mandatory execution prerequisite.",
              "feasibility_reason": "Ineligible: the manifold observation limit and conservative new-method pairwise/workspace screen are exceeded, even though sparse graphs can be used. Full-data connectivity has not been verified."
            },
            "diffusion_maps": {
              "scientific_reason": "Gaussian Diffusion Maps is suitable as an exploratory representation of multistep Euclidean similarity. The nondegenerate sampled distances support constructing Gaussian affinities, but do not establish a physical diffusion process, biological trajectory, or intrinsic manifold.",
              "feasibility_reason": "Ineligible: the manifold observation limit and conservative new-method pairwise/workspace screen are exceeded."
            },
            "tsne": {
              "scientific_reason": "t-SNE is suitable for exploratory visualization of local Euclidean similarities. The sampled median nearest-neighbor distance is about half the median pairwise distance, providing limited evidence of local distance contrast. Its suitability does not depend on preserving global Euclidean distances.",
              "feasibility_reason": "Two output dimensions are supported by Barnes-Hut t-SNE, but the method is ineligible under both the manifold observation limit and conservative new-method pairwise/workspace screen."
            },
            "umap": {
              "scientific_reason": "UMAP is suitable for exploratory visualization of local Euclidean neighborhood relationships. Sampled local distance contrast and connected sampled graphs support exploration, while leaving full-data neighborhood meaning and connectivity uncertain. Low global Euclidean distortion is not its objective.",
              "feasibility_reason": "Ineligible: the manifold observation limit and conservative new-method pairwise/workspace screen are exceeded, even when sparse graphs are used."
            }
          }
        },
        "status": "complete",
        "metrics": {
          "explained_variance_ratio": [
            0.5453597453418031,
            0.02260596224863435
          ],
          "singular_values": [
            131340.27523672834,
            26740.398924723842
          ]
        },
        "effective_parameters": {
          "copy": true,
          "iterated_power": 7,
          "n_components": 2,
          "n_oversamples": 10,
          "power_iteration_normalizer": "QR",
          "random_state": 0,
          "svd_solver": "randomized",
          "tol": 0.0,
          "whiten": false
        },
        "dependency_versions": {},
        "warnings": [],
        "elapsed_seconds": 1.0272651670020423
      }
    ]

### Execution notices and fallback disclosure

    {
      "fallback_occurred": false,
      "fallback_planner_calls": 0,
      "notices": [
        "EXECUTION SUCCEEDED: pca {\"svd_solver\": \"randomized\"}"
      ],
      "dimension_mode": "fixed",
      "selected_dimensions": 2
    }

### Full-representation evaluation

    {
      "sample_size": 512,
      "metrics": {
        "trustworthiness": 0.8114312065972222,
        "normalized_distance_error": 0.39269117260954034,
        "scale_aligned_distance_error": 0.3522550168455336,
        "distance_spearman": 0.8096712258680918,
        "neighbor_overlap": 0.13828125000000002
      },
      "skipped": {},
      "neighbors": 5,
      "distance_scale_factor": 1.2276647793429527
    }

### Coordinate-view evaluation

    {
      "sample_size": 512,
      "metrics": {
        "trustworthiness": 0.8114312065972222,
        "normalized_distance_error": 0.39269117260954034,
        "scale_aligned_distance_error": 0.3522550168455336,
        "distance_spearman": 0.8096712258680918,
        "neighbor_overlap": 0.13828125000000002
      },
      "skipped": {},
      "neighbors": 5,
      "distance_scale_factor": 1.2276647793429527
    }

### Evaluation limitations

    [
      "Metrics compare Euclidean distances in preprocessed feature space, not raw data or biological truth.",
      "Neighborhoods are within the recorded sample, not the full dataset; ties can affect ranks.",
      "Scores are descriptive in-sample evidence, not held-out validation or proof of an optimal plan.",
      "Memory estimate bounds working arrays heuristically; input storage and library overhead are excluded.",
      "First-coordinate plots can hide structure. Labels color plots only and do not influence scores.",
      "Euclidean distortion need not match nonlinear methods objectives; no universal pass/fail threshold."
    ]

## Evidence gaps and limits of attribution

- Historical preprocessing reasons are aggregate prose, not per-operation evidence mappings.
- A recorded setting does not establish why that exact numerical value is best; many settings are application policies or library defaults.
- Historical configuration does not always identify caller override versus default. No user instruction is inferred from a matching default.
- No exhaustive method comparison or scientific-optimality proof was performed.
- Model synthesis can be mistaken despite valid citations. Full records allow human review.
- The report model receives records and metrics, not the plot image; it does not perform visual assessment.

## Source bundle and reproducibility

See [manifest](manifest.json), [evidence catalog](evidence_catalog.json), [decision ledger](decision_ledger.json) and [generation status](report_generation.json). Original JSON files are copied without modifying their contents. They may contain feature names or local source paths; review before public sharing.

- [input_profile](evidence/input_profile.json)
- [preprocessing](evidence/preprocessing.json)
- [preprocessing_audit](evidence/preprocessing_audit.json)
- [processed_profile](evidence/processed_profile.json)
- [selection](evidence/selection.json)
- [selection_evidence](evidence/selection_evidence.json)
- [diagnostics](evidence/diagnostics.json)
- [execution](evidence/execution.json)
- [evaluation](evidence/evaluation.json)
- [workflow_config](evidence/workflow_config.json)
