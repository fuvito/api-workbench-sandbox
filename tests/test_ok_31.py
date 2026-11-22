"""The OpenAPI 3.1 variant of the ok API: served, a faithful subset, really 3.1."""

from pathlib import Path

import yaml

from app.config import Settings
from tests.conftest import make_client

ROOT = Path(__file__).parent.parent
METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


def load(name):
    return yaml.safe_load((ROOT / "specs" / name).read_text(encoding="utf-8"))


async def test_the_variant_is_served_with_the_rewritten_server_url(client):
    r = await client.get("/ok/openapi-3.1.yaml")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/yaml")
    doc = yaml.safe_load(r.text)
    assert doc["openapi"] == "3.1.0"
    assert doc["servers"] == [{"url": "http://testserver/ok"}]
    # nothing but the server URL differs from the checked-in file
    doc["servers"] = load("ok-3.1.yaml")["servers"]
    assert doc == load("ok-3.1.yaml")


async def test_public_base_url_applies_to_the_variant_too():
    client, _ = make_client(Settings(public_base_url="https://sandbox.example.run.app"))
    async with client:
        doc = yaml.safe_load((await client.get("/ok/openapi-3.1.yaml")).text)
    assert doc["servers"][0]["url"] == "https://sandbox.example.run.app/ok"


async def test_the_main_document_is_unchanged_and_other_families_have_no_variant(client):
    assert yaml.safe_load((await client.get("/ok/openapi.yaml")).text)["openapi"] == "3.0.3"
    for family in ("contract-fail", "conform-fail"):
        assert (await client.get(f"/{family}/openapi-3.1.yaml")).status_code == 404


def test_every_operation_of_the_variant_exists_in_the_main_spec_with_the_same_id():
    main, variant = load("ok.yaml"), load("ok-3.1.yaml")
    assert variant["paths"]
    for path, item in variant["paths"].items():
        for method in (m for m in item if m in METHODS):
            assert method in main["paths"][path], (method, path)
            assert item[method]["operationId"] == main["paths"][path][method]["operationId"]


def schemas(node):
    """Every schema object in the document."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "schema" or key == "items" or key == "additionalProperties":
                if isinstance(value, dict):
                    yield value
            if key == "properties" and isinstance(value, dict):
                yield from (v for v in value.values() if isinstance(v, dict))
            yield from schemas(value)
    elif isinstance(node, list):
        for value in node:
            yield from schemas(value)


def test_the_variant_uses_the_3_1_dialect_and_not_the_3_0_one():
    variant = load("ok-3.1.yaml")
    found = list(schemas(variant))
    assert not [s for s in found if "nullable" in s]  # 3.0 only
    assert not [s for s in found if "example" in s]  # a schema's `example` is the 3.0 spelling
    assert any(isinstance(s.get("type"), list) and "null" in s["type"] for s in found)  # type arrays
    assert any("const" in s for s in found)
    assert any(isinstance(s.get("examples"), list) for s in found)
    assert variant["info"]["license"]["identifier"] == "MIT"


async def test_a_nullable_field_really_accepts_null_on_the_server(client):
    # the variant says birthDate may be null; the server must agree
    r = await client.post("/ok/customers", json={"email": "n@example.com", "name": "N", "birthDate": None})
    assert r.status_code == 201, r.text
    assert r.json().get("birthDate") is None
