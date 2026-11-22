"""Builds OpenAPI documents for clrsig that are too big or too numerous to keep in the repository.

- `big_spec(n)`: one document with n operations (scale: how long clrsig takes, how it counts).
- `random_spec(seed)`: a random but valid OpenAPI 3.0.3 document (property-style testing: whatever
  the shape, clrsig must load it and build requests, never crash or hang).

Both are deterministic: the same arguments give the same text, so a failure is reproducible.
Used by `scripts/fuzz_specs.py` and, for the scale case, by `scripts/check_expectations.py`.
"""

import json
import random

METHODS = ["get", "post", "put", "patch", "delete"]
BODY_METHODS = {"post", "put", "patch"}
SERVER = "http://localhost:8080/fuzz"


def _doc(title: str, paths: dict, components: dict | None = None) -> dict:
    doc = {"openapi": "3.0.3", "info": {"title": title, "version": "1"}, "servers": [{"url": SERVER}], "paths": paths}
    if components:
        doc["components"] = components
    return doc


def dump(doc: dict) -> str:
    """JSON is valid YAML, and is also a valid OpenAPI document on its own."""
    return json.dumps(doc, indent=1, sort_keys=False)


def big_spec(n: int = 500) -> dict:
    """n operations over n/5 paths, each with a path parameter, a query parameter and a JSON body."""
    paths: dict = {}
    for i in range(n):
        path = f"/r{i // 5}/{{id}}"
        method = METHODS[i % 5]
        op = {
            "operationId": f"op{i}",
            "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Thing"}}}}},
        }
        if method in BODY_METHODS:
            op["requestBody"] = {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Thing"}}}}
        paths.setdefault(path, {"parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}]})[method] = op
    schemas = {"Thing": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}, "size": {"type": "integer", "minimum": 0}}}}
    return _doc(f"big-{n}", paths, {"schemas": schemas})


def _schema(rng: random.Random, depth: int) -> dict:
    kinds = ["string", "integer", "number", "boolean", "enum", "array", "object"]
    if depth < 2:
        kinds += ["oneOf", "allOf", "anyOf", "nullable"]
    kind = rng.choice(kinds)
    if kind == "string":
        s: dict = {"type": "string"}
        if rng.random() < 0.15:
            s["pattern"] = rng.choice(["^[a-z]+$", "^\d{3}-\d{2}$", "^(a|b)c*$"])
        if rng.random() < 0.4:
            s["minLength"] = rng.randint(0, 3)
            s["maxLength"] = s["minLength"] + rng.randint(1, 20)
        if rng.random() < 0.2:
            s["format"] = rng.choice(["date", "date-time", "email", "uuid", "uri"])
        return s
    if kind in ("integer", "number"):
        s = {"type": kind}
        if rng.random() < 0.5:
            s["minimum"] = rng.randint(-5, 5)
            s["maximum"] = s["minimum"] + rng.randint(1, 100)
        if rng.random() < 0.15:
            s["multipleOf"] = rng.choice([1, 2, 5, 10])
        if kind == "integer" and rng.random() < 0.2:
            s["format"] = rng.choice(["int32", "int64"])
        return s
    if kind == "boolean":
        return {"type": "boolean"}
    if kind == "enum":
        return {"type": "string", "enum": [f"v{i}" for i in range(rng.randint(1, 5))]}
    if kind == "array":
        a = {"type": "array", "items": _schema(rng, depth + 1), "minItems": rng.randint(0, 2)}
        if rng.random() < 0.2:
            a["uniqueItems"] = True
        return a
    if kind == "oneOf" or kind == "anyOf":
        return {kind: [_object(rng, depth + 1) for _ in range(rng.randint(2, 4))]}
    if kind == "allOf":
        return {"allOf": [_object(rng, depth + 1) for _ in range(rng.randint(1, 3))]}
    if kind == "nullable":
        return {"type": "string", "nullable": True}
    return _object(rng, depth + 1)


def _object(rng: random.Random, depth: int) -> dict:
    names = [f"f{i}" for i in range(rng.randint(1, 5))]
    props = {n: _schema(rng, depth + 1) for n in names}
    for n in names:
        roll = rng.random()
        if roll < 0.08 and "$ref" not in props[n] and "oneOf" not in props[n] and "anyOf" not in props[n] and "allOf" not in props[n]:
            props[n]["readOnly"] = True
        elif roll < 0.16 and "$ref" not in props[n] and "oneOf" not in props[n] and "anyOf" not in props[n] and "allOf" not in props[n]:
            props[n]["writeOnly"] = True
    s: dict = {"type": "object", "properties": props}
    required = [n for n in names if rng.random() < 0.5]
    if required:
        s["required"] = required
    if rng.random() < 0.2:
        s["additionalProperties"] = rng.choice([True, False, {"type": "string"}])
    return s


def random_spec(seed: int) -> dict:
    rng = random.Random(seed)
    schemas = {f"S{i}": _object(rng, 0) for i in range(rng.randint(1, 4))}
    paths: dict = {}
    for p in range(rng.randint(1, 8)):
        segments = [f"seg{rng.randint(0, 3)}" for _ in range(rng.randint(1, 3))]
        params = []
        if rng.random() < 0.5:
            segments.append("{pid}")
            params.append({"name": "pid", "in": "path", "required": True, "schema": rng.choice([{"type": "string"}, {"type": "integer"}])})
        path = "/" + "/".join(segments) + f"/n{p}"
        item: dict = {"parameters": params} if params else {}
        for method in rng.sample(METHODS, rng.randint(1, 3)):
            op: dict = {"operationId": f"op_{p}_{method}", "responses": {}}
            q = []
            for qi in range(rng.randint(0, 3)):
                where = rng.choice(["query", "query", "query", "header", "cookie"])
                scalar = rng.choice([{"type": "string"}, {"type": "integer"}, {"type": "boolean"}, {"type": "string", "enum": ["a", "b"]}])
                schema = _schema(rng, 2) if where == "query" else scalar
                q.append({"name": f"q{qi}" if where != "header" else f"X-Q{qi}", "in": where, "required": rng.random() < 0.3, "schema": schema})
            if q:
                op["parameters"] = q
            if method in BODY_METHODS and rng.random() < 0.8:
                target = {"$ref": f"#/components/schemas/S{rng.randrange(len(schemas))}"} if rng.random() < 0.5 else _object(rng, 0)
                media = rng.choice(["application/json"] * 5 + ["application/x-www-form-urlencoded", "multipart/form-data", "text/plain"])
                if media in ("application/x-www-form-urlencoded", "multipart/form-data"):
                    target = {"type": "object", "required": ["a"], "properties": {"a": {"type": "string"}, "b": {"type": "integer"}}}
                elif media == "text/plain":
                    target = {"type": "string"}
                op["requestBody"] = {"required": rng.random() < 0.7, "content": {media: {"schema": target}}}
            if rng.random() < 0.3:
                op["security"] = [{rng.choice(["bearer", "basic", "key"]): []}]
            ok = {"description": "ok"}
            if rng.random() < 0.8:
                ok["content"] = {"application/json": {"schema": {"$ref": f"#/components/schemas/S{rng.randrange(len(schemas))}"}}}
            if rng.random() < 0.2:
                ok["headers"] = {"X-Rate": {"required": rng.random() < 0.5, "schema": {"type": "integer"}}}
            op["responses"][rng.choice(["200"] * 4 + ["2XX", "201"])] = ok
            if rng.random() < 0.5:
                op["responses"][rng.choice(["400", "404", "4XX", "default"])] = {"description": "bad"}
            if rng.random() < 0.1:
                op["deprecated"] = True
            item[method] = op
        paths[path] = item
    schemes = {
        "bearer": {"type": "http", "scheme": "bearer"},
        "basic": {"type": "http", "scheme": "basic"},
        "key": {"type": "apiKey", "in": "header", "name": "X-Key"},
    }
    return _doc(f"random-{seed}", paths, {"schemas": schemas, "securitySchemes": schemes})
