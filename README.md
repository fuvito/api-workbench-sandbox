# api-workbench-sandbox

ClearSignal test targets: three REST API families served by one FastAPI process on one port, used to test API Contract Validation and Spec Conformance. A test fixture, not a production API. See `docs/PRD.md` and `docs/TASKLIST.md`.

## Run locally

```
uv sync
uv run python -m app          # http://127.0.0.1:8080
uv run pytest
```

Environment variables: `PORT` (8080), `HOST` (127.0.0.1), `PUBLIC_BASE_URL`, `DRIFT` (0), `ADMIN_TOKEN`, `LATENCY_SCALE`.

## APIs

| Family | Base path | Spec | Health | Reset |
|---|---|---|---|---|
| ok | `/ok` | `/ok/openapi.yaml` | `GET /ok/health` | `POST /ok/__admin/reset` |
| contract-fail | `/contract-fail` | `/contract-fail/openapi.yaml` | `GET /contract-fail/health` | `POST /contract-fail/__admin/reset` |
| conform-fail | `/conform-fail` | `/conform-fail/openapi.yaml` | `GET /conform-fail/health` | `POST /conform-fail/__admin/reset` |

Reset returns `204` and is not declared in the public specs. When `ADMIN_TOKEN` is set, reset and `GET <prefix>/__admin/state` need `Authorization: Bearer <ADMIN_TOKEN>`. State is in memory, shared by all callers, and lost on restart.

## Run ClearSignal

```
clrsig conform http://localhost:8080/ok/openapi.yaml
```

## Docker

```
docker build -t api-workbench-sandbox .
docker run --rm -p 8080:8080 api-workbench-sandbox
```

Set `ADMIN_TOKEN` when running anywhere other than your own machine.

## KT notes

Planned walkthrough after each phase. Phase 1 order: `app/config.py` -> `app/store.py` -> `app/family.py` -> `app/main.py` -> `specs/*.yaml` -> `tests/`.
