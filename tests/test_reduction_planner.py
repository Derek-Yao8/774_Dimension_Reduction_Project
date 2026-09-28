import json
import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from dimred_agent.data import Dataset, InputError
from dimred_agent.profile import profile_dataset
from dimred_agent.codex_planner import PlannerError
from dimred_agent.reduction_planner import (
    ResourceLimits, METHODS, planning_evidence, parameter_templates, validate_selection,
    run_reduction_planner, reduction_instructions,
)


def profile(is_sparse=False):
    x = np.arange(60, dtype=float).reshape(12, 5)
    return profile_dataset(Dataset(sparse.csr_matrix(x) if is_sparse else x,
                                   pd.DataFrame(index=range(12)), pd.DataFrame(index=range(5))))


def ready(evidence, method="pca"):
    return {"status": "ready", "explanation": "A preliminary choice using the available evidence.",
            "questions": [], "plan_json": json.dumps({
                "method": method, "n_components": evidence["dimensions"],
                "parameters": parameter_templates(evidence)[method],
                "reason": "Justified by the stated objective; parameters are initial choices.",
                "scientific_reason": "Initial suitability, with geometry uncertain.",
                "feasibility_reason": "Passes the configured screens, not guaranteed runtime.",
                "alternatives": {m: {"scientific_reason": "Less aligned with the stated objective.",
                                     "feasibility_reason": "See recorded eligibility checks."} for m in evidence['eligibility'] if m != method},
                "limitations": ["Geometry has not been measured."]})}


class Fake:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def propose(self, prompt, directory):
        self.prompts.append(prompt)
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.parametrize("method", list(METHODS))
def test_all_method_contracts_and_dimension_override(method):
    evidence = planning_evidence(profile(), dimensions=3)
    assert validate_selection(ready(evidence, method), evidence)["n_components"] == 3


def test_legacy_catalog_and_tsne_dimension_gate():
    old = ['pca', 'mds', 'isomap', 'lle']
    evidence = planning_evidence(profile(), available_methods=old)
    assert list(evidence['eligibility']) == old
    validate_selection(ready(evidence), evidence)
    assert not planning_evidence(profile(), dimensions=4)['eligibility']['tsne']['eligible']


@pytest.mark.parametrize('method,field,value', [
    ('kernel_pca', 'gamma', 0), ('kernel_pca', 'gamma', True),
    ('diffusion_maps', 'epsilon', -1), ('diffusion_maps', 'alpha', 2),
    ('diffusion_maps', 'diffusion_time', 0), ('laplacian_eigenmaps', 'n_neighbors', 2),
    ('tsne', 'perplexity', 12), ('tsne', 'max_iter', 250),
    ('umap', 'n_neighbors', 12), ('umap', 'min_dist', 2), ('umap', 'n_epochs', 0)])
def test_new_parameter_guards(method, field, value):
    evidence = planning_evidence(profile())
    response = ready(evidence, method)
    plan = json.loads(response['plan_json'])
    plan['parameters'][field] = value
    response['plan_json'] = json.dumps(plan)
    with pytest.raises(InputError):
        validate_selection(response, evidence)


@pytest.mark.parametrize("field,value", [("n_components", 3), ("parameters", {"svd_solver": "auto"}),
                                        ("method", "umap"), ("alternatives", {}), ("limitations", [])])
def test_invalid_model_choices(field, value):
    evidence = planning_evidence(profile())
    response = ready(evidence)
    plan = json.loads(response["plan_json"])
    plan[field] = value
    response["plan_json"] = json.dumps(plan)
    with pytest.raises(InputError):
        validate_selection(response, evidence)


def test_sparse_compatibility_and_resource_gates():
    evidence = planning_evidence(profile(True))
    assert validate_selection(ready(evidence), evidence)["parameters"]["svd_solver"] == "arpack"
    with pytest.raises(InputError, match="eligibility"):
        validate_selection(ready(evidence, "lle"), evidence)
    large = profile()
    large["n_observations"] = 10004
    evidence = planning_evidence(large)
    assert evidence["eligibility"]["pca"]["eligible"]
    assert not any(evidence["eligibility"][m]["eligible"] for m in ("mds", "isomap", "lle"))


@pytest.mark.parametrize("field,value", [("missing_values", 1), ("infinite_values", 1),
                                        ("ambiguities", ["Unknown orientation"]),
                                        ("constant_feature_positions", list(range(5)))])
def test_unready_data_rejected(field, value):
    data = profile()
    data[field] = value
    with pytest.raises(InputError):
        planning_evidence(data)


def test_small_data_and_no_silent_dimension_change():
    data = profile()
    data["n_observations"] = 3
    evidence = planning_evidence(data)
    assert not evidence["eligibility"]["lle"]["eligible"]
    with pytest.raises(InputError, match="dimensions"):
        planning_evidence(data, 3)


def test_retry_is_not_fallback_and_no_embedding(tmp_path):
    data = profile()
    evidence = planning_evidence(data)
    bad = ready(evidence, "isomap")
    plan = json.loads(bad["plan_json"])
    plan["parameters"]["n_neighbors"] = 999
    bad["plan_json"] = json.dumps(plan)
    planner = Fake([bad, ready(evidence)])
    outcome = run_reduction_planner(data, tmp_path / "selection", planner=planner, max_attempts=2)
    assert outcome["status"] == "selection_complete"
    assert len(outcome["validation_history"]) == 1
    assert "Invalid neighborhood" in planner.prompts[1]
    assert outcome["reduction_executed"] is False
    assert outcome["fallback_occurred"] is False
    assert outcome["backend"] == "injected_planner"
    assert (tmp_path / "selection/selection.json").exists()


@pytest.mark.parametrize("response,status", [
    ({"status": "needs_clarification", "explanation": "Objective unclear", "questions": ["Which structure matters?"], "plan_json": ""}, "needs_clarification"),
    (PlannerError("Usage unavailable"), "planner_unavailable"),
])
def test_clarification_and_backend_fail_without_retry(tmp_path, response, status):
    planner = Fake([response])
    outcome = run_reduction_planner(profile(), tmp_path / "selection", planner=planner)
    assert outcome["status"] == status
    assert len(planner.prompts) == 1
    assert not outcome["fallback_occurred"]


def test_labels_paths_and_names_excluded():
    data = profile()
    data["labels"] = {"secret_label": "secret_value"}
    data["provenance"]["sources"] = [{"path": "secret_path"}]
    data["features"][0]["name"] = "secret_feature"
    prompt = reduction_instructions(planning_evidence(data), "", "")
    assert "secret_" not in prompt


def test_no_eligible_method_makes_no_model_call(tmp_path):
    data = profile()
    data["n_observations"] = 100_000_000
    planner = Fake([])
    outcome = run_reduction_planner(data, tmp_path / "selection", planner=planner)
    assert outcome["status"] == "no_eligible_method"
    assert planner.prompts == []


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1])
def test_invalid_numeric_parameters(value):
    evidence = planning_evidence(profile())
    response = ready(evidence, "lle")
    plan = json.loads(response["plan_json"])
    plan["parameters"]["reg"] = value
    response["plan_json"] = json.dumps(plan)
    with pytest.raises(InputError):
        validate_selection(response, evidence)


def test_configurable_resources():
    data = profile()
    data["n_observations"] = 6000
    assert not planning_evidence(data)["eligibility"]["mds"]["eligible"]
    relaxed = planning_evidence(data, limits=ResourceLimits(3_000_000_000, 7000))
    assert relaxed["eligibility"]["mds"]["eligible"]
    tight = planning_evidence(data, limits=ResourceLimits(1, 7000))
    assert not tight["eligibility"]["pca"]["eligible"]


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_bad_budget(value):
    with pytest.raises(InputError):
        ResourceLimits(max_working_bytes=value)


def test_preview_and_single_call_budget(tmp_path):
    data = profile()
    planner = Fake([])
    outcome = run_reduction_planner(data, tmp_path / "preview", planner=planner, preview=True)
    assert outcome["status"] == "preview_only"
    assert outcome["planner_calls_attempted"] == 0
    assert planner.prompts == []
    bad = ready(planning_evidence(data))
    plan = json.loads(bad["plan_json"])
    del plan["scientific_reason"]
    bad["plan_json"] = json.dumps(plan)
    planner = Fake([bad])
    outcome = run_reduction_planner(data, tmp_path / "one", planner=planner)
    assert outcome["status"] == "validation_failed"
    assert outcome["planner_calls_attempted"] == 1


def test_alternatives_cannot_merge_science_with_feasibility():
    evidence = planning_evidence(profile())
    response = ready(evidence)
    plan = json.loads(response["plan_json"])
    plan["alternatives"]["mds"] = "Too expensive so scientifically wrong"
    response["plan_json"] = json.dumps(plan)
    with pytest.raises(InputError, match="separate"):
        validate_selection(response, evidence)
