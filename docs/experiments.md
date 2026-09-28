# Submitted experiments

## Inputs and scope

PathMNIST uses the MedMNIST validation partition: 10,004 RGB images flattened to
2,352 numeric features, with labels reserved for display. PBMC uses the 10x PBMC3K
filtered count matrix: all 2,700 cells and initially 32,738 genes, without cell-type
labels. Neither experiment creates a new train/test split; metrics describe
in-sample geometry. Both use fixed 2D and the default suitability/resource policy.

Acquire the [PathMNIST archive](https://zenodo.org/records/10519652/files/pathmnist.npz?download=1)
and [PBMC archive](https://cf.10xgenomics.com/samples/cell-exp/1.1.0/pbmc3k/pbmc3k_filtered_gene_bc_matrices.tar.gz).
The included acquisition utility downloads these and checks ingestion:

```sh
python scripts/validate_real_data.py --data data --out outputs/input_validation
```

## Fresh-run commands

Create `settings.json` containing `{"report": {"timeout": 300}}`, then run:

```sh
python scripts/run_agent.py data/pathmnist.npz --split val --config settings.json --report-name generated_report_1 --out outputs/pathmnist --context "PathMNIST validation subset. RGB pixel intensities in common 0-255 units, not counts. Labels are metadata. No new train/test split."
python scripts/run_agent.py data/pbmc3k/filtered_gene_bc_matrices/hg19 --config settings.json --report-name generated_report_2 --out outputs/pbmc --context "Raw nonnegative integer UMI counts; cells by genes. Retain all cells. Do not perform additional cell-quality filtering or variable-gene selection. No cell-type labels or new train/test split."
```

These commands implement the current scientific scope. New model decisions and
wording may differ from the submitted results; this is fresh analysis, not exact
numerical replay. Recorded settings and decisions remain in each report's evidence.

## Findings and limitations

PathMNIST preprocessing preserves original pixel intensities. PCA is the only
eligible method under the 5,000-observation non-PCA gate; it retains 56.7966% of
variance. PBMC applies total-count normalization to 10,000, log1p and constant
removal, leaving 16,634 genes. PCA, MDS, t-SNE and UMAP complete and are evaluated.
PBMC PCA retains 6.1279% of variance; MDS reaches its 300-iteration cap and t-SNE
records its iteration-limit flag. Execution success does not prove convergence.

All five embeddings are evaluated. Common scores use 512 PathMNIST observations
and the same 128 PBMC observations across methods. Plots show 10,000 PathMNIST
images and all 2,700 PBMC cells. Reports include direct model inspection of these
plots, their metric context and limitations. No methods are ranked.

PBMC retains all cells without an additional quality assessment and all
nonconstant genes without a variable-gene ranking or cutoff. This preserves a
broad feature representation and avoids another feature-selection rule. It does
not establish that every cell is high quality or every gene informative; noisy
features may influence geometry and increase computation. Constant removal is
distinct from selecting a subset of variable genes.

The report folders contain scientific evidence for these results, including
parameters, source identifiers, warnings and image hashes. They omit development
logs and report-generation transcripts. Original scientific context is preserved
as evidence; wording about deferral in that context records the instructions
received during the fit, not an unresolved current submission decision.
