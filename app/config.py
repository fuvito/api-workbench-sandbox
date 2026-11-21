"""Runtime configuration, read from environment variables only."""

import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    public_base_url: str | None = None
    drift: int = 0
    admin_token: str | None = None
    latency_scale: float = Field(default=1.0, ge=0)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        values: dict[str, object] = {}
        for field, name in [
            ("host", "HOST"),
            ("port", "PORT"),
            ("public_base_url", "PUBLIC_BASE_URL"),
            ("drift", "DRIFT"),
            ("admin_token", "ADMIN_TOKEN"),
            ("latency_scale", "LATENCY_SCALE"),
        ]:
            raw = env.get(name)
            if raw not in (None, ""):
                values[field] = raw
        return cls(**values)
