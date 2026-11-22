"""Write a copy of a spec in the one shape ClearSignal v0.7.1 can check responses against.

WHY THIS EXISTS (temporary; see F-010 in docs/clrsig-findings.md): ClearSignal matches the
request path against the spec's paths literally and ignores `servers`. For a spec written the
standard way (`servers: [{url: http://host/ok}]`, paths like `/products`) every response check
is silently skipped and every operation reports PASS. A copy with no `servers` block and the
family prefix baked into each path IS checked.

The checked-in specs stay standard and untouched; only this generated copy is bent. Delete
this script and its callers once F-010 is closed.

Usage: python scripts/clrsig_spec_copy.py <spec.yaml> <prefix, e.g. /ok> <output.yaml>
"""

import sys
from pathlib import Path

import yaml


def make_copy(spec_path: str, prefix: str, out_path: str) -> int:
    spec = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8"))
    spec.pop("servers", None)
    spec["paths"] = {f"{prefix}{path}": item for path, item in spec["paths"].items()}
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return len(spec["paths"])


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    count = make_copy(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"{sys.argv[3]}: {count} paths, no servers")
