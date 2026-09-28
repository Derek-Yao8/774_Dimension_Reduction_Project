import json
import subprocess
import numpy as np
import pandas as pd
import pytest
from dimred_agent import Dataset, InputError
from dimred_agent.codex_planner import (CodexPlanner, PlannerError, codex_environment,
                                       run_planner, validate_response, compact_profile)
from dimred_agent.profile import profile_dataset


def response(plan):
    return {"status": "ready", "explanation": "Explain measured data", "questions": [], "plan_json": json.dumps(plan)}


class FakePlanner:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def propose(self, prompt, directory):
        self.prompts.append(prompt)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return value


def dataset():
    return Dataset(np.array([[1., 7], [2, 7], [3, 7]]), pd.DataFrame(index=range(3)), pd.DataFrame(index=range(2)))


def test_repair_then_execute(tmp_path):
    planner = FakePlanner([response({"reason": "Invalid", "scale": "made_up"}),
                           response({"reason": "Remove measured constant", "remove_constants": True})])
    outcome = run_planner(dataset(), tmp_path / "run", planner=planner)
    assert outcome["status"] == "preprocessing_complete"
    assert outcome["output_shape"] == [3, 1]
    assert len(outcome["validation_history"]) == 1
    assert "Invalid scale" in planner.prompts[1]


def test_clarification_and_failure_do_not_execute(tmp_path):
    for i, value in enumerate([
        {"status": "needs_clarification", "explanation": "Unknown units", "questions": ["What are the units?"], "plan_json": ""},
        PlannerError("Usage unavailable")]):
        planner = FakePlanner([value])
        outcome = run_planner(dataset(), tmp_path / str(i), planner=planner)
        assert outcome["status"] in ("needs_clarification", "planner_unavailable")
        assert not (tmp_path / str(i) / "preprocessed").exists()
        assert len(planner.prompts) == 1


def test_no_api_environment_or_auth(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("CODEX_API_KEY", "test-secret")
    assert "OPENAI_API_KEY" not in codex_environment()
    assert "CODEX_API_KEY" not in codex_environment()
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "Logged in using an API key")
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(PlannerError, match="ChatGPT"):
        CodexPlanner(executable="codex").check_auth()
    assert 'forced_login_method="chatgpt"' in calls[0]


def test_model_cannot_raise_resource_limits():
    with pytest.raises(InputError, match="resource"):
        validate_response(response({"reason": "More memory", "max_dense_bytes": 999999999999}))


def test_profile_does_not_send_paths_or_full_features():
    profile = profile_dataset(dataset())
    profile["provenance"]["sources"] = [{"path": "private-path"}]
    compact = compact_profile(profile)
    assert "private-path" not in json.dumps(compact)
