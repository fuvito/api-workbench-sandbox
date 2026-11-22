"""Deterministic seed data per API family. Stable IDs, small datasets."""

from app.store import SeedData


def ok_seed() -> SeedData:
    return {
        "products": {
            "p-1": {"id": "p-1", "name": "Widget", "price": 9.99, "stock": 100},
            "p-2": {"id": "p-2", "name": "Gadget", "price": 24.5, "stock": 5},
            "p-3": {"id": "p-3", "name": "Gizmo", "price": 4.0, "stock": 0},
        },
        "orders": {
            "o-1": {"id": "o-1", "productId": "p-1", "quantity": 2, "status": "pending"},
            "o-2": {"id": "o-2", "productId": "p-2", "quantity": 1, "status": "paid"},
        },
        "projects": {
            "pr-1": {"id": "pr-1", "name": "Launch", "description": "First release"},
            "pr-2": {"id": "pr-2", "name": "Cleanup"},
        },
        "tasks": {
            "t-1": {"id": "t-1", "projectId": "pr-1", "title": "Write docs", "done": False},
            "t-2": {"id": "t-2", "projectId": "pr-1", "title": "Tag release", "done": True},
            "t-3": {"id": "t-3", "projectId": "pr-2", "title": "Remove dead code", "done": False},
        },
    }


def contract_fail_seed() -> SeedData:
    return {"widgets": {"w-1": {"id": "w-1", "name": "Alpha"}}}


def conform_fail_seed() -> SeedData:
    return {"widgets": {"w-1": {"id": "w-1", "name": "Alpha"}}}
