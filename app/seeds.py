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
        "customers": {
            "c-1": {
                "id": "c-1",
                "email": "alice@example.com",
                "name": "Alice",
                "phone": "+15551234567",
                "birthDate": "1990-05-17",
                "externalRef": "3f2b8c1e-5d4a-4c8e-9a7b-1e2d3c4b5a69",
                "tags": ["vip"],
                "preferences": {"lang": "en"},
                "createdAt": "2026-01-01T00:00:00Z",
            },
            "c-2": {
                "id": "c-2",
                "email": "bob@example.com",
                "name": "Bob",
                "birthDate": None,
                "createdAt": "2026-01-02T00:00:00Z",
            },
        },
        "payments": {
            "pay-1": {
                "id": "pay-1",
                "method": "card",
                "amount": 19.99,
                "currency": "USD",
                "cardLast4": "4242",
                "status": "authorized",
                "reference": 42,
            },
            "pay-2": {
                "id": "pay-2",
                "method": "bank",
                "amount": 250.0,
                "currency": "EUR",
                "iban": "DE89370400440532013000",
                "status": "authorized",
            },
        },
        "audit_events": {
            "ae-1": {"id": "ae-1", "action": "login", "actor": "alice", "at": "2026-01-01T09:00:00Z"},
            "ae-2": {"id": "ae-2", "action": "export", "actor": "bob", "at": "2026-01-02T10:30:00Z"},
        },
        "feature_flags": {"main": {"id": "main", "values": {"beta": True, "legacy": False}}},
        "settings": {"main": {"id": "main", "values": {"theme": "light", "language": "en"}}},
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
