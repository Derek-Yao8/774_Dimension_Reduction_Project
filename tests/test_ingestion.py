import json

import anndata
import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from scipy.io import mmwrite

from dimred_agent import Dataset, InputError, load_dataset, profile_dataset
from dimred_agent.cli import main


def test_csv_labels_ids_and_mixed_missing(tmp_path):
    source = tmp_path / "table.csv"
    source.write_text("sample,x,constant,category,label\na,0,2,A,yes\nb,,2,B,no\nc,4,2,,yes\n")
    with pytest.raises(InputError, match="orientation"):
        load_dataset(source)
    data = load_dataset(source, orientation="rows", label_column="label", id_column="sample")
    result = profile_dataset(data)
    assert data.X.shape == (3, 3)
    assert list(data.labels.index) == ["a", "b", "c"]
    assert "label" not in data.X
    assert result["missing_values"] == 2
    assert result["numeric_zero_fraction"] == pytest.approx(1 / 5)
    assert result["constant_feature_positions"] == [1]
    assert result["feature_types"]["categorical_or_text"] == 1
    json.dumps(result, allow_nan=False)


def test_medmnist_preserves_split_pixels_and_labels(tmp_path):
    source = tmp_path / "images.npz"
    images = np.arange(24, dtype=np.uint8).reshape(2, 2, 2, 3)
    np.savez(source, train_images=images, train_labels=[[2], [1]], test_images=images, test_labels=[[0], [0]])
    with pytest.raises(InputError, match="split"):
        load_dataset(source)
    data = load_dataset(source, split="train")
    np.testing.assert_array_equal(data.X[1], images[1].reshape(-1))
    assert data.labels.iloc[:, 0].tolist() == [2, 1]
    assert data.provenance["image_shape"] == [2, 2, 3]
    assert data.X.dtype == np.uint8


def test_tenx_transposition_and_sparse_profile(tmp_path, monkeypatch):
    source = tmp_path / "tenx"
    source.mkdir()
    mmwrite(source / "matrix.mtx", sparse.coo_matrix([[0, 2, 0], [1, 0, 3]]))
    (source / "genes.tsv").write_text("g1\tGeneA\ng2\tGeneB\n")
    (source / "barcodes.tsv").write_text("cellA\ncellB\ncellC\n")
    data = load_dataset(source)
    assert sparse.issparse(data.X)
    assert data.X.shape == (3, 2)
    assert list(data.obs.index) == ["cellA", "cellB", "cellC"]
    assert data.X[1, 0] == 2
    def forbid_dense(*args, **kwargs):
        raise AssertionError("Sparse profiling must not densify")
    monkeypatch.setattr(sparse.csr_matrix, "toarray", forbid_dense)
    monkeypatch.setattr(sparse.csc_matrix, "toarray", forbid_dense)
    result = profile_dataset(data)
    assert result["numeric_zero_fraction"] == .5
    assert result["missing_values"] == 0
    assert len(result["provenance"]["sources"]) == 3


def test_h5ad_keeps_metadata_outside_measurements(tmp_path):
    source = tmp_path / "cells.h5ad"
    ad = anndata.AnnData(sparse.csr_matrix([[0., 2], [1, 0]]),
                        obs=pd.DataFrame({"cell_type": ["A", "B"]}, index=["a", "b"]),
                        var=pd.DataFrame(index=["g1", "g2"]))
    ad.write_h5ad(source)
    data = load_dataset(source, label_column="cell_type")
    assert data.X.shape == (2, 2)
    assert data.labels.iloc[:, 0].tolist() == ["A", "B"]
    assert profile_dataset(data)["requires_clarification"]


def test_sparse_and_dense_agree_with_nan_inf_and_constant():
    array = np.array([[0., np.nan, 3], [0, np.inf, 3], [0, 0, 3]])
    obs, var = pd.DataFrame(index=range(3)), pd.DataFrame(index=range(3))
    a = profile_dataset(Dataset(array, obs, var))
    b = profile_dataset(Dataset(sparse.csr_matrix(array), obs, var))
    for key in ("features", "missing_values", "infinite_values", "numeric_zero_fraction", "constant_feature_positions"):
        assert a[key] == b[key]
    json.dumps(b, allow_nan=False)


def test_cli_success_and_failure_artifacts(tmp_path):
    source = tmp_path / "table.csv"
    source.write_text("x,y\n0,1\n2,3\n4,5\n")
    assert main([str(source), "--out", str(tmp_path / "bad")]) == 2
    assert (tmp_path / "bad" / "validation_error.json").exists()
    assert main([str(source), "--orientation", "rows", "--out", str(tmp_path / "good")]) == 0
    result = json.loads((tmp_path / "good" / "profile.json").read_text())
    assert result["n_features"] == 2
    assert (tmp_path / "good" / "profile.md").exists()
    with pytest.raises(SystemExit):
        main([str(source), "--orientation", "rows", "--out", str(tmp_path / "good")])


def test_candidate_columns_are_flagged_not_silently_removed(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("x,group\n1,A\n2,B\n")
    data = load_dataset(path, orientation="rows")
    assert data.X.shape[1] == 2
    assert data.labels is None
    assert profile_dataset(data)["requires_clarification"]


def test_columns_orientation(tmp_path):
    path = tmp_path / "data.tsv"
    path.write_text("gene\tcellA\tcellB\ng1\t1\t2\ng2\t3\t4\n")
    data = load_dataset(path, orientation="columns", id_column="gene")
    assert list(data.obs.index) == ["cellA", "cellB"]
    assert list(data.var.index) == ["g1", "g2"]
    assert data.X.iloc[1, 0] == 2


def test_malformed_inputs(tmp_path):
    path = tmp_path / "data.npz"
    np.savez(path, train_images=np.zeros((2, 2, 2)), train_labels=np.array([1]))
    with pytest.raises(InputError, match="Labels"):
        load_dataset(path)
    path = tmp_path / "empty.csv"
    path.write_text("x,y\n")
    with pytest.raises(InputError, match="nonempty"):
        load_dataset(path, orientation="rows")
