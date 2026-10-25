"""The ASGI adapter, driven the way a gateway drives it.

No Starlette, no TestClient: the point of `asgi_app` is that it is a bare ASGI
callable, so the test speaks ASGI directly. If this passes, mounting it in
someone else's app works.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from selffint.api import SelfFintApi
from selffint.asgi import MAX_BODY, asgi_app
from selffint.store import MirrorStore


def call(app, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    raw = b"" if body is None else json.dumps(body).encode()
    sent: list[dict] = []
    received = {"done": False}

    async def receive() -> dict:
        if received["done"]:
            return {"type": "http.disconnect"}
        received["done"] = True
        return {"type": "http.request", "body": raw, "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    asyncio.run(app({"type": "http", "method": method, "path": path}, receive, send))
    start = next(message for message in sent if message["type"] == "http.response.start")
    payload = b"".join(
        message.get("body", b"") for message in sent if message["type"] == "http.response.body"
    )
    return start["status"], json.loads(payload or b"{}")


@pytest.fixture()
def app():
    store = MirrorStore(":memory:")
    yield asgi_app(SelfFintApi(store))
    store.close()


def test_get_health(app):
    status, payload = call(app, "GET", "/health")
    assert status == 200 and payload["ok"] is True


def test_get_status_seeds_and_reports(app):
    status, payload = call(app, "GET", "/status")
    assert status == 200 and payload["site"]["mode"] == "demo"


def test_post_body_is_parsed(app):
    status, payload = call(app, "POST", "/invoices", {
        "customer": "Acme Textiles",
        "items": [{"description": "Work", "qty": 1, "rate": 1000}],
    })
    assert status == 201 and payload["document"]["docstatus"] == 0


def test_a_non_json_body_is_a_400_payload(app):
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"not json", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(app({"type": "http", "method": "POST", "path": "/invoices"}, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    body = json.loads(next(m for m in sent if m["type"] == "http.response.body")["body"])
    assert start["status"] == 400 and body["ok"] is False


def test_an_oversized_body_is_refused(app):
    async def receive():
        return {"type": "http.request", "body": b"x" * (MAX_BODY + 1), "more_body": False}

    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    asyncio.run(app({"type": "http", "method": "POST", "path": "/invoices"}, receive, send))
    assert next(m for m in sent if m["type"] == "http.response.start")["status"] == 400


def test_unknown_path_is_404_with_json(app):
    status, payload = call(app, "GET", "/nope")
    assert status == 404 and payload["ok"] is False


def test_responses_are_json_and_carry_a_length(app):
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(app({"type": "http", "method": "GET", "path": "/status"}, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    headers = dict(start["headers"])
    assert headers[b"content-type"] == b"application/json; charset=utf-8"
    body = next(m for m in sent if m["type"] == "http.response.body")["body"]
    assert int(headers[b"content-length"]) == len(body)


def test_a_non_http_scope_is_rejected(app):
    with pytest.raises(RuntimeError):
        asyncio.run(app({"type": "websocket"}, None, None))
