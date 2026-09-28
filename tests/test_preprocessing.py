import json
import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from dimred_agent import Dataset, InputError
from dimred_agent.preprocessing import PreprocessingPlan as Plan, preprocess


def data(x):
    return Dataset(x, pd.DataFrame(index=[f"row{i}" for i in range(x.shape[0])]),
                   pd.DataFrame(index=range(x.shape[1])),
                   pd.DataFrame({"label": range(x.shape[0])}, index=[f"row{i}" for i in range(x.shape[0])]))


def test_impute_scale_preserves_original_and_alignment(tmp_path):
    original = np.array([[1., np.nan, 5], [3, 2, 5], [5, 4, 5]])
    source = data(original.copy())
    result = preprocess(source, Plan("Test numeric EDA", missing="mean", remove_constants=True, scale="standard", center=True))
    assert result.dataset.X.shape == (3, 2)
    np.testing.assert_allclose(result.dataset.X.mean(0), 0, atol=1e-12)
    np.testing.assert_allclose(result.dataset.X.std(0), 1)
    np.testing.assert_array_equal(source.X, original)
    assert result.dataset.labels.equals(source.labels)
    assert result.dataset.obs.equals(source.obs)
    result.save(tmp_path / "result")
    audit = json.loads((tmp_path / "result/preprocessing.json").read_text())
    assert audit["imputation"][0]["fill"] == 3
    np.testing.assert_array_equal(np.load(tmp_path / "result/measurements.npy"), result.dataset.X)


def test_sparse_counts_match_dense_and_preserve_input():
    x = np.array([[0., 2, 2], [3, 0, 1], [1, 5, 0]])
    plan = Plan("Confirmed RNA counts", count_data_confirmed=True, normalize_total=100, log1p=True, scale="maxabs")
    source = data(sparse.csr_matrix(x))
    result = preprocess(source, plan)
    assert sparse.issparse(result.dataset.X)
    np.testing.assert_allclose(result.dataset.X.toarray(), preprocess(data(x), plan).dataset.X)
    np.testing.assert_array_equal(source.X.toarray(), x)


def test_sparse_missing_mean_includes_implicit_zeros():
    x = sparse.csr_matrix([[0., 1], [np.nan, 2], [6, 3]])
    result = preprocess(data(x), Plan("Impute", missing="mean"))
    assert result.dataset.X[1, 0] == 3


def test_encoding_and_feature_lineage():
    source = data(pd.DataFrame({"value": [1., 2, 3], "kind": ["a", "b", "a"]}))
    result = preprocess(source, Plan("Encode observed categories", categorical="onehot"))
    np.testing.assert_array_equal(result.dataset.X.toarray(), [[1, 1, 0], [2, 0, 1], [3, 1, 0]])
    assert result.dataset.var.source_position.tolist() == [0, 1, 1]
    assert result.dataset.var.category.iloc[1:].tolist() == ["a", "b"]


@pytest.mark.parametrize("spec", [{"reason": "x", "remove_constants": "yes"}, {"reason": "x", "unknown": 1},
                                  {"reason": "x", "normalize_total": 100}, {"reason": ""},
                                  {"reason": "x", "drop_features": [True]}])
def test_reject_invalid_plans(spec):
    with pytest.raises(InputError):
        Plan.from_dict(spec)


def test_invalid_data_and_resources():
    for x, plan in [
        (np.array([[1., np.inf], [2, 3]]), Plan("Fail on infinity")),
        (np.ones((3, 2)), Plan("Constants", remove_constants=True)),
        (np.ones((3, 2)), Plan("Budget", max_dense_bytes=1)),
        (sparse.eye(3), Plan("No dense conversion", scale="standard", center=True)),
        (np.zeros((3, 2)), Plan("No empty libraries", count_data_confirmed=True, normalize_total=100)),
        (np.array([[-1., 2], [2, 3]]), Plan("Nonnegative log", log1p=True)),
    ]:
        with pytest.raises(InputError):
            preprocess(data(x), plan)


def test_explicit_ambiguity_resolution_and_all_missing():
    source = data(np.array([[1., np.nan], [2, np.nan]]))
    source.ambiguities = ["Unknown meaning"]
    with pytest.raises(InputError, match="resolution"):
        preprocess(source, Plan("Drop empty", all_missing="drop"))
    result = preprocess(source, Plan("Drop empty", all_missing="drop", ambiguity_resolutions=["Confirmed numeric measurements"]))
    assert result.dataset.X.shape == (2, 1)
    assert source.ambiguities == ["Unknown meaning"]
