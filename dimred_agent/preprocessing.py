"""Validated, fixed-order preprocessing for exploratory (full-dataset) analysis.

Plans are supplied explicitly. This module does not make AI decisions or provide
a fit/transform interface for predictive train/test workflows.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from .data import Dataset, InputError


@dataclass(frozen=True)
class PreprocessingPlan:
    reason: str
    schema_version: str = "1.0"
    drop_features: tuple[int, ...] = ()
    infinity: str = "error"             # error | missing
    missing: str = "error"              # error | mean | median | zero
    all_missing: str = "error"          # error | drop
    categorical: str = "error"          # error | onehot
    remove_constants: bool = False
    count_data_confirmed: bool = False
    normalize_total: float | None = None
    log1p: bool = False
    scale: str = "none"                 # none | maxabs | standard
    center: bool = False
    max_categories: int = 100
    max_output_features: int = 100000
    max_dense_bytes: int = 1_000_000_000
    # Explicit interpretation of each ambiguity, in the original order.
    ambiguity_resolutions: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise InputError("Preprocessing plan must be a JSON object.")
        unknown = set(value) - {f.name for f in fields(cls)}
        if unknown:
            raise InputError(f"Unknown plan fields: {sorted(unknown)}")
        try:
            plan = cls(**value)
        except TypeError as exc:
            raise InputError(str(exc)) from exc
        plan.validate()
        return plan

    def validate(self):
        if self.schema_version != "1.0" or not isinstance(self.reason, str) or not self.reason.strip():
            raise InputError("Plan requires schema_version 1.0 and a nonempty reason.")
        for key, allowed in {"infinity": {"error", "missing"}, "missing": {"error", "mean", "median", "zero"},
                             "all_missing": {"error", "drop"}, "categorical": {"error", "onehot"},
                             "scale": {"none", "maxabs", "standard"}}.items():
            if not isinstance(getattr(self, key), str) or getattr(self, key) not in allowed:
                raise InputError(f"Invalid {key} policy.")
        for key in ("remove_constants", "count_data_confirmed", "log1p", "center"):
            if type(getattr(self, key)) is not bool:
                raise InputError(f"{key} must be a boolean.")
        for key in ("max_categories", "max_output_features", "max_dense_bytes"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 1:
                raise InputError(f"{key} must be a positive integer.")
        if not isinstance(self.drop_features, (list, tuple)) or any(type(i) is not int or i < 0 for i in self.drop_features):
            raise InputError("drop_features must contain nonnegative integer positions.")
        if len(set(self.drop_features)) != len(self.drop_features):
            raise InputError("Duplicate drop_features positions.")
        if not isinstance(self.ambiguity_resolutions, (list, tuple)) or any(not isinstance(s, str) or not s.strip() for s in self.ambiguity_resolutions):
            raise InputError("ambiguity_resolutions must contain nonempty explanations.")
        if self.normalize_total is not None:
            if type(self.normalize_total) not in (int, float) or not np.isfinite(self.normalize_total) or self.normalize_total <= 0:
                raise InputError("normalize_total must be a positive finite number.")
            if not self.count_data_confirmed:
                raise InputError("Total-count normalization requires explicit count-data confirmation.")
        if self.center and self.scale != "standard":
            raise InputError("Centering is supported only with standard scaling.")


@dataclass
class PreprocessingResult:
    dataset: Dataset
    audit: dict

    def save(self, directory):
        """Persist transformed data, labels, metadata, plan and fitted statistics."""
        directory = Path(directory)
        if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
            raise InputError("Choose a new or empty preprocessing output directory.")
        directory.mkdir(parents=True, exist_ok=True)
        data = self.dataset
        if sparse.issparse(data.X):
            sparse.save_npz(directory / "measurements.sparse.npz", data.X)
        else:
            np.save(directory / "measurements.npy", data.X, allow_pickle=False)
        data.obs.to_csv(directory / "observations.csv", index_label="observation_id")
        data.var.to_csv(directory / "features.csv", index_label="feature_id")
        if data.labels is not None:
            data.labels.to_csv(directory / "labels.csv", index_label="observation_id")
        (directory / "preprocessing.json").write_text(json.dumps(self.audit, indent=2, allow_nan=False), encoding="utf-8")


def preprocess(dataset: Dataset, plan: PreprocessingPlan) -> PreprocessingResult:
    plan.validate()
    if len(plan.ambiguity_resolutions) != len(dataset.ambiguities):
        raise InputError("Provide one explicit resolution per input ambiguity before preprocessing.")
    n, p = dataset.X.shape
    if any(i >= p for i in plan.drop_features):
        raise InputError("drop_features contains an out-of-range position.")
    keep = [i for i in range(p) if i not in set(plan.drop_features)]
    if not keep:
        raise InputError("Plan removes every feature.")
    sparse_input = sparse.issparse(dataset.X)
    if not sparse_input and n * len(keep) * 8 > plan.max_dense_bytes:
        raise InputError("Dense float64 conversion exceeds the configured array-size limit.")
    if sparse_input and plan.center:
        raise InputError("Centering sparse data would densify it; choose center=false.")
    columns, metadata, events, imputation = [], [], [], []
    source = dataset.X.tocsc(copy=True) if sparse_input else dataset.X
    if sparse_input:
        source.sum_duplicates()
        source.eliminate_zeros()
    encoded = False
    for j in keep:
        name = str(dataset.var.index[j])
        record = {"source_position": j, "source_name": name}
        if sparse_input:
            column = source[:, j].astype(float)
            values = column.data.copy()
            numeric = True
        else:
            series = source.iloc[:, j] if isinstance(source, pd.DataFrame) else pd.Series(source[:, j])
            if pd.api.types.is_complex_dtype(series.dtype):
                raise InputError("Complex features are unsupported.")
            numeric = pd.api.types.is_numeric_dtype(series.dtype)
            values = series.to_numpy(dtype=float, na_value=np.nan, copy=True) if numeric else None
        if not numeric:
            if series.isna().all():
                if plan.all_missing == "drop":
                    events.append({"operation": "drop_all_missing", **record})
                    continue
                raise InputError(f"All-missing feature: {name}")
            if plan.categorical != "onehot":
                raise InputError(f"Non-numeric feature requires encoding or exclusion: {name}")
            if plan.normalize_total is not None or plan.log1p:
                raise InputError("Count/log transforms cannot be combined with categorical encoding.")
            if series.isna().any():
                raise InputError("Missing categories require explicit exclusion or upstream correction; numeric imputation does not apply.")
            codes, categories = pd.factorize(series, sort=False)
            if len(categories) > plan.max_categories:
                raise InputError(f"Too many categories in {name}; possible identifier/text column.")
            if len(metadata) + len(categories) > plan.max_output_features:
                raise InputError("Encoding exceeds output feature limit.")
            block = sparse.csr_matrix((np.ones(n), (np.arange(n), codes)), shape=(n, len(categories)))
            columns.append(block)
            metadata.extend([{**record, "category": str(v), "encoding": "onehot"} for v in categories])
            encoded = True
            continue
        if np.isinf(values).any():
            if plan.infinity == "error":
                raise InputError(f"Infinite values in {name}.")
            events.append({"operation": "infinity_to_missing", **record, "count": int(np.isinf(values).sum())})
            values[np.isinf(values)] = np.nan
        mask = np.isnan(values)
        missing = int(mask.sum())
        if missing == n:
            if plan.all_missing == "drop":
                events.append({"operation": "drop_all_missing", **record})
                continue
            raise InputError(f"All-missing feature: {name}")
        if missing:
            if plan.missing == "error":
                raise InputError(f"Missing values in {name}.")
            if sparse_input and plan.missing == "median":
                raise InputError("Sparse median imputation is unsupported; choose mean or zero.")
            fill = 0.0 if plan.missing == "zero" else (float(np.nansum(values) / (n - missing)) if plan.missing == "mean" else float(np.nanmedian(values)))
            values[mask] = fill
            imputation.append({**record, "count": missing, "fill": fill})
        if sparse_input:
            column.data = values
            column.eliminate_zeros()
            columns.append(column)
        else:
            columns.append(values[:, None])
        metadata.append({**record, "encoding": "numeric"})
    if not columns or len(metadata) > plan.max_output_features:
        raise InputError("No usable features or output feature limit exceeded.")
    X = sparse.hstack(columns, format="csr") if sparse_input or encoded else np.hstack(columns)
    if sparse.issparse(X):
        X.eliminate_zeros()
    raw = X.data if sparse.issparse(X) else X
    if not np.isfinite(raw).all():
        raise InputError("Imputation produced nonfinite values.")
    if plan.normalize_total is not None:
        if np.any(raw < 0) or np.any(raw != np.floor(raw)):
            raise InputError("Count normalization expects nonnegative integer-valued input.")
        totals = np.asarray(X.sum(axis=1)).ravel()
        if np.any(totals <= 0) or not np.isfinite(totals).all():
            raise InputError("Zero-total or nonfinite-total rows cannot be normalized; resolve explicitly.")
        factors = plan.normalize_total / totals
        X = sparse.diags(factors).dot(X).tocsr() if sparse.issparse(X) else X * factors[:, None]
        events.append({"operation": "normalize_total", "target": plan.normalize_total, "row_factors": factors.tolist()})
    if plan.log1p:
        raw = X.data if sparse.issparse(X) else X
        if np.any(raw < 0):
            raise InputError("This log1p tool requires nonnegative measurements.")
        if sparse.issparse(X):
            X.data = np.log1p(X.data)
        else:
            X = np.log1p(X)
        events.append({"operation": "log1p"})
    if sparse.issparse(X):
        low = X.min(axis=0).toarray().ravel()
        high = X.max(axis=0).toarray().ravel()
    else:
        low, high = X.min(axis=0), X.max(axis=0)
    constants = low == high
    if plan.remove_constants:
        events.append({"operation": "remove_constants", "removed": [m for m, flag in zip(metadata, constants) if flag]})
        X = X[:, ~constants]
        metadata = [m for m, flag in zip(metadata, constants) if not flag]
        if X.shape[1] == 0:
            raise InputError("Constant removal leaves no features.")
    if sparse.issparse(X) and plan.center:
        raise InputError("Centering encoded sparse data would densify it.")
    if plan.scale != "none":
        means = np.asarray(X.mean(axis=0)).ravel()
        if plan.scale == "maxabs":
            scales = abs(X).max(axis=0).toarray().ravel() if sparse.issparse(X) else np.abs(X).max(axis=0)
        else:
            variance = np.asarray(X.power(2).mean(axis=0)).ravel() - means**2 if sparse.issparse(X) else X.var(axis=0)
            scales = np.sqrt(np.maximum(variance, 0))
        scales[scales == 0] = 1
        X = X @ sparse.diags(1 / scales) if sparse.issparse(X) else (X - means if plan.center else X) / scales
        events.append({"operation": "scale", "kind": plan.scale, "center": plan.center, "means": means.tolist(), "scales": scales.tolist(), "ddof": 0})
    if sparse.issparse(X):
        X = X.tocsr()
        X.eliminate_zeros()
    if not np.isfinite(X.data if sparse.issparse(X) else X).all():
        raise InputError("Transformation produced nonfinite values.")
    var = pd.DataFrame(metadata, index=[f"feature_{i}" for i in range(len(metadata))])
    audit = {"schema_version": "1.0", "scope": "full-dataset exploratory preprocessing; not predictive train/test fitting",
             "plan": asdict(plan), "input_shape": [n, p], "output_shape": list(X.shape),
             "source_provenance": deepcopy(dataset.provenance), "input_assumptions": list(dataset.assumptions),
             "input_ambiguities": list(dataset.ambiguities), "imputation": imputation, "events": events,
             "row_order_preserved": True, "labels_used_for_transformations": False}
    # Ensure all fitted statistics can be persisted before returning success.
    json.dumps(audit, allow_nan=False)
    result = Dataset(X, dataset.obs.copy(deep=True), var,
                     dataset.labels.copy(deep=True) if dataset.labels is not None else None,
                     {**deepcopy(dataset.provenance), "preprocessing_plan": asdict(plan)},
                     list(dataset.assumptions) + ["Preprocessing fitted on the full exploratory dataset."], [])
    return PreprocessingResult(result, audit)
