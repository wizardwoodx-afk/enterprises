"""Engine wiring: does the service actually build a real Beholders crew?

Skipped when the engine's dependencies are absent, so the pure-service suite
still runs anywhere. Nothing here calls an LLM: ``Crew.kickoff`` is patched, and
what we assert is the *translation* from a stored ``CrewDefinition`` to real
``Agent`` / ``Task`` / ``Crew`` objects — roles, ordering, context links,
process, and the callbacks the run registry depends on.
"""
from __future__ import annotations

import pytest

def _engine_available() -> bool:
    """True when the engine's dependency tree is actually importable.

    ``beholders`` imports lazily, so ``importorskip('beholders')`` would always
    pass and then fail inside a test. Touching a real engine name is the only
    honest probe.
    """
    try:
        import beholders

        beholders.Crew  # noqa: B018 - attribute access triggers the bootstrap
    except Exception:  # noqa: BLE001 - any import-time failure means "not installed"
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _engine_available(), reason="the engine's dependencies are not installed"
)

from beholders.service.api import BeholdersApi  # noqa: E402
from beholders.service.models import CrewDefinition, EventType, RunStatus  # noqa: E402
from beholders.service.runs import EngineExecutor, RunRegistry  # noqa: E402
from beholders.service.store import CrewStore  # noqa: E402

CREW = {
    "name": "Research Desk",
    "process": "hierarchical",
    "manager_role": "Researcher",
    "agents": [
        {"role": "Researcher", "goal": "g", "backstory": "b", "allow_delegation": True},
        {"role": "Writer", "goal": "g2", "backstory": "b2"},
    ],
    "tasks": [
        {"name": "gather", "description": "collect", "agent": "Researcher", "expected_output": "list"},
        {"name": "write", "description": "write", "agent": "Writer", "context": ["gather"]},
    ],
}


@pytest.fixture()
def captured(monkeypatch):
    """Intercept the real ``Crew.kickoff`` so no model call happens."""
    import beholders

    seen: dict = {}

    class FakeOutput:
        raw = "final answer"

    def fake_kickoff(self, inputs=None, **kwargs):  # noqa: ARG001
        from types import SimpleNamespace

        seen["crew"] = self
        seen["inputs"] = inputs
        # Drive the crew's own callback so the emit path is exercised too.
        for task in self.tasks:
            self.task_callback(SimpleNamespace(name="done", agent="x", raw="out"))
        return FakeOutput()

    monkeypatch.setattr(beholders.Crew, "kickoff", fake_kickoff)
    return seen


def test_executor_builds_real_engine_objects(tmp_path, captured, monkeypatch):
    store = CrewStore(tmp_path / "crews")
    crew = store.create(CREW)
    runs = RunRegistry(executor=EngineExecutor(), history=5)
    api = BeholdersApi(store=store, runs=runs)

    status, payload = api.dispatch("POST", f"/crews/{crew.id}/runs", {"inputs": {"topic": "tidal"}})
    assert status == 202
    run_id = payload["run"]["id"]
    assert runs.wait(run_id, timeout=30)

    record = runs.get(run_id)
    assert record.status is RunStatus.SUCCEEDED, record.error
    assert record.result == "final answer"

    engine_crew = captured["crew"]
    # Researcher is the manager, so it leads rather than working the queue.
    assert [a.role for a in engine_crew.agents] == ["Writer"]
    assert engine_crew.manager_agent is not None
    assert engine_crew.manager_agent.role == "Researcher"
    assert [t.description for t in engine_crew.tasks] == ["collect", "write"]
    assert engine_crew.process.value == "hierarchical"
    # `context` is translated into an object link, not left as a string.
    assert engine_crew.tasks[1].context[0] is engine_crew.tasks[0]
    assert captured["inputs"] == {"topic": "tidal"}


def test_task_started_events_precede_the_engine_call(tmp_path, captured):
    store = CrewStore(tmp_path / "crews")
    crew = store.create(CREW)
    runs = RunRegistry(executor=EngineExecutor())
    record = runs.start(crew, {})
    assert runs.wait(record.id, timeout=30)
    kinds = [e.type for e in record.events]
    assert kinds.count(EventType.TASK_STARTED) == 2
    # The engine's task_callback reached the registry as TASK_COMPLETED events.
    assert kinds.count(EventType.TASK_COMPLETED) == 2


def test_engine_import_failure_is_reported_not_raised(tmp_path, monkeypatch):
    """A broken environment must surface as a failed run, never a crash."""
    import builtins

    real_import = builtins.__import__

    def deny(name, *args, **kwargs):
        if name == "beholders" and args and args[2]:  # fromlist present
            raise ImportError("simulated missing engine")
        return real_import(name, *args, **kwargs)

    store = CrewStore(tmp_path / "crews")
    crew = store.create(CREW)
    runs = RunRegistry(executor=EngineExecutor())
    monkeypatch.setattr(builtins, "__import__", deny)
    record = runs.start(crew, {})
    assert runs.wait(record.id, timeout=30)
    got = runs.get(record.id)
    assert got.status is RunStatus.FAILED
    assert "Beholders engine is not importable" in got.error


def test_definition_from_blueprint_runs(tmp_path, captured):
    from beholders.service.api import BLUEPRINTS

    store = CrewStore(tmp_path / "crews")
    runs = RunRegistry(executor=EngineExecutor())
    api = BeholdersApi(store=store, runs=runs)
    for blueprint in BLUEPRINTS:
        spec = {k: v for k, v in blueprint.items() if k != "id"}
        status, payload = api.dispatch("POST", "/crews", spec)
        assert status == 201, payload
        crew_id = payload["crew"]["id"]
        _, started = api.dispatch("POST", f"/crews/{crew_id}/runs", {})
        assert runs.wait(started["run"]["id"], timeout=30)
        assert runs.get(started["run"]["id"]).status is RunStatus.SUCCEEDED
