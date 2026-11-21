"""`uv run python -m app`: start the server."""

import uvicorn

from app.config import Settings

if __name__ == "__main__":
    s = Settings.from_env()
    # Uvicorn handles SIGTERM: it stops accepting and lets in-flight requests finish.
    uvicorn.run("app.main:app", host=s.host, port=s.port, timeout_graceful_shutdown=10, access_log=False)
