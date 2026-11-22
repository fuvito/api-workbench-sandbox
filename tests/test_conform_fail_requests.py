"""conform-fail slice 3: correct operations plus the deliberately wrong environments and fixtures."""

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
P = "/conform-fail"
ENV = ROOT / "clrsig" / "environments"


def env_values(name: str) -> dict[str, str]:
    data = yaml.safe_load((ENV / f"{name}.yaml").read_text(encoding="utf-8"))
    return {v["name"]: v["value"] for v in data["variables"]}


# ---- the operations are correct on their own ----


@pytest.mark.parametrize("item_id,expected", [("7", 7), ("0", 0), ("-5", -5), ("123456789", 123456789)])
async def test_param_type_accepts_every_integer(client, item_id, expected):
    r = await client.get(f"{P}/requests/param-type/{item_id}")
    assert r.status_code == 200 and r.json() == {"id": expected}


@pytest.mark.parametrize("item_id", ["abc", "1.5", "7a", "--1", "1" * 40, "%20", "0x10"])
async def test_param_type_rejects_non_integers_with_the_declared_400(client, item_id):
    r = await client.get(f"{P}/requests/param-type/{item_id}")
    assert r.status_code == 400 and set(r.json()) == {"code", "message"}


@pytest.mark.parametrize("amount", [0, 5, 19.99, 1e6])
async def test_body_value_accepts_non_negative_numbers(client, amount):
    r = await client.post(f"{P}/requests/body-value", json={"amount": amount})
    assert r.status_code == 201 and r.json() == {"id": 1}


@pytest.mark.parametrize(
    "body",
    [{}, {"amount": "19.99"}, {"amount": "cheap"}, {"amount": True}, {"amount": None}, {"amount": -1}, {"amount": [1]}, [], "x", None],
)
async def test_body_value_rejects_everything_else(client, body):
    r = await client.post(f"{P}/requests/body-value", json=body)
    assert r.status_code == 400 and set(r.json()) == {"code", "message"}


async def test_body_value_rejects_unreadable_json(client):
    r = await client.post(f"{P}/requests/body-value", content=b'{"amount": cheap}', headers={"Content-Type": "application/json"})
    assert r.status_code == 400  # what ClearSignal v0.7.1 sends for amount=cheap (F-017)


# ---- the right environment is right, the wrong ones are wrong in exactly one way ----


def test_the_right_environment_has_valid_values():
    values = env_values("conform-fail")
    assert values["itemId"].lstrip("-").isdigit() and float(values["amount"]) >= 0
    assert values["baseUrl"] == "http://localhost:8080/conform-fail"


def test_bad_values_environment_differs_only_in_the_two_values():
    right, wrong = env_values("conform-fail"), env_values("conform-fail-bad-values")
    assert wrong["itemId"] == "abc" and wrong["amount"] == "cheap"
    assert wrong["baseUrl"] == right["baseUrl"]
    assert not wrong["itemId"].isdigit()
    with pytest.raises(ValueError):
        float(wrong["amount"])


def test_missing_value_environment_defines_neither_value():
    values = env_values("conform-fail-missing-value")
    assert "itemId" not in values and "amount" not in values and "baseUrl" in values


def test_bad_function_environment_uses_a_function_clrsig_does_not_know():
    assert env_values("conform-fail-bad-function")["itemId"] == "{{$noSuchFunction}}"


def test_unset_variable_environment_refers_to_a_variable_nobody_sets(monkeypatch):
    value = env_values("conform-fail-unset-var")["token"]
    assert value == "${CLRSIG_UNSET_FIXTURE_VAR}"
    import os

    assert "CLRSIG_UNSET_FIXTURE_VAR" not in os.environ


def test_the_bad_function_scenario_has_one_broken_and_one_good_step():
    scenario = yaml.safe_load((ROOT / "clrsig" / "scenarios" / "conform-fail-bad-function.yaml").read_text(encoding="utf-8"))
    urls = [s["request"]["url"] for s in scenario["steps"]]
    assert "{{$noSuchFunction}}" in urls[0] and "{{$" not in urls[1]


# ---- the unreadable-spec fixtures really are unreadable in the intended way ----


def test_unreadable_yaml_does_not_parse():
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load((ROOT / "clrsig" / "fixtures" / "unreadable-yaml.yaml").read_text(encoding="utf-8"))


def test_not_openapi_parses_as_yaml_but_is_not_a_spec():
    data = yaml.safe_load((ROOT / "clrsig" / "fixtures" / "not-openapi.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict) and "openapi" not in data and "paths" not in data


def test_fixtures_are_not_served_as_specs(client):
    # They live under clrsig/fixtures and are never reachable through the server.
    assert not (ROOT / "specs" / "unreadable-yaml.yaml").exists()
    assert json.dumps(sorted(p.name for p in (ROOT / "specs").glob("*.yaml"))) == '["conform-fail.yaml", "contract-fail.yaml", "ok.yaml"]'


# ---- the spec describes these operations as correct ----


def test_the_spec_declares_the_operations_and_their_400s():
    spec = yaml.safe_load((ROOT / "specs" / "conform-fail.yaml").read_text(encoding="utf-8"))
    param = spec["paths"]["/requests/param-type/{itemId}"]["get"]
    assert param["parameters"][0]["schema"]["type"] == "integer" and "400" in param["responses"]
    body = spec["paths"]["/requests/body-value"]["post"]
    amount = spec["components"]["schemas"]["AmountBody"]["properties"]["amount"]
    assert amount["type"] == "number" and "example" not in amount  # so the value comes from the environment
    assert "201" in body["responses"] and "400" in body["responses"]
