"""Access to the live uvicorn server, for the transport-level cases (a connection reset).

The ASGI interface never exposes the socket, so a case that must drop a connection without
answering needs the server object. `app/__main__.py` stores it here; each connection knows its
client address, which is how a handler finds its own connection. When the app runs without a real
server (the in-process test client) there is nothing to abort and `abort_connection` returns False.

Only the connection that carried the current request is touched; nothing else is reachable from here.
"""

from typing import Any

server: Any = None  # the uvicorn.Server, set by `python -m app`


def abort_connection(client: tuple[str, int] | None) -> bool:
    """Abort (TCP reset) the connection whose peer is `client`. True if one was found."""
    if server is None or client is None:
        return False
    for protocol in list(server.server_state.connections):
        if getattr(protocol, "client", None) == tuple(client):
            protocol.transport.abort()
            return True
    return False
