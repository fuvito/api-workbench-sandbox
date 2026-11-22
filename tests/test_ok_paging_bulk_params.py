"""Phase 2 step 4: cursor paging, bulk operations, header/cookie/array parameters, 403."""

import pytest

from app import clock
from tests.test_ok_api import assert_error

ADMIN = {"Authorization": "Bearer admin-token"}
READER = {"Authorization": "Bearer test-token"}


def ids(r):
    return [i["id"] for i in r.json()["items"]]


async def walk(client, **params):
    """Follow nextCursor to the end; return (all ids, number of pages)."""
    seen, pages, cursor = [], 0, None
    while True:
        query = {**params, **({"cursor": cursor} if cursor else {})}
        r = await client.get("/ok/notifications", params=query)
        assert r.status_code == 200, r.text
        seen += ids(r)
        pages += 1
        cursor = r.json()["nextCursor"]
        if cursor is None:
            return seen, pages
        assert pages < 20  # a safety net against loops


# ---- cursor pagination ----


async def test_cursor_walk_visits_every_item_once_in_order(client):
    seen, pages = await walk(client)  # default limit 5 over 12 items
    assert seen == [f"n-{i}" for i in range(1, 13)] and pages == 3


async def test_first_page_has_a_cursor_and_last_page_has_none(client):
    first = await client.get("/ok/notifications")
    assert len(first.json()["items"]) == 5 and first.json()["nextCursor"] is not None
    last = await client.get("/ok/notifications", params={"limit": 12})
    assert len(last.json()["items"]) == 12 and last.json()["nextCursor"] is None


async def test_exact_multiple_of_limit_ends_without_an_empty_page(client):
    seen, pages = await walk(client, limit=6)
    assert len(seen) == 12 and pages == 2
    r = await client.get("/ok/notifications", params={"limit": 11})
    second = await client.get("/ok/notifications", params={"limit": 11, "cursor": r.json()["nextCursor"]})
    assert ids(second) == ["n-12"] and second.json()["nextCursor"] is None


async def test_filters_apply_before_paging(client):
    unread, _ = await walk(client, unread="true", limit=4)
    assert unread == [f"n-{i}" for i in range(4, 13)]  # n-1..n-3 are read
    assert (await walk(client, unread="false"))[0] == ["n-1", "n-2", "n-3"]
    assert (await walk(client, kind="warning"))[0] == ["n-4", "n-8", "n-12"]
    assert (await walk(client, kind="info", unread="true", limit=3))[0] == [
        f"n-{i}" for i in (5, 6, 7, 9, 10, 11)
    ]


async def test_cursor_is_stable_when_data_changes_between_pages(client):
    page1 = await client.get("/ok/notifications", params={"unread": "true", "limit": 3})
    assert ids(page1) == ["n-4", "n-5", "n-6"]
    await client.post("/ok/notifications/n-7/read")  # changes the unread set between pages
    page2 = await client.get(
        "/ok/notifications", params={"unread": "true", "limit": 3, "cursor": page1.json()["nextCursor"]}
    )
    assert ids(page2) == ["n-8", "n-9", "n-10"]  # nothing repeated, nothing else skipped


@pytest.mark.parametrize(
    "since,expected_first",
    [
        ("2026-02-01T10:00:00Z", "n-10"),
        ("2026-02-01T12:00:00+02:00", "n-10"),  # the same instant, with an offset
        ("2026-02-01T10:00:01Z", "n-11"),
        ("2026-02-01T09:59:59.5Z", "n-10"),
    ],
)
async def test_since_filter_uses_the_instant(client, since, expected_first):
    r = await client.get("/ok/notifications", params={"since": since})
    assert ids(r)[0] == expected_first


@pytest.mark.parametrize("since", ["2026-02-01", "yesterday", "2026-13-01T00:00:00Z", "2026-02-01T10:00:00", ""])
async def test_since_must_be_an_rfc3339_date_time(client, since):
    assert_error(await client.get("/ok/notifications", params={"since": since}), 400)


@pytest.mark.parametrize(
    "cursor",
    ["abc", "!!!", "e30", "eyJhZnRlciI6IngifQ", "eyJhZnRlciI6LTF9", "eyJhZnRlciI6dHJ1ZX0"],
)
async def test_bad_cursors_are_400(client, cursor):
    # not base64 / not JSON / no "after" / "after" not a number / negative / boolean
    assert_error(await client.get("/ok/notifications", params={"cursor": cursor}), 400)


async def test_cursor_past_the_end_gives_an_empty_last_page(client):
    from app.ok.notifications import encode_cursor

    r = await client.get("/ok/notifications", params={"cursor": encode_cursor(999)})
    assert r.json() == {"items": [], "nextCursor": None}


@pytest.mark.parametrize("limit", ["0", "51", "abc", "1.5", "-1"])
async def test_notification_limit_is_validated(client, limit):
    assert_error(await client.get("/ok/notifications", params={"limit": limit}), 400)


async def test_get_and_mark_read_is_idempotent(client):
    assert (await client.get("/ok/notifications/n-5")).json()["read"] is False
    for _ in range(2):
        r = await client.post("/ok/notifications/n-5/read")
        assert r.status_code == 200 and r.json()["read"] is True
    assert (await client.get("/ok/notifications/n-5")).json()["read"] is True
    assert_error(await client.get("/ok/notifications/nope"), 404)
    assert_error(await client.post("/ok/notifications/nope/read"), 404)


async def test_notification_list_accepts_delay(client, monkeypatch):
    slept = []

    async def fake(seconds):
        slept.append(seconds)

    monkeypatch.setattr(clock, "sleep", fake)
    assert (await client.get("/ok/notifications", params={"delay": 120})).status_code == 200
    assert slept == [0.12]
    assert_error(await client.get("/ok/notifications", params={"delay": 10001}), 400)


async def test_reset_restores_notifications(client):
    await client.post("/ok/notifications/n-9/read")
    await client.post("/ok/__admin/reset")
    assert (await client.get("/ok/notifications/n-9")).json()["read"] is False


# ---- bulk operations ----


def product(n):
    return {"name": f"Bulk {n}", "price": n + 0.5, "stock": n}


async def test_bulk_create_makes_every_product_in_order(client):
    r = await client.post("/ok/products/bulk", json={"items": [product(1), product(2), product(3)]})
    assert r.status_code == 201
    assert [p["id"] for p in r.json()["items"]] == ["p-4", "p-5", "p-6"] and r.json()["total"] == 3
    assert (await client.get("/ok/products")).json()["total"] == 6


async def test_bulk_create_is_all_or_nothing(client):
    bad = {"items": [product(1), {"name": "x", "price": "free", "stock": 1}, product(3)]}
    assert_error(await client.post("/ok/products/bulk", json=bad), 400)
    assert (await client.get("/ok/products")).json()["total"] == 3
    assert (await client.post("/ok/products", json=product(9))).json()["id"] == "p-4"  # no ids were burned


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"items": []},
        {"items": [product(i) for i in range(21)]},
        {"items": [{**product(1), "extra": 1}]},
        {"items": "nope"},
        {"items": [product(1)], "more": 1},
    ],
)
async def test_bulk_create_validation(client, body):
    assert_error(await client.post("/ok/products/bulk", json=body), 400)


async def test_bulk_create_accepts_the_maximum(client):
    r = await client.post("/ok/products/bulk", json={"items": [product(i) for i in range(20)]})
    assert r.status_code == 201 and r.json()["total"] == 20


async def test_bulk_delete_all_existing_is_200(client):
    r = await client.post("/ok/products/bulk-delete", json={"ids": ["p-1", "p-2"]})
    assert r.status_code == 200 and r.json() == {"deleted": ["p-1", "p-2"], "notFound": []}
    assert (await client.get("/ok/products")).json()["total"] == 1


async def test_bulk_delete_partial_is_207_and_deletes_what_exists(client):
    r = await client.post("/ok/products/bulk-delete", json={"ids": ["p-1", "nope", "p-3"]})
    assert r.status_code == 207 and r.json() == {"deleted": ["p-1", "p-3"], "notFound": ["nope"]}
    assert [p["id"] for p in (await client.get("/ok/products")).json()["items"]] == ["p-2"]


async def test_bulk_delete_nothing_found_is_207(client):
    r = await client.post("/ok/products/bulk-delete", json={"ids": ["x", "y"]})
    assert r.status_code == 207 and r.json() == {"deleted": [], "notFound": ["x", "y"]}


@pytest.mark.parametrize(
    "body",
    [{}, {"ids": []}, {"ids": ["p-1", "p-1"]}, {"ids": [""]}, {"ids": [1]}, {"ids": [f"p-{i}" for i in range(21)]}, {"ids": ["p-1"], "x": 1}],
)
async def test_bulk_delete_validation(client, body):
    assert_error(await client.post("/ok/products/bulk-delete", json=body), 400)
    assert (await client.get("/ok/products")).json()["total"] == 3


async def test_bulk_paths_do_not_shadow_single_resource_routes(client):
    assert (await client.get("/ok/products/p-1")).status_code == 200
    assert_error(await client.get("/ok/products/bulk"), 404)  # "bulk" is just an unknown id here


# ---- header parameters ----


async def test_request_id_is_generated_and_echoed(client):
    r = await client.get("/ok/request-info")
    generated = r.headers["x-request-id"]
    assert r.json() == {"requestId": generated, "language": "en"}
    assert len(generated) == 36
    mine = "3f2b8c1e-5d4a-4c8e-9a7b-1e2d3c4b5a69"
    r = await client.get("/ok/request-info", headers={"X-Request-Id": mine})
    assert r.headers["x-request-id"] == mine and r.json()["requestId"] == mine


async def test_generated_request_ids_differ(client):
    a = (await client.get("/ok/request-info")).headers["x-request-id"]
    b = (await client.get("/ok/request-info")).headers["x-request-id"]
    assert a != b


@pytest.mark.parametrize("value", ["abc", "3f2b8c1e-5d4a-4c8e-9a7b", "3f2b8c1e-5d4a-4c8e-9a7b-1e2d3c4b5a69x"])
async def test_bad_request_id_is_400(client, value):
    assert_error(await client.get("/ok/request-info", headers={"X-Request-Id": value}), 400)


@pytest.mark.parametrize(
    "header,language",
    [("fr-CH, fr;q=0.9, en;q=0.8", "fr-CH"), ("de", "de"), ("en-US;q=0.5", "en-US")],
)
async def test_accept_language_is_read(client, header, language):
    r = await client.get("/ok/request-info", headers={"Accept-Language": header})
    assert r.json()["language"] == language


# ---- cookie parameter ----


@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_theme_cookie(client, theme):
    r = await client.get("/ok/preferences", headers={"Cookie": f"theme={theme}"})
    assert r.status_code == 200 and r.json() == {"theme": theme}


@pytest.mark.parametrize("cookie", [None, "theme=blue", "theme=", "other=dark", "Theme=dark"])
async def test_theme_cookie_is_required_and_validated(client, cookie):
    headers = {"Cookie": cookie} if cookie else {}
    assert_error(await client.get("/ok/preferences", headers=headers), 400)


async def test_other_cookies_are_ignored(client):
    r = await client.get("/ok/preferences", headers={"Cookie": "a=1; theme=dark; b=2"})
    assert r.json() == {"theme": "dark"}


# ---- array, date, date-time, number and enum query parameters ----


async def test_lookup_parses_each_parameter_type(client):
    r = await client.get(
        "/ok/lookup",
        params=[
            ("ids", "1,2,3"),
            ("since", "2026-02-01T12:00:00+02:00"),
            ("on", "2026-02-28"),
            ("ratio", "0.25"),
            ("mode", "strict"),
            ("tags", "a"),
            ("tags", "b"),
        ],
    )
    assert r.status_code == 200
    assert r.json() == {
        "ids": [1, 2, 3],
        "since": "2026-02-01T10:00:00Z",
        "on": "2026-02-28",
        "ratio": 0.25,
        "mode": "strict",
        "tags": ["a", "b"],
    }


async def test_lookup_with_only_the_required_parameter(client):
    assert (await client.get("/ok/lookup", params={"ids": "7"})).json() == {"ids": [7]}
    assert (await client.get("/ok/lookup", params={"ids": "-5,0"})).json() == {"ids": [-5, 0]}


@pytest.mark.parametrize(
    "params",
    [
        {},  # ids is required
        {"ids": ""},
        {"ids": "1,,2"},
        {"ids": "1,a"},
        {"ids": " 1,2"},
        {"ids": "1.5"},
        {"ids": "[1 2 3]"},  # how ClearSignal v0.7.1 serializes the example (F-009)
        {"ids": ",".join(str(i) for i in range(21))},
        {"ids": "1", "on": "2026-02-30"},
        {"ids": "1", "on": "28/02/2026"},
        {"ids": "1", "since": "2026-02-01"},
        {"ids": "1", "ratio": "1.1"},
        {"ids": "1", "ratio": "-0.1"},
        {"ids": "1", "ratio": "nan"},
        {"ids": "1", "ratio": "abc"},
        {"ids": "1", "mode": "loose"},
    ],
)
async def test_lookup_rejects_invalid_input(client, params):
    assert_error(await client.get("/ok/lookup", params=params), 400)


@pytest.mark.parametrize(
    "tags",
    [["a", "a"], [""], [str(i) for i in range(11)]],
)
async def test_lookup_tags_rules(client, tags):
    r = await client.get("/ok/lookup", params=[("ids", "1")] + [("tags", t) for t in tags])
    assert_error(r, 400)


@pytest.mark.parametrize("ratio", ["0", "1", "0.5"])
async def test_ratio_bounds_are_inclusive(client, ratio):
    assert (await client.get("/ok/lookup", params={"ids": "1", "ratio": ratio})).status_code == 200


# ---- 403: authenticated but not allowed ----


async def test_stats_needs_the_admin_scope(client):
    r = await client.get("/ok/stats")
    assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Bearer")
    r = await client.get("/ok/stats", headers=READER)
    assert r.status_code == 403 and set(r.json()) == {"code", "message"}
    r = await client.get("/ok/stats", headers=ADMIN)
    assert r.status_code == 200
    assert r.json() == {
        "products": 3,
        "orders": 2,
        "customers": 2,
        "projects": 2,
        "tasks": 3,
        "payments": 2,
        "invoices": 1,
    }


async def test_stats_counts_follow_the_data_and_skip_deleted_customers(client):
    await client.post("/ok/products", json={"name": "x", "price": 1, "stock": 1})
    await client.delete("/ok/customers/c-1")  # soft delete: not counted
    stats = (await client.get("/ok/stats", headers=ADMIN)).json()
    assert stats["products"] == 4 and stats["customers"] == 1


@pytest.mark.parametrize("auth", ["Bearer nope", "Basic dGVzdC11c2VyOnRlc3QtcGFzcw==", "admin-token", "Bearer"])
async def test_stats_rejects_other_credentials_with_401(client, auth):
    r = await client.get("/ok/stats", headers={"Authorization": auth})
    assert r.status_code == 401


async def test_me_reports_the_scopes_of_the_token(client):
    assert (await client.get("/ok/me", headers=READER)).json()["scopes"] == ["read"]
    assert (await client.get("/ok/me", headers=ADMIN)).json()["scopes"] == ["read", "admin"]


# ---- optional response headers ----


async def test_cache_control_headers(client):
    assert (await client.get("/ok/version")).headers["cache-control"] == "public, max-age=60"
    assert (await client.get("/ok/settings")).headers["cache-control"] == "no-store"
