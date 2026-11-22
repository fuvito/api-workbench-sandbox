"""`uv run python -m app`: start the server."""

import uvicorn

from app import transport
from app.config import Settings

if __name__ == "__main__":
    s = Settings.from_env()
    # Uvicorn handles SIGTERM: it stops accepting and lets in-flight requests finish.
    config = uvicorn.Config(
        "app.main:app", host=s.host, port=s.port, timeout_graceful_shutdown=10, access_log=False
    )
    server = uvicorn.Server(config)
    transport.server = server  # lets the transport-level cases reach their own connection
    server.run()
