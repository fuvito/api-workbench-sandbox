"""The adversarial group (/conform-fail/hostile/*) and the generated documents of the fuzz and scale cases."""

import json
import sys
from pathlib import Path

import httpx
import pytest
import yaml

from app.conform_fail import hostile

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import make_specs  # noqa: E402

H = "/conform-fail/hostile"


def spec():
    return yaml.safe_load((ROOT / "specs" / "conform-fail.yaml").read_text(encoding="utf-8"))


def hostile_paths():
    return {p: item for p, item in spec()["paths"].items() if p.startswith("/hostile/")}


def test_every_case_is_in_the_spec_and_every_spec_path_is_a_case():
    names = {p.removeprefix("/hostile/") for p in hostile_paths()}
    served = set(hostile.BODIES) | {"gzip", "gzip-lie", "duplicate-headers", "big-header", "chunked-stream"}
    assert names == served and len(names) == 20


@pytest.mark.parametrize("name", sorted(hostile.BODIES))
async def test_a_body_is_served_byte_for_byte(client, name):
    r = await client.get(f"{H}/{name}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    assert r.content == hostile.BODIES[name]


def test_the_valid_bodies_are_valid_json_and_the_malformed_ones_are_not():
    valid = ["deep-nesting", "wide-object", "unicode", "integer-as-float", "integer-exponent", "big-integer", "negative-zero",
             "float-overflow", "lone-surrogate", "duplicate-keys"]
    for name in valid:
        json.loads(hostile.BODIES[name].decode("utf-8", "surrogatepass"))  # strict enough for these
    for name in ("invalid-utf8", "raw-newline-in-string", "nan-literal", "trailing-garbage"):
        with pytest.raises((ValueError, UnicodeDecodeError)):
            json.loads(hostile.BODIES[name].decode("utf-8"), parse_constant=_reject)
    assert hostile.BODIES["bom"].startswith(b"\xef\xbb\xbf")


def _reject(token):
    raise ValueError(token)


def test_the_documented_sizes():
    assert hostile.BODIES["deep-nesting"].count(b"[") == hostile.DEPTH
    assert json.loads(hostile.BODIES["wide-object"]).keys() >= {"k0", f"k{hostile.WIDTH - 1}"}
    assert len(json.loads(hostile.BODIES["wide-object"])) == hostile.WIDTH + 1


async def test_gzip_is_a_real_gzip_body_and_the_lie_is_not(client):
    # httpx decodes Content-Encoding: gzip itself: the real body arrives as JSON, the lie cannot be decoded.
    real = await client.get(f"{H}/gzip")
    assert real.headers["content-encoding"] == "gzip" and json.loads(real.content) == {"id": 1}
    with pytest.raises(httpx.DecodingError):
        await client.get(f"{H}/gzip-lie")


async def test_duplicate_headers_are_sent_twice(client):
    r = await client.get(f"{H}/duplicate-headers")
    assert r.headers.get_list("x-dup") == ["one", "two"]
    assert r.headers.get_list("set-cookie") == ["a=1; Path=/", "b=2; Path=/"]


async def test_the_big_header_and_the_chunked_stream(client):
    big = await client.get(f"{H}/big-header")
    assert len(big.headers["x-big"]) == hostile.BIG_HEADER
    chunked = await client.get(f"{H}/chunked-stream")
    assert "content-length" not in chunked.headers and json.loads(chunked.content) == {"id": 1, "text": "chunked"}


async def test_the_hostile_group_has_no_state_to_reset(client):
    before = (await client.get(f"{H}/unicode")).content
    assert (await client.post("/conform-fail/__admin/reset")).status_code == 204
    assert (await client.get(f"{H}/unicode")).content == before


# ---- scripts/make_specs.py ----


def count_operations(doc):
    return sum(1 for item in doc["paths"].values() for key in item if key != "parameters")


def test_the_big_spec_has_the_requested_number_of_operations_and_unique_ids():
    doc = make_specs.big_spec(500)
    assert count_operations(doc) == 500
    ids = [op["operationId"] for item in doc["paths"].values() for key, op in item.items() if key != "parameters"]
    assert len(set(ids)) == 500


@pytest.mark.parametrize("seed", range(1, 25))
def test_a_random_spec_is_deterministic_and_well_formed(seed):
    doc = make_specs.random_spec(seed)
    assert make_specs.dump(doc) == make_specs.dump(make_specs.random_spec(seed))
    assert doc["openapi"] == "3.0.3" and doc["paths"]
    ids = [op["operationId"] for item in doc["paths"].values() for key, op in item.items() if key != "parameters"]
    assert len(ids) == len(set(ids)) >= 1
    for item in doc["paths"].values():
        for key, op in item.items():
            if key == "parameters":
                continue
            assert op["responses"], (seed, key)
    json.loads(make_specs.dump(doc))  # valid JSON, which is also valid YAML


def test_different_seeds_make_different_documents():
    assert len({make_specs.dump(make_specs.random_spec(s)) for s in range(1, 20)}) == 19
