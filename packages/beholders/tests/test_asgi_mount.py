"""The mount contract: the gateway serves the same handlers the plugin calls.

The gateway itself is not in this checkout, so the thing worth testing is the
adapter — that a bare ASGI mount under `/api/plugins/beholders` answers exactly
the requests `apps/desktop/src/plugins/beholders/api.ts` sends.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from beholders.service.api import BeholdersApi
from beholders.service.asgi import asgi_app
from beholders.service.runs import RunRegistry
from beholders.service.store import CrewStore

MOUNT = "/api/plugins/beholders"


class FakeExecutor:
    def kickoff(self, crew, inputs, emit, should_stop):  # noqa: ARG002
        return "ok"


def call(app, method: str, path: str, body: dict | None = None, query: str = ""):
    """One request through the ASGI app; returns (status, payload)."""
    raw = json.dumps(body).encode() if body is not None else b""
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query.encode(),
        "root_path": "",
        "headers": [(b"content-type", b"application/json")],
    }
    sent: list[dict] = []
    received = False

    async def receive():
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": raw, "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))

    start = next(m for m in sent if m["type"] == "http.response.start")
    payload = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], json.loads(payload or b"{}")


@pytest.fixture()
def app(tmp_path):
    api = BeholdersApi(store=CrewStore(tmp_path / "crews"), runs=RunRegistry(executor=FakeExecutor()))
    return asgi_app(api, prefix=MOUNT), api


CREW = {
    "name": "Desk",
    "process": "sequential",
    "agents": [{"role": "Researcher"}],
    "tasks": [{"name": "gather", "description": "d", "agent": "Researcher"}],
}


def test_health_under_the_mount_path(app):
    server, _ = app
    status, payload = call(server, "GET", f"{MOUNT}/health")
    assert status == 200
    assert payload["service"] == "beholders"


def test_create_then_list_through_the_mount(app):
    server, api = app
    status, payload = call(server, "POST", f"{MOUNT}/crews", CREW)
    assert status == 201
    crew_id = payload["crew"]["id"]

    status, listed = call(server, "GET", f"{MOUNT}/crews")
    assert status == 200
    assert [c["id"] for c in listed["crews"]] == [crew_id]

    status, payload = call(server, "POST", f"{MOUNT}/crews/{crew_id}/runs", {"inputs": {}})
    assert status == 202
    api.runs.wait(payload["run"]["id"], timeout=5)

    status, payload = call(server, "GET", f"{MOUNT}/runs/{payload['run']['id']}")
    assert status == 200
    assert payload["run"]["status"] == "succeeded"


def test_query_strings_reach_the_handlers(app):
    server, api = app
    crew_id = call(server, "POST", f"{MOUNT}/crews", CREW)[1]["crew"]["id"]
    run_id = call(server, "POST", f"{MOUNT}/crews/{crew_id}/runs", {"inputs": {}})[1]["run"]["id"]
    api.runs.wait(run_id, timeout=5)

    status, payload = call(server, "GET", f"{MOUNT}/runs", query=f"crew_id={crew_id}")
    assert status == 200
    assert [r["id"] for r in payload["runs"]] == [run_id]

    status, payload = call(server, "GET", f"{MOUNT}/runs", query="crew_id=crew_other")
    assert payload["runs"] == []


def test_unknown_route_is_a_json_404_not_an_html_page(app):
    server, _ = app
    status, payload = call(server, "GET", f"{MOUNT}/nope")
    assert status == 404
    assert payload["ok"] is False


def test_malformed_body_is_400(app):
    server, _ = app
    scope = {
        "type": "http",
        "method": "POST",
        "path": f"{MOUNT}/crews",
        "query_string": b"",
        "root_path": "",
        "headers": [],
    }
    sent: list[dict] = []
    received = False

    async def receive():
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": b"{not json", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(server(scope, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 400


def test_root_path_is_honoured_when_the_host_does_not_strip_it(tmp_path):
    api = BeholdersApi(store=CrewStore(tmp_path / "crews"), runs=RunRegistry(executor=FakeExecutor()))
    bare = asgi_app(api)  # no prefix: rely on root_path, as Starlette passes it

    scope = {
        "type": "http",
        "method": "GET",
        "path": f"{MOUNT}/health",
        "root_path": MOUNT,
        "query_string": b"",
        "headers": [],
    }
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(bare(scope, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 200


def test_lifespan_is_answered(tmp_path):
    api = BeholdersApi(store=CrewStore(tmp_path / "crews"))
    server = asgi_app(api)
    sent: list[dict] = []
    events = iter([{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}])

    async def receive():
        return next(events)

    async def send(message):
        sent.append(message)

    asyncio.run(server({"type": "lifespan"}, receive, send))
    assert [m["type"] for m in sent] == ["lifespan.startup.complete", "lifespan.shutdown.complete"]


def test_preflight_is_allowed_for_the_plugin_origin(app):
    server, _ = app
    status, _ = call(server, "OPTIONS", f"{MOUNT}/crews")
    assert status == 204
