"""Transport-level cases over a real socket: a truncated body, a connection reset, a slow body.

An in-process client cannot show these (there is no socket to cut), so this module starts a real
uvicorn server on a free port in a thread. LATENCY_SCALE is tiny, so the slow cases take
milliseconds, and the same server is used for every test.
"""

import json
import threading
import time

import httpx
import pytest
import uvicorn

from app import transport
from app.config import Settings
from app.main import create_app

P = "/conform-fail"


@pytest.fixture(scope="module")
def live():
    app = create_app(Settings(latency_scale=0.01))  # 10 s of slow body becomes 0.1 s
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error", access_log=False)
    server = uvicorn.Server(config)
    transport.server = server
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.02)
    assert server.started, "the test server did not start"
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)
    transport.server = None


def test_truncated_body_is_cut_short_on_the_wire(live):
    with pytest.raises(httpx.RemoteProtocolError):
        httpx.get(f"{live}{P}/timeout/truncated-body")  # declared 1000 bytes, received 100


def test_truncated_body_headers_arrive_before_the_cut(live):
    with httpx.stream("GET", f"{live}{P}/timeout/truncated-body") as response:
        assert response.status_code == 200 and response.headers["content-length"] == "1000"
        received = b""
        with pytest.raises(httpx.RemoteProtocolError):
            for chunk in response.iter_raw():
                received += chunk
        assert len(received) == 100


def test_connection_reset_gives_no_answer_at_all(live):
    with pytest.raises((httpx.RemoteProtocolError, httpx.ReadError)):
        httpx.get(f"{live}{P}/timeout/connection-reset")


def test_a_reset_only_affects_its_own_connection(live):
    with httpx.Client(base_url=live) as other:
        assert other.get("/ok/health").status_code == 200  # an unrelated, open connection
        with pytest.raises((httpx.RemoteProtocolError, httpx.ReadError)):
            httpx.get(f"{live}{P}/timeout/connection-reset")
        assert other.get("/ok/health").status_code == 200  # still alive afterwards
    assert httpx.get(f"{live}/ok/health").status_code == 200  # and the server keeps serving


def test_the_server_survives_repeated_resets_and_truncations(live):
    for _ in range(5):
        with pytest.raises(httpx.HTTPError):
            httpx.get(f"{live}{P}/timeout/connection-reset")
        with pytest.raises(httpx.HTTPError):
            httpx.get(f"{live}{P}/timeout/truncated-body")
    assert httpx.get(f"{live}{P}/health").status_code == 200


def test_slow_body_sends_headers_first_and_then_trickles(live):
    started = time.time()
    with httpx.stream("GET", f"{live}{P}/timeout/slow-body") as response:
        headers_at = time.time() - started
        body = b"".join(response.iter_raw())
    total = time.time() - started
    assert response.status_code == 200 and len(body) == 50 and json.loads(body)["ok"] is True
    assert headers_at < 0.5 * total  # the headers did not wait for the body
    assert total >= 0.05  # 49 waits of 2 ms (0.2 s x 0.01 scale), so it is not instant


def test_hang_outlasts_a_short_client_timeout():
    # A separate server at the default scale: with 0.01 the hang is only 0.3 s, so use a tighter timeout.
    app = create_app(Settings(latency_scale=1))
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        with pytest.raises(httpx.ReadTimeout):
            httpx.get(f"http://127.0.0.1:{port}{P}/timeout/hang", timeout=0.3)  # waits 30 s
        with pytest.raises(httpx.ReadTimeout):
            httpx.get(f"http://127.0.0.1:{port}{P}/timeout/slow-headers", timeout=0.3)  # waits 4 s
        # and the server is still answering other requests while those waits run on
        assert httpx.get(f"http://127.0.0.1:{port}{P}/health", timeout=2).status_code == 200
    finally:
        server.should_exit = True
        thread.join(timeout=5)
