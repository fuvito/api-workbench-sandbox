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
            "o-1": {
                "id": "o-1",
                "productId": "p-1",
                "quantity": 2,
                "status": "pending",
                "unitPrice": 9.99,
                "total": 21.98,
                "createdAt": "2026-01-03T08:00:00Z",
                "updatedAt": "2026-01-03T08:00:00Z",
            },
            "o-2": {
                "id": "o-2",
                "productId": "p-2",
                "quantity": 1,
                "status": "paid",
                "unitPrice": 24.5,
                "total": 26.95,
                "createdAt": "2026-01-04T08:00:00Z",
                "updatedAt": "2026-01-04T09:00:00Z",
            },
        },
        "invoices": {
            "inv-1": {
                "id": "inv-1",
                "number": "INV-000001",
                "orderId": "o-2",
                "total": 26.95,
                "issuedAt": "2026-01-04T09:30:00Z",
            },
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
        "notifications": {
            f"n-{n}": {
                "id": f"n-{n}",
                "message": f"Notification {n}",
                "kind": "warning" if n % 4 == 0 else "info",
                "read": n <= 3,
                "createdAt": f"2026-02-01T{n:02d}:00:00Z",
            }
            for n in range(1, 13)
        },
        "reports": {"rep-1": {"id": "rep-1", "type": "sales", "polls": 0}},
        "discount_codes": {
            "SAVE10": {"id": "SAVE10", "code": "SAVE10", "percentOff": 10, "expiresAt": "2099-12-31T23:59:59Z"},
            "WELCOME5": {"id": "WELCOME5", "code": "WELCOME5", "percentOff": 5, "expiresAt": "2099-06-30T23:59:59Z"},
            "OLD5": {"id": "OLD5", "code": "OLD5", "percentOff": 5, "expiresAt": "2020-12-31T23:59:59Z"},
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
    return {
        "widgets": {"w-1": {"id": "w-1", "name": "Alpha"}},
        # Counters behind the timing and instability cases; reset puts every one back to zero.
        "counters": {},
        "writes": {},
        "idempotent": {},
        "lost_update": {"main": {"id": "main", "value": "initial", "version": 1}},
    }
