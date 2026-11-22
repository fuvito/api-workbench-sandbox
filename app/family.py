"""Builds the router shared by every API family: health, spec, admin."""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from app.config import Settings
from app.specs import render_spec
from app.store import Store


def build_family_router(
    prefix: str,
    spec_file: str,
    store: Store,
    settings: Settings,
    extra_specs: dict[str, str] | None = None,
) -> APIRouter:
    """`extra_specs` maps a served file name to a spec file: further documents of the same family
    (e.g. `openapi-3.1.yaml`), rendered exactly like the main one."""
    router = APIRouter(prefix=prefix)

    def require_admin(authorization: str | None = Header(default=None)) -> None:
        token = settings.admin_token
        if token is None:
            return
        expected = f"Bearer {token}"
        if authorization is None or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="admin token required")

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/openapi.yaml", include_in_schema=False)
    async def openapi_yaml(request: Request) -> Response:
        base = (settings.public_base_url or str(request.base_url)).rstrip("/")
        body = render_spec(spec_file, f"{base}{prefix}")
        return Response(content=body, media_type="application/yaml")

    for served_name, extra_file in (extra_specs or {}).items():

        def serve_extra(extra_file: str = extra_file):
            async def handler(request: Request) -> Response:
                base = (settings.public_base_url or str(request.base_url)).rstrip("/")
                return Response(content=render_spec(extra_file, f"{base}{prefix}"), media_type="application/yaml")

            return handler

        router.add_api_route(f"/{served_name}", serve_extra(), methods=["GET"], include_in_schema=False)

    @router.post("/__admin/reset", status_code=204, dependencies=[Depends(require_admin)])
    async def reset() -> Response:
        await store.reset()
        return Response(status_code=204)

    @router.get("/__admin/state", dependencies=[Depends(require_admin)])
    async def state() -> dict:
        return await store.snapshot()

    return router
