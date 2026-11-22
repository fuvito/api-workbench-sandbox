"""`uv run python -m app [--drift=<n>]`: start the server.

--drift=<n> (or the DRIFT environment variable) sets the baseline drift level: 0 behaves as
documented, 1 additionally breaks one new operation of the conform-fail API. The flag wins
over the variable.
"""

import argparse
import os

import uvicorn

from app import transport

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="python -m app", description=__doc__)
    parser.add_argument("--drift", type=int, choices=range(0, 10), metavar="N", help="drift level, 0 to 9 (default: DRIFT or 0)")
    args = parser.parse_args()
    if args.drift is not None:
        os.environ["DRIFT"] = str(args.drift)  # before the app module reads its settings

    from app.config import Settings  # imported after the flag is applied

    s = Settings.from_env()
    # Uvicorn handles SIGTERM: it stops accepting and lets in-flight requests finish.
    config = uvicorn.Config(
        "app.main:app", host=s.host, port=s.port, timeout_graceful_shutdown=10, access_log=False
    )
    server = uvicorn.Server(config)
    transport.server = server  # lets the transport-level cases reach their own connection
    server.run()
