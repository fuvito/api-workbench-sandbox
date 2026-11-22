"""Request-body size limit (CLAUDE.md: bound request body sizes).

Pure ASGI so it also catches bodies without a Content-Length (chunked): the bytes are counted as
the handler reads them. Over the limit the answer is 413 in the same error shape as the rest
(`{"code", "message"}`); it is a protection of the instance, not part of any family's contract, so
no spec declares it. Responses are bounded elsewhere (`/large` is capped at 60 MB, delays in
app/latency.py).
"""

import json

MAX_BODY_BYTES = 1024 * 1024  # 1 MiB: far above anything ClearSignal sends to these fixtures


class BodyTooLarge(Exception):
    pass


class BodyLimit:
    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            return await self.refuse(send)

        seen = 0
        exceeded = False
        started = False

        async def counting_receive():
            nonlocal seen, exceeded
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    exceeded = True
                    raise BodyTooLarge
            return message

        async def tracking_send(message):
            # Frameworks turn a failed body read into their own 400/500: once the limit was
            # crossed, whatever answer the handler produces is replaced by the 413.
            nonlocal started
            if exceeded:
                if message["type"] == "http.response.start" and not started:
                    started = True
                    await self.refuse(send)
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except BodyTooLarge:
            if not started:
                await self.refuse(send)

    async def refuse(self, send):
        body = json.dumps(
            {"code": "payload_too_large", "message": f"the request body is over {self.max_bytes} bytes"}
        ).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                                (b"connection", b"close")]})
        await send({"type": "http.response.body", "body": body})
