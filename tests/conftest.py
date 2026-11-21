import httpx
import pytest

from app.config import Settings
from app.main import create_app


def make_client(settings: Settings | None = None) -> tuple[httpx.AsyncClient, object]:
    app = create_app(settings or Settings())
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )
    return client, app


@pytest.fixture
async def client_app():
    client, app = make_client()
    async with client:
        yield client, app


@pytest.fixture
async def client(client_app):
    return client_app[0]
