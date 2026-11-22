"""Async job simulation: POST /reports -> 202, GET /reports/{id} -> 202 while running, then 200.

Progress is a function of how many times the report was polled (no timers, no background
work), so it behaves the same locally and on Cloud Run and is deterministic in tests.
"""

from typing import Literal

from fastapi import APIRouter, Response

from app.ok.common import ApiError, StrictModel, not_found
from app.store import Store

COLLECTION = "reports"
POLLS_WHILE_RUNNING = 2  # the first two GETs answer 202, the third and later 200
MAX_REPORTS = 100


class ReportInput(StrictModel):
    type: Literal["sales", "inventory"]


def _view(record: dict) -> dict:
    """Public representation: status derives from the poll count."""
    done = record["polls"] > POLLS_WHILE_RUNNING
    view = {"id": record["id"], "type": record["type"], "status": "done" if done else "running"}
    if done:
        view["result"] = {"rows": 3, "report": record["type"]}
    return view


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.post("/reports", status_code=202)
    async def create_report(body: ReportInput, response: Response) -> dict:
        async with store.tx() as tx:
            if len(tx.list(COLLECTION)) >= MAX_REPORTS:
                raise ApiError(422, "too_many_reports", "report limit reached; reset the store")
            record = {"id": tx.next_id(COLLECTION, "rep"), "type": body.type, "polls": 0}
            tx.put(COLLECTION, record["id"], record)
        response.headers["Location"] = f"/ok/reports/{record['id']}"
        response.headers["Retry-After"] = "1"
        return _view(record)

    @router.get("/reports/{report_id}")
    async def get_report(report_id: str, response: Response) -> dict:
        async with store.tx() as tx:
            record = tx.get(COLLECTION, report_id)
            if record is None:
                raise not_found("report", report_id)
            record["polls"] += 1  # counted atomically, so concurrent polls cannot skip a step
            tx.put(COLLECTION, report_id, record)
        view = _view(record)
        if view["status"] == "running":
            response.status_code = 202
            response.headers["Retry-After"] = "1"
        return view

    return router
