"""conform-fail slice 5: business rules the server breaks, drift, and the spec-change fixtures."""

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
import yaml

from app.config import Settings
from app.conform_fail import rules
from tests.conftest import make_client
from tests.test_ok_api import assert_error

ROOT = Path(__file__).parent.parent
P = "/conform-fail"


async def new_order(client, quantity):
    r = await client.post(f"{P}/rules/orders", json={"quantity": quantity})
    assert r.status_code == 201, r.text
    return r.json()


# ---- stock: no check against it ----


async def test_the_stock_starts_at_five_and_goes_negative(client):
    assert (await client.get(f"{P}/rules/stock")).json() == {"stock": 5}
    assert (await new_order(client, 3))["status"] == "pending"
    assert (await client.get(f"{P}/rules/stock")).json() == {"stock": 2}
    await new_order(client, 8)  # the broken rule: accepted although only 2 are left
    assert (await client.get(f"{P}/rules/stock")).json() == {"stock": -6}


@pytest.mark.parametrize("body", [{}, {"quantity": 0}, {"quantity": -1}, {"quantity": "3"}, {"quantity": True}, {"quantity": 1, "x": 1}, [], None])
async def test_order_input_is_still_validated(client, body):
    assert_error(await client.post(f"{P}/rules/orders", json=body), 400)
    assert (await client.get(f"{P}/rules/stock")).json() == {"stock": 5}  # a refused order takes no stock


# ---- order states: a shipped order can be cancelled ----


async def test_order_lifecycle_and_the_broken_cancel(client):
    order_id = (await new_order(client, 1))["id"]
    r = await client.post(f"{P}/rules/orders/{order_id}/ship")
    assert r.status_code == 200 and r.json()["status"] == "shipped"
    assert_error(await client.post(f"{P}/rules/orders/{order_id}/ship"), 409)  # this rule is kept
    r = await client.post(f"{P}/rules/orders/{order_id}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"  # the broken rule: a correct server says 409
    assert_error(await client.post(f"{P}/rules/orders/{order_id}/cancel"), 409)  # already cancelled
    assert_error(await client.post(f"{P}/rules/orders/{order_id}/ship"), 409)  # a cancelled order cannot ship


async def test_pending_orders_can_be_cancelled_and_unknown_ones_are_404(client):
    assert (await client.post(f"{P}/rules/orders/o-1/cancel")).json()["status"] == "cancelled"  # the seeded order
    assert_error(await client.post(f"{P}/rules/orders/nope/ship"), 404)
    assert_error(await client.post(f"{P}/rules/orders/nope/cancel"), 404)


# ---- unique email: never compared ----


async def test_a_duplicate_email_is_accepted(client):
    for _ in range(2):
        r = await client.post(f"{P}/rules/customers", json={"email": "ada@example.com"})
        assert r.status_code == 201 and r.json() == {"id": 1}
    state = (await client.get(f"{P}/__admin/state")).json()
    assert [c["email"] for c in state["rules_customers"].values()] == ["ada@example.com"] * 2


@pytest.mark.parametrize("body", [{}, {"email": "ab"}, {"email": 5}, {"email": "a@b.co", "x": 1}, []])
async def test_customer_input_is_still_validated(client, body):
    assert_error(await client.post(f"{P}/rules/customers", json=body), 400)


# ---- withdrawals: a refusal answered 200 ----


async def test_insufficient_funds_is_a_200_with_an_error_body(client):
    ok = await client.post(f"{P}/rules/withdrawals", json={"amount": 40})
    assert ok.json() == {"id": "w-1", "balance": 60}
    refused = await client.post(f"{P}/rules/withdrawals", json={"amount": 500})
    assert refused.status_code == 200 and refused.json() == {"error": "insufficient funds"}  # not the declared 422
    assert "id" not in refused.json()  # so the response does not match the 200 schema (CS-RESP-005)
    assert (await client.post(f"{P}/rules/withdrawals", json={"amount": 60})).json()["balance"] == 0  # balance untouched


@pytest.mark.parametrize("body", [{}, {"amount": 0}, {"amount": "5"}, {"amount": 1.5}, {"amount": 1, "x": 1}])
async def test_withdrawal_input_is_still_validated(client, body):
    assert_error(await client.post(f"{P}/rules/withdrawals", json=body), 400)


# ---- pagination: the first page makes another writer insert at the head ----


async def test_page_two_repeats_the_last_item_of_page_one(client):
    page1 = (await client.get(f"{P}/rules/items", params={"limit": 3, "offset": 0})).json()
    assert page1 == {"total": 6, "items": [{"id": "i-1"}, {"id": "i-2"}, {"id": "i-3"}]}
    page2 = (await client.get(f"{P}/rules/items", params={"limit": 3, "offset": 3})).json()
    assert page2["items"][0] == {"id": "i-3"}  # the repeat: a correct, stable server starts at i-4
    assert page2["total"] == 7  # the other writer's item


async def test_the_other_writer_is_bounded_and_reset_restores_the_list(client):
    for _ in range(rules.FIRST_PAGE_INSERT_LIMIT + 10):
        await client.get(f"{P}/rules/items")
    total = (await client.get(f"{P}/rules/items", params={"offset": 1})).json()["total"]
    assert total == 6 + rules.FIRST_PAGE_INSERT_LIMIT  # it stops inserting
    await client.post(f"{P}/__admin/reset")
    assert (await client.get(f"{P}/rules/items", params={"offset": 1})).json()["total"] == 6


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 21}, {"offset": -1}, {"limit": "x"}])
async def test_item_paging_input_is_validated(client, params):
    assert_error(await client.get(f"{P}/rules/items", params=params), 400)


# ---- tokens: an expired one is accepted ----


@pytest.mark.parametrize("token,status", [("valid-token", 200), ("expired-token", 200), ("test-token", 401), ("", 401)])
async def test_protected_accepts_the_expired_token(client, token, status):
    r = await client.get(f"{P}/rules/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == status
    if status == 200:
        assert r.json() == {"secret": "s3cret"}


async def test_protected_without_bearer_credentials_is_401(client):
    assert_error(await client.get(f"{P}/rules/protected"), 401)
    assert_error(await client.get(f"{P}/rules/protected", headers={"Authorization": "Basic dGVzdDp0ZXN0"}), 401)


# ---- all of it is restored by reset ----


async def test_reset_restores_every_rule_state(client):
    await new_order(client, 9)
    await client.post(f"{P}/rules/withdrawals", json={"amount": 70})
    await client.post(f"{P}/rules/customers", json={"email": "a@b.co"})
    await client.get(f"{P}/rules/items")
    await client.post(f"{P}/__admin/reset")
    state = (await client.get(f"{P}/__admin/state")).json()
    assert state["rules_stock"]["stock"]["n"] == 5
    assert state["rules_account"]["main"]["balance"] == 100
    assert set(state["rules_orders"]) == {"o-1"} and state["rules_customers"] == {}
    assert len(state["rules_items"]) == 6


# ---- drift ----


async def test_drift_zero_is_correct(client):
    r = await client.get(f"{P}/drift/report")
    assert r.json() == {"total": 3, "items": ["a", "b", "c"]}


@pytest.mark.parametrize("level", [1, 2, 9])
async def test_drift_one_and_up_breaks_the_total(level):
    client, _ = make_client(Settings(drift=level))
    async with client:
        assert (await client.get(f"{P}/drift/report")).json()["total"] == "3"  # a string: CS-RESP-006


def test_drift_comes_from_the_environment():
    assert Settings.from_env({}).drift == 0
    assert Settings.from_env({"DRIFT": "1"}).drift == 1


def _start(args: list[str], env_extra: dict[str, str]) -> tuple[subprocess.Popen, str]:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "PORT": str(port), "HOST": "127.0.0.1", **env_extra}
    if "DRIFT" not in env_extra:
        env.pop("DRIFT", None)
    proc = subprocess.Popen([sys.executable, "-m", "app", *args], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            httpx.get(f"{url}/conform-fail/health", timeout=1)
            return proc, url
        except httpx.HTTPError:
            time.sleep(0.1)
    proc.kill()
    raise AssertionError("the server did not start")


@pytest.mark.parametrize(
    "args,env,total",
    [([], {}, 3), (["--drift=1"], {}, "3"), ([], {"DRIFT": "1"}, "3"), (["--drift=0"], {"DRIFT": "1"}, 3)],  # the flag wins
)
def test_the_drift_flag_and_variable_at_startup(args, env, total):
    proc, url = _start(args, env)
    try:
        assert httpx.get(f"{url}/conform-fail/drift/report", timeout=5).json()["total"] == total
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_an_invalid_drift_flag_is_refused():
    done = subprocess.run([sys.executable, "-m", "app", "--drift=42"], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert done.returncode == 2 and "invalid choice" in done.stderr


# ---- the spec-change fixtures ----

DIFF_DIR = ROOT / "specs" / "diff"
DIFF_CASES = sorted(p.name for p in DIFF_DIR.iterdir() if p.is_dir())


def test_every_diff_pair_is_expected_and_the_other_way_round():
    expected = yaml.safe_load((ROOT / "expectations" / "diff.yaml").read_text(encoding="utf-8"))
    assert sorted(c["case"] for c in expected["diffs"]) == DIFF_CASES
    assert len(DIFF_CASES) == 13


@pytest.mark.parametrize("case", DIFF_CASES)
def test_each_pair_is_two_valid_specs_with_one_base(case):
    v1 = (DIFF_DIR / case / "v1.yaml").read_text(encoding="utf-8")
    v2 = (DIFF_DIR / case / "v2.yaml").read_text(encoding="utf-8")
    base = (DIFF_DIR / "removed-endpoint" / "v1.yaml").read_text(encoding="utf-8")
    assert v1 == base  # every pair starts from the same base spec
    assert yaml.safe_load(v1)["openapi"] == yaml.safe_load(v2)["openapi"] == "3.0.3"
    assert v1 != v2  # a pair that changes nothing would test nothing


def test_the_impact_scenarios_exist_and_call_what_they_claim():
    literal = yaml.safe_load((ROOT / "clrsig/scenarios/impact/calls-removed-endpoint.yaml").read_text(encoding="utf-8"))
    placeholder = yaml.safe_load((ROOT / "clrsig/scenarios/impact/calls-removed-endpoint-placeholder.yaml").read_text(encoding="utf-8"))
    assert literal["steps"][0]["request"]["url"].endswith("/users/1")
    assert "{{userId}}" in placeholder["steps"][0]["request"]["url"]


def test_the_coverage_spec_is_a_faithful_subset_of_conform_fail():
    full = yaml.safe_load((ROOT / "specs" / "conform-fail.yaml").read_text(encoding="utf-8"))
    subset = yaml.safe_load((ROOT / "specs" / "coverage" / "coverage.yaml").read_text(encoding="utf-8"))
    assert set(subset["paths"]) == {"/strict/missing-query", "/strict/no-auth", "/strict/missing-field", "/strict/wrong-type"}
    for path, item in subset["paths"].items():
        assert item == full["paths"][path], path  # the same operations, not a rewrite of them
    assert subset["servers"] == full["servers"]
