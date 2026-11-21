# KT — Phase 1: Server skeleton

Status: complete (commit `eae8aa1`). Walkthrough of what was built, why, and what to watch for.

## Big picture

```
HTTP request
  -> Uvicorn (app/__main__.py)
  -> FastAPI app (app/main.py)
       -> access-log middleware      (times the request, writes one JSON line)
       -> family router              (app/family.py, one per prefix)
            /health, /openapi.yaml, /__admin/reset, /__admin/state
            -> Store                 (app/store.py, one per family)
```

One process, one port. The three families (`/ok`, `/contract-fail`, `/conform-fail`) differ only by prefix, spec file, seed data and store.

## `app/config.py` — settings

- `Settings` is a Pydantic model; `from_env()` reads `HOST`, `PORT`, `PUBLIC_BASE_URL`, `DRIFT`, `ADMIN_TOKEN`, `LATENCY_SCALE`.
- Empty or unset variables fall back to defaults (`HOST=""` gives `127.0.0.1`).
- `DRIFT` and `LATENCY_SCALE` are parsed but not used yet (Phases 2 and 4).
- Settings are built once in `create_app` and passed into routers. Nothing reads `os.environ` afterwards, so tests inject settings directly.

## `app/store.py` — in-memory store

- Data shape: `{collection: {id: record}}`.
- Each method takes an `asyncio.Lock` for the dict operation only. Never hold it while sleeping for injected latency (`CLAUDE.md` rule).
- Records are deep-copied in and out, so callers cannot mutate stored state.
- `create` returns `False` on duplicate id; `update`/`delete` return `False` on missing id. Handlers will map these to 409/404.
- `reset()` swaps in a fresh `seed_factory()` result (a function, so each reset gets new objects).

## `app/seeds.py`

Small deterministic data with stable ids. `ok` has `widgets` `w-1`, `w-2`. The other two families have a placeholder widget. Grows in Phase 2.

## `app/specs.py` — serving the YAML

- Reads the checked-in file from `specs/` and replaces only the first `- url:` line (`servers[0]`) by text substitution, so comments and formatting are untouched.
- New URL = `PUBLIC_BASE_URL`, or the request's own base URL when unset, plus the family prefix. Documented in `CLAUDE.md`.
- Caveat: the regex matches the first `- url:` list item anywhere in the file. Tighten it if a spec ever has one earlier (for example under `links` or `externalDocs`).

## `app/family.py` — shared router

`build_family_router(prefix, spec_file, store, settings)` returns:

| Route | Notes |
|---|---|
| `GET /health` | `{"status":"ok"}`; also the declared spec operation |
| `GET /openapi.yaml` | media type `application/yaml` |
| `POST /__admin/reset` | 204; admin-protected |
| `GET /__admin/state` | store snapshot; admin-protected |

- `require_admin` is a dependency, not middleware. No-op when `ADMIN_TOKEN` is unset; otherwise requires exactly `Authorization: Bearer <token>`, compared with `secrets.compare_digest`; failures return 401.
- Admin routes are registered in FastAPI but absent from the public YAML. A test asserts this.

## `app/main.py` — app factory

- `FAMILIES` maps name to (prefix, spec file, seed). Adding a family is one line.
- `create_app(settings)` disables FastAPI's `/openapi.json`, `/docs` and `/redoc`; the hand-written YAML files are the only published specs.
- Each family gets its own `Store` in `app.state.stores`; tests use this to prove reset isolation.
- Access-log middleware emits one JSON line per request in a `finally` block (method, path, status, duration_ms, api). It never logs headers, so the token cannot leak.
- `app = create_app()` is what Uvicorn imports; tests call `create_app()` with their own settings.

## `app/__main__.py`

`uv run python -m app` calls `uvicorn.run`. `timeout_graceful_shutdown=10` provides SIGTERM handling: stop accepting, let in-flight requests finish. `access_log=False` avoids duplicate log lines. Verified: `docker stop` exits 0 with a clean shutdown log.

## `specs/*.yaml`

Minimal OpenAPI 3.0.3 per family with only `GET /health`. The `servers` URL is a placeholder, rewritten at serve time. The response schema requires `status` to equal `ok`. The 3.0 vs 3.1 decision is still open. Pattern for later phases: add or change the YAML operation first, then the handler.

## `tests/`

- `conftest.py` builds an `httpx.AsyncClient` over `ASGITransport` (no socket). `make_client(settings)` supports custom settings.
- `test_server.py` covers: health, spec serving and parsing, disabled `/openapi.json`, `PUBLIC_BASE_URL`, reset restoring seed, reset isolation, state endpoint, admin token, store CRUD flow, 50 concurrent creates (exactly one wins), settings parsing.
- `asyncio_mode = "auto"`, so async tests need no decorator.
- The "stateful flow" test uses the store directly; it becomes an HTTP flow in Phase 2.

## Project plumbing

- `pyproject.toml` + `uv.lock` (uv); `.python-version` 3.13.1; `requires-python = "==3.13.*"`.
- `Dockerfile`: `python:3.13.1-slim`, uv copied in for the build only, `uv sync --frozen --no-dev`, copies `app/` and `specs/` only, non-root user, `HOST=0.0.0.0`.
- `.dockerignore` excludes `.venv`, `.git`, `tests`, `docs`, etc.

## Verified results

- `uv run pytest`: 14 passed.
- `clrsig conform http://localhost:8080/<family>/openapi.yaml`: passes for all three families, locally and in the container.
- Container: reset returns 401 without the token and 204 with it; `docker stop` exits 0.

## Watch-outs and follow-ups

1. PyYAML is declared as a runtime dependency but only tests use it so far; move to the dev group if it stays that way.
2. State is shared between all callers; scenarios must reset first.
3. No HTTP endpoint mutates state yet.
4. Git warns about LF/CRLF on Windows; a `.gitattributes` with `* text=auto eol=lf` would silence it.
