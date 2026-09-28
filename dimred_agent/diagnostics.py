"""Bounded, reproducible geometry measurements; no embeddings or AI calls."""
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components
from scipy.spatial.distance import pdist, squareform

from .data import InputError


@dataclass(frozen=True)
class DiagnosticConfig:
    max_samples: int = 512
    max_working_bytes: int = 128_000_000
    seed: int = 0
    neighbors: tuple = (5, 15, 30)

    def __post_init__(self):
        for name in ("max_samples", "max_working_bytes"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise InputError(f"Diagnostic {name} must be a positive integer.")
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise InputError("Diagnostic seed must be an integer in [0, 2**32).")
        if (not isinstance(self.neighbors, tuple) or not 1 <= len(self.neighbors) <= 8
                or any(type(k) is not int or not 1 <= k <= 100 for k in self.neighbors)
                or len(set(self.neighbors)) != len(self.neighbors)):
            raise InputError("Choose 1 to 8 unique diagnostic neighbor counts in [1,100].")


def working_estimate(m, p):
    # Copies for variance/duplicate sorting, distances/sorting/graphs and vectors.
    # Includes a bounded dense sample even for sparse input; not process peak RAM.
    return 4 * m * p * 8 + 8 * m * m * 8 + 64 * p


def quantiles(values):
    return dict(zip(("min", "q25", "median", "q75", "max"),
                    map(float, np.quantile(values, [0, .25, .5, .75, 1]))))


def compute_diagnostics(X, config=None):
    config = config or DiagnosticConfig()
    if len(X.shape) != 2 or min(X.shape) == 0 or X.dtype.kind not in "biuf":
        raise InputError("Diagnostics require a nonempty real numeric matrix.")
    n, p = map(int, X.shape)
    report = {
        "schema_version": "1.0", "status": "complete", "input_shape": [n, p],
        "config": asdict(config), "metric": "euclidean", "sample_positions": [],
        "limitations": [
            "These diagnostics do not prove linearity, manifold structure or an optimal method.",
            "A sampled graph does not establish full-data connectivity or the same best neighbor count.",
            "Connectivity at large k can result from inappropriate bridges; it is not a quality score.",
            "Duplicate and unusual-distance observations are measured, never automatically removed.",
            "Feature variance is not a covariance spectrum or PCA explained variance.",
            "Memory screening excludes loading the input and is not a hard process RAM cap.",
        ],
    }
    low, high = 0, min(n, config.max_samples)
    while low < high:
        mid = (low + high + 1) // 2
        if working_estimate(mid, p) <= config.max_working_bytes:
            low = mid
        else:
            high = mid - 1
    m = low
    report.update(sample_size=m, sampled=m < n, estimated_working_bytes=working_estimate(m, p))
    if m < 2:
        report.update(status="skipped", reason="Fewer than two rows fit the diagnostic sample/budget.")
        return report
    positions = np.arange(n) if m == n else np.sort(np.random.default_rng(config.seed).choice(n, m, replace=False))
    report["sample_positions"] = positions.tolist()
    report["scope"] = "sample_only" if m < n else "all_observations"
    # Sparse input is never fully densified before sampling. The bounded sample
    # is explicitly materialized for stable Euclidean distance and variance math.
    rows = X[positions]
    sample = rows.toarray().astype(np.float64, copy=False) if sparse.issparse(rows) else np.array(rows, dtype=np.float64, copy=True)
    report["sample_materialized_dense"] = True
    if not np.isfinite(sample).all():
        raise InputError("Diagnostic sample contains missing or infinite values.")
    _, counts = np.unique(sample, axis=0, return_counts=True)
    report["duplicates"] = {
        "extra_identical_rows": int(m - len(counts)),
        "groups_with_duplicates": int(np.count_nonzero(counts > 1)),
        "rows_in_duplicate_groups": int(counts[counts > 1].sum()),
        "definition": "Exact equality of postprocessed sampled rows, not biological identity.",
    }
    with np.errstate(over="ignore", invalid="ignore"):
        variance = np.var(sample, axis=0, ddof=0)
        distances = pdist(sample, metric="euclidean")
    if np.isfinite(variance).all() and np.isfinite(variance.sum()):
        total = float(variance.sum())
        descending = np.sort(variance)[::-1]
        report["feature_variance"] = {
            "status": "complete", "ddof": 0, "distribution": quantiles(variance),
            "zero_variance_features": int(np.count_nonzero(variance == 0)),
            "largest_feature_share": float(descending[0] / total) if total else None,
            "top_five_feature_share": float(descending[:5].sum() / total) if total else None,
        }
    else:
        report["feature_variance"] = {"status": "skipped", "reason": "Numeric overflow; no scaling was silently applied."}
    if not np.isfinite(distances).all():
        report["status"] = "partial"
        report["distances"] = {"status": "skipped", "reason": "Euclidean distance overflow."}
        report["neighborhoods"] = [{"status": "skipped", "reason": "Distances are nonfinite."}]
        return report
    D = squareform(distances)
    np.fill_diagonal(D, np.inf)  # Exclude self, retain distinct zero-distance rows.
    order = np.argsort(D, axis=1, kind="stable")
    nearest = D[np.arange(m), order[:, 0]]
    mean = float(distances.mean())
    # Scale before computing spread to avoid squaring large distances.
    cv = float(np.std(distances / mean)) if mean > 0 and np.isfinite(mean) else None
    median = float(np.median(distances))
    report["distances"] = {
        "status": "complete", "pair_count": len(distances), "distribution": quantiles(distances),
        "coefficient_of_variation": cv,
        "zero_distance_pair_fraction": float(np.mean(distances == 0)),
        "nearest_neighbor_distribution": quantiles(nearest),
        "median_nearest_to_median_pairwise_ratio": float(np.median(nearest) / median) if median else None,
    }
    report["neighborhoods"] = []
    for k in config.neighbors:
        if k >= m:
            report["neighborhoods"].append({"k": k, "status": "skipped", "reason": "k must be smaller than sampled row count."})
            continue
        graph = sparse.csr_matrix((np.ones(m * k, dtype=np.uint8),
                                   (np.repeat(np.arange(m), k), order[:, :k].ravel())), shape=(m, m))
        graph = graph.maximum(graph.T)
        count, labels = connected_components(graph, directed=False)
        sizes = np.bincount(labels)
        boundary = D[np.arange(m), order[:, k - 1]]
        ties = np.sum(D == boundary[:, None], axis=1) > 1
        report["neighborhoods"].append({
            "k": k, "status": "complete", "components": int(count),
            "largest_component_fraction": float(sizes.max() / m),
            "smallest_component_size": int(sizes.min()),
            "boundary_distance_distribution": quantiles(boundary),
            "rows_with_boundary_distance_ties": int(ties.sum()),
            "graph": "undirected union kNN; self excluded; ties resolved by sampled row order",
        })
    if report["feature_variance"]["status"] != "complete":
        report["status"] = "partial"
    return report


def diagnostic_summary(report):
    """Only compact aggregate measurements go to the planner, not row positions."""
    return {k: v for k, v in report.items() if k not in ("sample_positions", "source_sha256")}


def diagnostics_from_run(directory, profile, config=None):
    """Read our processed numeric artifact; never infer data from a filename alone."""
    directory = Path(directory) / "preprocessed"
    is_sparse = profile["storage"].startswith("sparse")
    path = directory / ("measurements.sparse.npz" if is_sparse else "measurements.npy")
    X = sparse.load_npz(path).tocsr() if is_sparse else np.load(path, mmap_mode="r", allow_pickle=False)
    if list(X.shape) != [profile["n_observations"], profile["n_features"]]:
        raise InputError("Processed matrix shape disagrees with profile.")
    if X.dtype.kind not in "biuf":
        raise InputError("Processed matrix must be real numeric.")
    # Check all stored values in bounded blocks before trusting an old profile.
    if is_sparse:
        X.sum_duplicates()
        values = X.data
        for start in range(0, len(values), 100_000):
            if not np.isfinite(values[start:start + 100_000]).all():
                raise InputError("Processed matrix contains nonfinite values.")
    else:
        for start in range(0, X.shape[0], 32):
            if not np.isfinite(X[start:start + 32]).all():
                raise InputError("Processed matrix contains nonfinite values.")
    report = compute_diagnostics(X, config)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    report["source_sha256"] = digest.hexdigest()
    return report
