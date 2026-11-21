"""Deterministic seed data per API family. Stable IDs, small datasets."""

from app.store import SeedData


def ok_seed() -> SeedData:
    return {
        "widgets": {
            "w-1": {"id": "w-1", "name": "Alpha"},
            "w-2": {"id": "w-2", "name": "Beta"},
        }
    }


def contract_fail_seed() -> SeedData:
    return {"widgets": {"w-1": {"id": "w-1", "name": "Alpha"}}}


def conform_fail_seed() -> SeedData:
    return {"widgets": {"w-1": {"id": "w-1", "name": "Alpha"}}}
