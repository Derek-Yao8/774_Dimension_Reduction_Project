import json
import numpy as np
import pytest
from scipy import sparse

from dimred_agent.data import InputError
from dimred_agent.diagnostics import DiagnosticConfig, compute_diagnostics, diagnostic_summary, diagnostics_from_run
from dimred_agent.reduction_planner import planning_evidence, reduction_instructions, run_reduction_planner
from test_reduction_planner import profile, ready, Fake


def test_known_values_and_duplicates():
    x = np.array([[0., 0], [0, 0], [3, 4]])
    original = x.copy()
    result = compute_diagnostics(x, DiagnosticConfig(neighbors=(1, 2, 5)))
    assert result["duplicates"]["extra_identical_rows"] == 1
    assert result["duplicates"]["rows_in_duplicate_groups"] == 2
    # Three pairs are 0, 5, 5; variances are 2 and 32/9.
    assert result["distances"]["distribution"]["median"] == 5
    assert result["distances"]["zero_distance_pair_fraction"] == pytest.approx(1 / 3)
    assert result["feature_variance"]["largest_feature_share"] == pytest.approx(.64)
    assert result["neighborhoods"][-1]["status"] == "skipped"
    np.testing.assert_array_equal(x, original)


def test_graph_connectivity_changes_with_k():
    x = np.array([[0., 0], [1, 0], [100, 0], [101, 0]])
    result = compute_diagnostics(x, DiagnosticConfig(neighbors=(1, 2)))
    assert [g["components"] for g in result["neighborhoods"]] == [2, 1]
    assert result["neighborhoods"][0]["largest_component_fraction"] == .5


def test_sparse_dense_agree_and_do_not_modify():
    x = np.array([[0., 0, 1], [0, 2, 0], [1, 2, 3], [0, 0, 1]])
    csr = sparse.csr_matrix(x)
    original = csr.copy()
    config = DiagnosticConfig(neighbors=(1, 2))
    assert compute_diagnostics(x, config) == compute_diagnostics(csr, config)
    assert (csr != original).nnz == 0


def test_sampling_reproducible_bounded_and_compact():
    x = np.arange(2000., dtype=float).reshape(100, 20)
    config = DiagnosticConfig(max_samples=40, max_working_bytes=20_000, seed=7)
    result = compute_diagnostics(x, config)
    assert result == compute_diagnostics(x, config)
    assert 2 <= result["sample_size"] < 40
    assert result["estimated_working_bytes"] <= config.max_working_bytes
    assert len(set(result["sample_positions"])) == result["sample_size"]
    assert "sample_positions" not in diagnostic_summary(result)
    other = compute_diagnostics(x, DiagnosticConfig(40, 20_000, 8))
    assert result["sample_positions"] != other["sample_positions"]


def test_budget_skip_and_degenerate_data_are_explicit():
    x = np.zeros((5, 3))
    assert compute_diagnostics(x, DiagnosticConfig(max_working_bytes=1))["status"] == "skipped"
    result = compute_diagnostics(x, DiagnosticConfig(neighbors=(1, 2)))
    assert result["duplicates"]["extra_identical_rows"] == 4
    assert result["distances"]["coefficient_of_variation"] is None
    assert result["feature_variance"]["largest_feature_share"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("kwargs", [{"max_samples": True}, {"max_working_bytes": 0}, {"seed": -1},
                                    {"neighbors": (0,)}, {"neighbors": (2, 2)}, {"neighbors": (101,)}])
def test_bad_config(kwargs):
    with pytest.raises(InputError):
        DiagnosticConfig(**kwargs)


def test_nonfinite_and_overflow():
    with pytest.raises(InputError, match="nonfinite|infinite"):
        compute_diagnostics(np.array([[0., 1], [np.nan, 2]]))
    result = compute_diagnostics(np.array([[1e200, 0], [-1e200, 0]]))
    assert result["status"] == "partial"
    assert result["distances"]["status"] == "skipped"
    json.dumps(result, allow_nan=False)


def test_artifact_loader_and_planner_integration(tmp_path):
    folder = tmp_path / "run/preprocessed"
    folder.mkdir(parents=True)
    x = np.arange(60.).reshape(12, 5)
    np.save(folder / "measurements.npy", x)
    data = profile()
    result = diagnostics_from_run(tmp_path / "run", data, DiagnosticConfig(neighbors=(2, 5)))
    assert len(result["source_sha256"]) == 64
    evidence = planning_evidence(data, diagnostics=result)
    planner = Fake([ready(evidence)])
    outcome = run_reduction_planner(data, tmp_path / "selection", diagnostics=result, planner=planner)
    assert outcome["status"] == "selection_complete"
    assert '"components"' in planner.prompts[0]
    assert "sample_positions" not in planner.prompts[0]
    assert (tmp_path / "selection/diagnostics.json").exists()
    x[0, 0] = np.inf
    np.save(folder / "measurements.npy", x)
    with pytest.raises(InputError, match="nonfinite"):
        diagnostics_from_run(tmp_path / "run", data)


def test_mismatched_diagnostics_rejected():
    with pytest.raises(InputError, match="dimensions"):
        planning_evidence(profile(), diagnostics={"input_shape": [3, 3]})
