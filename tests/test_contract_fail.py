"""The contract-fail family: every case exists in the spec and breaks exactly one thing."""

import json
import re
from pathlib import Path

import pytest
import yaml

from app import clock
from app.contract_fail import cases as cf

SPEC = yaml.safe_load((Path(__file__).parent.parent / "specs" / "contract-fail.yaml").read_text(encoding="utf-8"))
PREFIX = "/contract-fail/cases/"
WIDGET = {"id": 1, "name": "Alpha", "price": 9.99}


def spec_slugs() -> set[str]:
    return {p.removeprefix("/cases/") for p in SPEC["paths"] if p.startswith("/cases/")}


# ---- the spec and the handlers describe the same cases ----


def test_every_spec_case_has_a_handler_and_every_handler_a_spec_case():
    assert spec_slugs() == set(cf.CASES)


def test_undocumented_routes_are_really_absent_from_the_spec():
    assert set(cf.UNDOCUMENTED) == {"nc-undocumented-path"}
    assert not set(cf.UNDOCUMENTED) & spec_slugs()


@pytest.mark.parametrize("slug", sorted(cf.CASES))
def test_case_follows_the_naming_convention(slug):
    assert re.fullmatch(r"(control|resp|gap|nc)-[a-z0-9]+(-[a-z0-9]+)*", slug), slug


@pytest.mark.parametrize("slug", sorted(spec_slugs()))
def test_every_case_operation_is_documented_and_tagged(slug):
    operation = SPEC["paths"][f"/cases/{slug}"]["get"]
    assert operation["operationId"] and operation["summary"] and operation["description"]
    assert operation["tags"] in (["cases"], ["controls"])
    assert "200" in operation["responses"]


def test_the_spec_declares_the_correct_behavior_not_the_deviation():
    """Spot checks that the spec says what is right while the handler does what is wrong."""
    declared = SPEC["paths"]["/cases/resp-001-undeclared-status"]["get"]["responses"]
    assert set(declared) == {"200", "404"}  # 500 must stay undeclared
    assert "default" in SPEC["paths"]["/cases/resp-001b-default-response-ok"]["get"]["responses"]
    schemas = SPEC["components"]["schemas"]
    assert schemas["ClosedDoc"]["additionalProperties"] is False
    assert "additionalProperties" not in schemas["Widget"]  # open: an extra property is legal
    assert schemas["UserDoc"]["properties"]["password"]["writeOnly"] is True
    assert SPEC["components"]["headers"]["TotalCount"]["required"] is True


def test_the_served_spec_hides_nothing_and_has_no_admin_route(client):
    # Reset is deliberately not described by the public spec.
    assert not any("__admin" in p for p in SPEC["paths"])


# ---- helpers ----


async def get(client, slug):
    r = await client.get(PREFIX + slug)
    return r


def body(r):
    return json.loads(r.content)


# ---- controls: nothing wrong ----


async def test_control_ok_is_fully_correct(client):
    r = await get(client, "control-ok")
    assert r.status_code == 200 and r.headers["content-type"] == "application/json"
    assert body(r) == WIDGET


async def test_default_response_control_uses_an_undeclared_status(client):
    r = await get(client, "resp-001b-default-response-ok")
    assert r.status_code == 503
    assert "503" not in SPEC["paths"]["/cases/resp-001b-default-response-ok"]["get"]["responses"]


# ---- CS-RESP-001 .. 006: each deviates in one way only ----


async def test_001_undeclared_status(client):
    r = await get(client, "resp-001-undeclared-status")
    assert r.status_code == 500 and r.headers["content-type"] == "application/json"
    assert set(body(r)) == {"code", "message"}  # a perfectly good Error body


async def test_002_wrong_content_type_but_valid_json(client):
    r = await get(client, "resp-002-wrong-content-type")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    assert body(r) == WIDGET  # the body itself is correct


async def test_003_missing_required_header_with_a_correct_body(client):
    r = await get(client, "resp-003-missing-required-header")
    assert "x-total-count" not in r.headers
    assert r.headers["content-type"] == "application/json" and body(r) == WIDGET


async def test_004_wrong_header_type_with_a_correct_body(client):
    r = await get(client, "resp-004-wrong-header-type")
    assert r.headers["x-total-count"] == "many" and body(r) == WIDGET


async def test_005_missing_required_field_with_the_header_present(client):
    r = await get(client, "resp-005-missing-required-field")
    assert body(r) == {"name": "Alpha", "price": 9.99}


async def test_006_wrong_field_type(client):
    assert body(await get(client, "resp-006-wrong-field-type")) == {"id": 1, "name": "Alpha", "price": "9.99"}


async def test_006b_array_for_object(client):
    assert body(await get(client, "resp-006b-array-for-object")) == [WIDGET]


async def test_nested_wrong_type_is_deep_and_only_there(client):
    data = body(await get(client, "resp-nested-wrong-type"))
    assert data["lines"][0]["qty"] == "two"  # the one wrong value
    assert data["lines"][1]["qty"] == 1 and data["customer"]["address"]["city"] == "London"


# ---- CS-RESP-007 .. 012 ----


@pytest.mark.parametrize(
    "slug,expected",
    [
        ("resp-007-enum", {"status": "archived"}),
        ("resp-007b-minimum", {"quantity": -1}),
        ("resp-007f-maximum", {"percent": 101}),
        ("resp-007c-pattern", {"code": "abc-1"}),
        ("resp-007c-minlength", {"name": "ab"}),
        ("resp-007c-maxlength", {"name": "toolong"}),
        ("resp-007c-minitems", {"tags": []}),
        ("resp-007c-uniqueitems", {"tags": ["a", "a"]}),
        ("resp-007d-null-not-nullable", {"id": 1, "name": None}),
        ("resp-007e-bad-datetime", {"createdAt": "yesterday"}),
        ("resp-009-oneof-no-match", {"c": 1}),
        ("resp-poly-discriminator-wrong", {"type": "cat", "barks": True}),
        ("resp-010-extra-property-closed", {"id": 1, "extra": True}),
        ("resp-011-writeonly-leak", {"id": 1, "name": "Ada", "password": "hunter2"}),
        ("resp-007g-format-email-uuid", {"mail": "nope", "ref": "not-a-uuid"}),
        ("gap-format-uri", {"link": "not a uri"}),
    ],
)
async def test_body_deviations_are_exactly_these(client, slug, expected):
    r = await get(client, slug)
    assert r.status_code == 200 and r.headers["content-type"] == "application/json"
    assert body(r) == expected


async def test_008_invalid_json_keeps_the_json_content_type(client):
    r = await get(client, "resp-008-invalid-json")
    assert r.content == b"{not json" and r.headers["content-type"] == "application/json"
    with pytest.raises(json.JSONDecodeError):
        json.loads(r.content)


async def test_008b_empty_body(client):
    r = await get(client, "resp-008b-empty-body")
    assert r.status_code == 200 and r.content == b"" and r.headers["content-type"] == "application/json"


async def test_010b_open_schema_extra_property_is_legal(client):
    assert body(await get(client, "resp-010b-extra-property-open")) == {**WIDGET, "extra": True}


async def test_012_xml_is_valid_xml(client):
    import xml.etree.ElementTree as ET

    r = await get(client, "resp-012-xml-valid")
    assert r.headers["content-type"].startswith("application/xml")
    assert ET.fromstring(r.content).findtext("id") == "1"


async def test_multi_problem_has_both_problems(client):
    r = await get(client, "resp-multi-problem")
    assert "x-total-count" not in r.headers  # problem 1: header
    assert "id" not in body(r)  # problem 2: body


# ---- gaps and not-checked ----


async def test_gap_undeclared_header_adds_only_the_header(client):
    r = await get(client, "gap-undeclared-header")
    assert r.headers["x-debug"] == "1" and body(r) == WIDGET
    assert "x-debug" not in json.dumps(SPEC)


async def test_gap_slow_response_waits_five_seconds_scaled(client, monkeypatch):
    slept = []

    async def fake(seconds):
        slept.append(seconds)

    monkeypatch.setattr(clock, "sleep", fake)
    r = await get(client, "gap-slow-response")
    assert r.status_code == 200 and body(r) == WIDGET and slept == [5.0]


async def test_nc_cases(client):
    r = await get(client, "nc-002-no-content-declared")
    assert r.status_code == 200 and body(r) == WIDGET
    assert "content" not in SPEC["paths"]["/cases/nc-002-no-content-declared"]["get"]["responses"]["200"]

    r = await get(client, "nc-octet-stream")
    assert r.headers["content-type"] == "application/octet-stream" and r.content == bytes([0, 1, 2, 3])

    r = await get(client, "nc-no-content-type")
    assert "content-type" not in r.headers and body(r) == WIDGET


async def test_undocumented_path_exists_on_the_server(client):
    r = await get(client, "nc-undocumented-path")
    assert r.status_code == 200 and body(r) == WIDGET


async def test_unknown_case_is_404_and_only_get_is_allowed(client):
    assert (await client.get(PREFIX + "no-such-case")).status_code == 404
    assert (await client.post(PREFIX + "control-ok")).status_code == 405


async def test_cases_are_stateless_and_do_not_touch_other_families(client):
    before = (await client.get("/ok/__admin/state")).json()
    for slug in ("resp-001-undeclared-status", "resp-005-missing-required-field", "control-ok"):
        await get(client, slug)
    assert (await client.get("/ok/__admin/state")).json() == before
    assert (await client.post("/contract-fail/__admin/reset")).status_code == 204
