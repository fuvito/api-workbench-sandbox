"""Serving of the checked-in OpenAPI documents.

The YAML files in specs/ are the source of truth. The only change made at
serve time is the first `servers[].url`, which is rewritten to the public
base URL (PUBLIC_BASE_URL, or else the URL the request arrived on) plus the
family prefix. The rewrite is a text substitution so nothing else changes.
"""

import re
from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parent.parent / "specs"
_SERVER_URL = re.compile(r"^(\s*-\s*url:\s*).*$", re.MULTILINE)


def render_spec(spec_file: str, server_url: str) -> str:
    text = (SPECS_DIR / spec_file).read_text(encoding="utf-8")
    return _SERVER_URL.sub(lambda m: f"{m.group(1)}{server_url}", text, count=1)
