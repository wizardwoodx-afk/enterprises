"""Service tests — no LLM, no network, no engine dependencies.

The registry takes an injectable executor precisely so the merge can be verified
on a machine where the engine's third-party deps are not installed.
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from beholders.service.api import BeholdersApi
from beholders.service.models import (
    CrewDefinition,
    EventType,
    Process,
    RunStatus,
)
from beholders.service.rpc import CrewRpc, RpcError, handle_request
from beholders.service.runs import RunRegistry
from beholders.service.store import CrewNotFound, CrewStore

CREW = {
    "name": "Research Desk",
    "description": "scope, gather, write",
    "process": "sequential",
    "agents": [
        {"role": "Researcher", "goal": "find sources"},
        {"role": "Writer", "goal": "write the brief"},
    ],
    "tasks": [
        {"name": "gather", "description": "collect about {topic}", "agent": "Researcher"},
        {"name": "write", "description": "write it up", "agent": "Writer", "context": ["gather"]},
    ],
}


class FakeExecutor:
    """Deterministic stand-in: emits the event shape the engine would."""

    def __init__(self, *, fail: bool = False, delay: float = 0.0, honour_cancel: bool = True):
        self.fail = fail
        self.delay = delay
        self.honour_cancel = honour_cancel

    def kickoff(self, crew, inputs, emit, should_stop):
        for task in crew.tasks:
            if should_stop() and self.honour_cancel:
                raise RuntimeError("stopped")
            emit(EventType.TASK_STARTED, {"task": task.name, "agent": task.agent})
            if self.delay:
                time.sleep(self.delay)
            if self.fail and task is crew.tasks[-1]:
                emit(EventType.TASK_FAILED, {"task": task.name, "error": "boom"})
                raise RuntimeError("boom")
            emit(EventType.TASK_COMPLETED, {"task": task.name, "agent": task.agent, "summary": "ok"})
        return f"done:{','.join(t.name for t in crew.tasks)}"


@pytest.fixture()
def store(tmp_path):
    return CrewStore(tmp_path / "crews")


@pytest.fixture()
def api(store):
    return BeholdersApi(store=store, runs=RunRegistry(executor=FakeExecutor()))


# --------------------------------------------------------------- definitions
def test_crew_round_trips_through_the_store(store):
    created = store.create(CREW)
    assert created.id.startswith("crew_")
    assert [a.role for a in created.agents] == ["Researcher", "Writer"]
    assert created.process is Process.SEQUENTIAL

    reread = store.get(created.id)
    assert reread.to_dict() == created.to_dict()
    assert [c.id for c in store.list()] == [created.id]


def test_crew_rejects_unknown_agent_on_a_task(store):
    bad = {**CREW, "tasks": [{"name": "x", "description": "d", "agent": "Nobody"}]}
    with pytest.raises(ValueError, match="unknown agent"):
        CrewDefinition.from_dict(bad)


def test_crew_rejects_unknown_process(store):
    with pytest.raises(ValueError, match="unknown process"):
        CrewDefinition.from_dict({**CREW, "process": "swarm"})


def test_store_rejects_path_traversal_ids(store):
    with pytest.raises(ValueError):
        store.get("../../etc/passwd")


def test_delete_then_get_raises(store):
    crew = store.create(CREW)
    store.delete(crew.id)
    with pytest.raises(CrewNotFound):
        store.get(crew.id)


def test_malformed_files_do_not_break_the_list(store):
    store.create(CREW)
    (store.root / "broken.json").write_text("{not json", encoding="utf-8")
    assert len(store.list()) == 1


# --------------------------------------------------------------------- runs
def test_run_succeeds_and_records_ordered_events(store):
    runs = RunRegistry(executor=FakeExecutor())
    api = BeholdersApi(store=store, runs=runs)
    crew = store.create(CREW)

    status, payload = api.dispatch("POST", f"/crews/{crew.id}/runs", {"inputs": {"topic": "x"}})
    assert status == 202
    run_id = payload["run"]["id"]
    assert runs.wait(run_id, timeout=5)

    record = runs.get(run_id)
    assert record.status is RunStatus.SUCCEEDED
    assert record.result == "done:gather,write"

    kinds = [e.type for e in record.events]
    assert kinds[0] is EventType.RUN_STARTED
    assert kinds[-1] is EventType.RUN_COMPLETED
    assert kinds.count(EventType.TASK_STARTED) == 2
    assert kinds.count(EventType.TASK_COMPLETED) == 2
    # seq is monotonic and 1-based: a poller can resume from any cursor.
    assert [e.seq for e in record.events] == list(range(1, len(record.events) + 1))


def test_failed_run_captures_the_error(store):
    runs = RunRegistry(executor=FakeExecutor(fail=True))
    crew = store.create(CREW)
    record = runs.start(crew, {})
    assert runs.wait(record.id, timeout=5)
    record = runs.get(record.id)
    assert record.status is RunStatus.FAILED
    assert "boom" in record.error
    assert record.events[-1].type is EventType.RUN_FAILED


def test_cancel_marks_the_run_cancelled(store):
    runs = RunRegistry(executor=FakeExecutor(delay=0.2))
    crew = store.create(CREW)
    record = runs.start(crew, {})
    time.sleep(0.05)
    runs.cancel(record.id)
    assert runs.wait(record.id, timeout=5)
    assert runs.get(record.id).status is RunStatus.CANCELLED


def test_history_cap_drops_only_finished_runs(store):
    runs = RunRegistry(executor=FakeExecutor(), history=2)
    crew = store.create(CREW)
    ids = [runs.start(crew, {}).id for _ in range(4)]
    for run_id in ids:
        runs.wait(run_id, timeout=5)
    assert len(runs.list(limit=10)) <= 2


def test_concurrent_runs_stay_isolated(store):
    runs = RunRegistry(executor=FakeExecutor(delay=0.02))
    crew = store.create(CREW)
    started = [runs.start(crew, {"n": i}) for i in range(5)]
    threads = [threading.Thread(target=runs.wait, args=(r.id, 5)) for r in started]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for r in started:
        got = runs.get(r.id)
        assert got.status is RunStatus.SUCCEEDED
        assert got.events[0].detail["crew_id"] == crew.id


# ----------------------------------------------------------------------- api
def test_health_reports_counts(api, store):
    store.create(CREW)
    status, payload = api.dispatch("GET", "/health")
    assert status == 200
    assert payload["service"] == "beholders"
    assert payload["crew_count"] == 1


def test_blueprints_are_creatable(api):
    status, payload = api.dispatch("GET", "/blueprints")
    assert status == 200 and len(payload["blueprints"]) >= 3
    for blueprint in payload["blueprints"]:
        spec = {k: v for k, v in blueprint.items() if k != "id"}
        crew = CrewDefinition.from_dict(spec)
        assert crew.tasks and crew.agents


def test_create_read_update_delete(api):
    status, payload = api.dispatch("POST", "/crews", CREW)
    assert status == 201
    crew_id = payload["crew"]["id"]

    assert api.dispatch("GET", f"/crews/{crew_id}")[0] == 200

    renamed = {**CREW, "name": "Renamed Desk"}
    status, payload = api.dispatch("PUT", f"/crews/{crew_id}", renamed)
    assert status == 200 and payload["crew"]["name"] == "Renamed Desk"

    assert api.dispatch("DELETE", f"/crews/{crew_id}")[0] == 200
    assert api.dispatch("GET", f"/crews/{crew_id}")[0] == 404


def test_invalid_crew_is_a_400_not_a_crash(api):
    status, payload = api.dispatch("POST", "/crews", {"name": ""})
    assert status == 400
    assert payload["ok"] is False


def test_unknown_route_and_method(api):
    assert api.dispatch("GET", "/nope")[0] == 404
    assert api.dispatch("TRACE", "/crews")[0] == 405


def test_runs_listing_filters_by_crew(store):
    runs = RunRegistry(executor=FakeExecutor())
    api = BeholdersApi(store=store, runs=runs)
    a = store.create(CREW)
    b = store.create({**CREW, "name": "Other"})
    ra = runs.start(a, {})
    rb = runs.start(b, {})
    runs.wait(ra.id, 5)
    runs.wait(rb.id, 5)
    _, payload = api.dispatch("GET", "/runs", {"crew_id": a.id})
    assert [r["id"] for r in payload["runs"]] == [ra.id]


# ----------------------------------------------------------------------- rpc
def test_rpc_envelope_success(store):
    api = BeholdersApi(store=store, runs=RunRegistry(executor=FakeExecutor()))
    rpc = CrewRpc(api)

    created = handle_request(rpc, {"jsonrpc": "2.0", "id": 1, "method": "crew.create", "params": {"crew": CREW}})
    assert created["id"] == 1
    crew_id = created["result"]["crew"]["id"]

    listed = handle_request(rpc, {"jsonrpc": "2.0", "id": 2, "method": "crew.list"})
    assert len(listed["result"]["crews"]) == 1

    run = handle_request(rpc, {"jsonrpc": "2.0", "id": 3, "method": "crew.run", "params": {"crew_id": crew_id}})
    run_id = run["result"]["run"]["id"]
    api.runs.wait(run_id, 5)

    got = handle_request(rpc, {"jsonrpc": "2.0", "id": 4, "method": "crew.runs.get", "params": {"run_id": run_id}})
    assert got["result"]["run"]["status"] == "succeeded"


def test_rpc_unknown_method_and_missing_params(store):
    rpc = CrewRpc(BeholdersApi(store=store, runs=RunRegistry(executor=FakeExecutor())))
    unknown = handle_request(rpc, {"jsonrpc": "2.0", "id": 1, "method": "crew.nope"})
    assert unknown["error"]["code"] == -32601

    missing = handle_request(rpc, {"jsonrpc": "2.0", "id": 2, "method": "crew.get", "params": {}})
    assert missing["error"]["code"] == -32602

    not_found = handle_request(
        rpc, {"jsonrpc": "2.0", "id": 3, "method": "crew.get", "params": {"crew_id": "crew_missing"}}
    )
    assert not_found["error"]["code"] == -32004


def test_rpc_never_leaks_a_stack_on_internal_error(store):
    class Exploding(BeholdersApi):
        def dispatch(self, method, path, body=None):  # noqa: ARG002
            raise RuntimeError("kaboom")

    rpc = CrewRpc(Exploding(store=store))
    response = handle_request(rpc, {"jsonrpc": "2.0", "id": 9, "method": "crew.list"})
    assert response["error"]["code"] == -32603
    assert "kaboom" in response["error"]["message"]
    assert "Traceback" not in json.dumps(response)


def test_rpc_rejects_non_object_params(store):
    rpc = CrewRpc(BeholdersApi(store=store))
    response = handle_request(rpc, {"jsonrpc": "2.0", "id": 1, "method": "crew.list", "params": [1, 2]})
    assert response["error"]["code"] == -32602


# ----------------------------------------------------------------------- cli
def test_cli_lists_crews(monkeypatch, tmp_path, capsys):
    from beholders.service import cli

    monkeypatch.setenv("BEHOLDERS_HOME", str(tmp_path / "home"))
    CrewStore().create(CREW)

    assert cli.main(["crews"]) == 0
    assert "Research Desk" in capsys.readouterr().out


def test_cli_create_from_a_file(monkeypatch, tmp_path, capsys):
    from beholders.service import cli

    monkeypatch.setenv("BEHOLDERS_HOME", str(tmp_path / "home"))
    source = tmp_path / "crew.json"
    source.write_text(json.dumps(CREW), encoding="utf-8")

    assert cli.main(["create", str(source)]) == 0
    assert "Research Desk" in capsys.readouterr().out


def test_cli_run_of_an_unknown_crew_is_a_clean_failure(monkeypatch, tmp_path, capsys):
    from beholders.service import cli

    monkeypatch.setenv("BEHOLDERS_HOME", str(tmp_path / "home"))

    assert cli.main(["run", "crew_missing"]) == 1
    assert "unknown crew" in capsys.readouterr().out


def test_cli_rejects_an_unknown_subcommand():
    from beholders.service import cli

    with pytest.raises(SystemExit):
        cli.main(["frobnicate"])
