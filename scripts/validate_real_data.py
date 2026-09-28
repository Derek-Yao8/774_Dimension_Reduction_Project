"""Download official backup datasets and validate ingestion, not embeddings."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

import numpy as np
from scipy import sparse

from dimred_agent import load_dataset, profile_dataset
from dimred_agent.profile import render_summary

PATH_URL = "https://zenodo.org/records/10519652/files/pathmnist.npz?download=1"
PBMC_URL = "https://cf.10xgenomics.com/samples/cell-exp/1.1.0/pbmc3k/pbmc3k_filtered_gene_bc_matrices.tar.gz"


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def download(url, path):
    if not path.exists():
        print(f"Downloading {path.name}", flush=True)
        partial = path.with_suffix(path.suffix + ".partial")
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=120) as source, partial.open("wb") as target:
            shutil.copyfileobj(source, target)
        partial.replace(path)
    return {"url": url, "file": str(path), "bytes": path.stat().st_size, "sha256": digest(path)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("outputs/real_data_validation"))
    args = parser.parse_args()
    require(not args.out.exists(), "Choose a new output directory.")
    args.data.mkdir(parents=True, exist_ok=True)
    path_file, pbmc_file = args.data / "pathmnist.npz", args.data / "pbmc3k.tar.gz"
    sources = [download(PATH_URL, path_file), download(PBMC_URL, pbmc_file)]
    require(digest(path_file, "md5") == "a8b06965200029087d5bd730944a56c1", "PathMNIST official MD5 mismatch.")
    sources[0]["official_md5_verified"] = True
    sources[1]["checksum_note"] = "SHA-256 recorded locally; no publisher checksum supplied here."
    # Extract only the three named data files; never execute or extract archive links.
    folder = args.data / "pbmc3k" / "filtered_gene_bc_matrices" / "hg19"
    folder.mkdir(parents=True, exist_ok=True)
    with tarfile.open(pbmc_file) as archive:
        for name in ("matrix.mtx", "genes.tsv", "barcodes.tsv"):
            member = archive.getmember(f"filtered_gene_bc_matrices/hg19/{name}")
            require(member.isfile(), f"Expected regular archive file: {name}")
            with archive.extractfile(member) as source, (folder / name).open("wb") as target:
                shutil.copyfileobj(source, target)
    args.out.mkdir(parents=True)
    results = []

    def save(name, dataset, checks):
        print(f"Profiling {name}: {dataset.X.shape}", flush=True)
        profile = profile_dataset(dataset)
        require(profile["missing_values"] == 0 and profile["infinite_values"] == 0, "Unexpected missing/nonfinite values.")
        destination = args.out / name
        destination.mkdir()
        (destination / "profile.json").write_text(json.dumps(profile, indent=2, allow_nan=False), encoding="utf-8")
        (destination / "profile.md").write_text(render_summary(profile), encoding="utf-8")
        results.append({"name": name, "shape": list(dataset.X.shape), "storage": profile["storage"],
                        "missing_values": profile["missing_values"], "numeric_zero_fraction": profile["numeric_zero_fraction"],
                        "constant_features": len(profile["constant_feature_positions"]),
                        "labels": profile["labels"], "checks_passed": checks})

    for split, count in (("train", 89996), ("val", 10004), ("test", 7180)):
        data = load_dataset(path_file, split=split)
        require(data.X.shape == (count, 2352), "PathMNIST shape mismatch.")
        require(data.provenance["image_shape"] == [28, 28, 3], "Unexpected image shape.")
        require(data.X.dtype == np.uint8, "Expected uint8 pixels.")
        require(set(data.labels.iloc[:, 0]) == set(range(9)), "Expected nine label codes.")
        with np.load(path_file, allow_pickle=False) as original:
            require(np.array_equal(data.labels.to_numpy(), original[f"{split}_labels"]), "Label alignment mismatch.")
            require(np.array_equal(data.X.reshape(count, 28, 28, 3), original[f"{split}_images"]), "Image flattening changed values/order.")
        save(f"pathmnist_{split}", data, ["official dimensions", "nine classes", "exact pixel roundtrip", "exact label alignment", "no missing/infinite values"])

    data = load_dataset(folder)
    require(data.X.shape == (2700, 32738), "PBMC shape mismatch.")
    require(sparse.issparse(data.X), "PBMC must remain sparse.")
    require(data.labels is None, "Raw PBMC must not invent labels.")
    require(np.all(data.X.data >= 0) and np.all(data.X.data == np.floor(data.X.data)), "Expected nonnegative counts.")
    # Independent text-level check of every MTX coordinate and its transpose.
    with (folder / "matrix.mtx").open() as stream:
        line = next(stream)
        while line.startswith("%"):
            line = next(stream)
        genes, cells, nnz = map(int, line.split())
        coordinates = np.loadtxt(stream, dtype=np.int64)
    require((cells, genes) == data.X.shape and nnz == data.X.nnz, "MTX shape/nnz mismatch.")
    observed = np.asarray(data.X[coordinates[:, 1] - 1, coordinates[:, 0] - 1]).ravel()
    require(np.array_equal(observed, coordinates[:, 2]), "MTX transposition/value mismatch.")
    save("pbmc3k", data, ["official dimensions", "sparse storage", "all original MTX coordinates and values", "nonnegative integer counts", "no invented labels", "no missing/infinite values"])
    (args.out / "validation.json").write_text(json.dumps({"status": "passed", "scope": "ingestion only; no preprocessing or dimension reduction", "sources": sources, "datasets": results}, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
