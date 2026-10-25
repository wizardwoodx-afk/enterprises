"""ASGI adapter — mount the Beholders service inside the gateway.

The desktop's plugin REST door calls `/api/plugins/beholders/*` on the gateway.
That gateway is not part of this repository, so this module is the contract
between the two: a bare ASGI callable with no framework dependency (no FastAPI,
no Starlette), mountable anywhere an ASGI app goes.

    # in the gateway's app factory
    from beholders.service import BeholdersApi
    from beholders.service.asgi import asgi_app

    api = BeholdersApi()
    app.mount("/api/plugins/beholders", asgi_app(api))

That is the whole integration. The same `BeholdersApi` also backs the JSON-RPC
`crew.*` methods (`service/rpc.py`) and the standalone `beholders serve`
(`service/server.py`), so all three doors agree by construction.

Why hand-rolled ASGI rather than Starlette: the service is mounted into someone
else's app, and a plugin must not drag a second web framework — with its own
version pins and middleware — into that app's import graph.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qs

from .api import BeholdersApi

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

MAX_BODY = 4 * 1024 * 1024

_JSON = [(b"content-type", b"application/json; charset=utf-8")]


async def _read_body(receive: Receive) -> dict[str, Any]:
    chunks: list[bytes] = []
    size = 0

    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            raise ConnectionAbortedError("client disconnected")
        if message["type"] != "http.request":
            continue
        chunk = message.get("body", b"")
        size += len(chunk)
        if size > MAX_BODY:
            raise ValueError("request body too large")
        chunks.append(chunk)
        if not message.get("more_body", False):
            break

    raw = b"".join(chunks)
    if not raw:
        return {}
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("request body must be a JSON object")
    return parsed


async def _send_json(send: Send, status: int, payload: Any) -> None:
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [*_JSON, (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


def asgi_app(api: BeholdersApi | None = None, *, prefix: str = ""):
    """Build an ASGI callable serving the Beholders routes.

    ``prefix`` is the path the app is mounted under when the host passes full
    paths through (`root_path` is honoured too); leave it empty when the host
    strips the mount point, which is what Starlette and friends do.
    """
    service = api or BeholdersApi()

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
            return

        if scope["type"] != "http":
            raise RuntimeError(f"Beholders service does not handle {scope['type']!r}")

        method = scope.get("method", "GET").upper()
        path = scope.get("path") or "/"
        mount = prefix or scope.get("root_path") or ""

        if mount and path.startswith(mount):
            path = path[len(mount):] or "/"

        if method == "OPTIONS":
            await send(
                {
                    "type": "http.response.start",
                    "status": 204,
                    "headers": [
                        (b"access-control-allow-methods", b"GET,POST,PUT,PATCH,DELETE,OPTIONS"),
                        (b"access-control-allow-headers", b"content-type"),
                        (b"access-control-allow-origin", b"*"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return

        try:
            body = await _read_body(receive) if method in ("POST", "PUT", "PATCH", "DELETE") else {}
        except (ValueError, json.JSONDecodeError) as exc:
            await _send_json(send, 400, {"ok": False, "error": f"invalid JSON body: {exc}"})
            return

        # Query params are merged under the body, so `GET /runs?crew_id=x` and
        # `GET /runs` with `{crew_id}` behave identically.
        query = parse_qs(scope.get("query_string", b"").decode("utf-8", "replace"))
        params = {**{k: v[-1] for k, v in query.items()}, **body}

        status, payload = service.dispatch(method, path, params)
        await _send_json(send, status, payload)

    return app


__all__ = ["asgi_app"]
