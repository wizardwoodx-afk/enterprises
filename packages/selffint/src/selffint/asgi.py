"""ASGI adapter — mount SelfFint inside the Beyond gateway.

    from selffint import SelfFintApi, asgi_app

    app.mount("/api/plugins/self-fint", asgi_app(SelfFintApi()))

Hand-rolled on purpose: this package is mounted into someone else's app and must
not add a second web framework (or a second HTTP client) to that app's import
graph. Body cap, JSON in, JSON out, and every failure as a payload.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from .api import SelfFintApi

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
    try:
        parsed = json.loads(raw)
    except ValueError as error:
        raise ValueError(f"body is not JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise ValueError("body must be a JSON object")
    return parsed


async def _send_json(send: Send, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, default=str).encode()
    await send(
        {
            "type": "http.response.start",
            "status": int(status),
            "headers": [*_JSON, (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


def asgi_app(api: SelfFintApi) -> Callable[[Scope, Receive, Send], Awaitable[None]]:
    """Return a bare ASGI callable. `path` is taken verbatim: mount it under
    ``/api/plugins/self-fint`` and every route below is relative."""

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            raise RuntimeError(f"unsupported ASGI scope: {scope.get('type')}")
        try:
            body = await _read_body(receive) if scope.get("method") in {"POST", "PUT", "PATCH"} else {}
        except (ConnectionAbortedError, ValueError) as error:
            await _send_json(send, 400, {"ok": False, "error": str(error)})
            return

        status, payload = api.dispatch(scope.get("method", "GET"), scope.get("path", "/"), body)
        await _send_json(send, status, payload)

    return app
