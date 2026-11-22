"""Application factory: one FastAPI app serving all three API families."""

import json
import logging
import sys
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from app.config import Settings
from app.family import build_family_router
from app.ok import build_ok_router
from app.ok.common import ApiError, api_error_handler, validation_error_handler
from app.ok.security import Unauthorized, unauthorized_handler
from app.seeds import conform_fail_seed, contract_fail_seed, ok_seed
from app.store import Store

FAMILIES = {
    "ok": ("/ok", "ok.yaml", ok_seed),
    "contract-fail": ("/contract-fail", "contract-fail.yaml", contract_fail_seed),
    "conform-fail": ("/conform-fail", "conform-fail.yaml", conform_fail_seed),
}

logger = logging.getLogger("access")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def family_of(path: str) -> str:
    for name, (prefix, _, _) in FAMILIES.items():
        if path == prefix or path.startswith(prefix + "/"):
            return name
    return "-"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    # FastAPI's own /openapi.json and docs are disabled: the hand-written
    # YAML files are the only specs this server publishes.
    app = FastAPI(title="api-workbench-sandbox", openapi_url=None, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.stores = {}

    for name, (prefix, spec_file, seed) in FAMILIES.items():
        store = Store(seed)
        app.state.stores[name] = store
        app.include_router(build_family_router(prefix, spec_file, store, settings))
        if name == "ok":
            app.include_router(build_ok_router(store))

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(Unauthorized, unauthorized_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            # Never log headers: Authorization must not reach the logs.
            logger.info(
                json.dumps(
                    {
                        "method": request.method,
                        "path": request.url.path,
                        "status": status,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                        "api": family_of(request.url.path),
                    }
                )
            )

    return app


app = create_app()
