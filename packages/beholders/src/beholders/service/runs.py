"""Run registry: execute crews, stream their lifecycle, keep the history.

Execution is pluggable. ``EngineExecutor`` drives the real vendored engine; the
tests inject a deterministic fake so the whole service can be exercised without
an LLM, a network call, or any of the engine's third-party dependencies. That
seam is what makes the merge testable.

Cancellation is cooperative: the executor receives a ``should_stop`` callable and
checks it between tasks, which is the only point the engine can be interrupted
safely (a task is an LLM round-trip; killing it mid-call would leave the
provider stream dangling).
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, Protocol

from .models import (
    CrewDefinition,
    EventType,
    RunEvent,
    RunRecord,
    RunStatus,
    new_id,
    now_iso,
)

Emit = Callable[[EventType, dict[str, Any]], None]
ShouldStop = Callable[[], bool]


class CrewNotFoundInStore(KeyError):
    pass


class Executor(Protocol):
    """What the registry needs from whatever actually runs a crew."""

    def kickoff(
        self,
        crew: CrewDefinition,
        inputs: dict[str, Any],
        emit: Emit,
        should_stop: ShouldStop,
    ) -> str:
        """Run the crew and return its final output as text."""
        ...


class RunRegistry:
    """Owns running crews and their event logs."""

    def __init__(self, executor: Executor | None = None, *, history: int = 50) -> None:
        self._executor = executor or EngineExecutor()
        self._lock = threading.Lock()
        self._runs: dict[str, RunRecord] = {}
        self._order: list[str] = []
        self._cancel: dict[str, threading.Event] = {}
        self._done: dict[str, threading.Event] = {}
        self._history = history

    # -- public API ----------------------------------------------------
    def start(self, crew: CrewDefinition, inputs: dict[str, Any] | None = None) -> RunRecord:
        run = RunRecord(id=new_id("run"), crew_id=crew.id, crew_name=crew.name, inputs=inputs or {})
        cancel = threading.Event()
        done = threading.Event()
        with self._lock:
            self._runs[run.id] = run
            self._order.append(run.id)
            self._cancel[run.id] = cancel
            self._done[run.id] = done
            self._trim_locked()
        thread = threading.Thread(
            target=self._execute, args=(run, crew, cancel, done), name=f"beholders-{run.id}", daemon=True
        )
        thread.start()
        return run

    def get(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self._runs.get(run_id)
        if record is None:
            raise KeyError(run_id)
        return record

    def list(self, *, crew_id: str | None = None, limit: int = 50) -> list[RunRecord]:
        with self._lock:
            ids = list(reversed(self._order))
        out: list[RunRecord] = []
        for run_id in ids:
            record = self._runs.get(run_id)
            if record is None:
                continue
            if crew_id and record.crew_id != crew_id:
                continue
            out.append(record)
            if len(out) >= limit:
                break
        return out

    def cancel(self, run_id: str) -> RunRecord:
        record = self.get(run_id)
        with self._lock:
            flag = self._cancel.get(run_id)
        if flag is not None:
            flag.set()
        return record

    def wait(self, run_id: str, timeout: float = 30.0) -> bool:
        """Block until the run finishes. Returns False on timeout. Test/CLI aid."""
        with self._lock:
            done = self._done.get(run_id)
        return bool(done and done.wait(timeout))

    # -- internals -----------------------------------------------------
    def _emit(self, run: RunRecord, event_type: EventType, detail: dict[str, Any]) -> None:
        with self._lock:
            run.events.append(
                RunEvent(seq=len(run.events) + 1, at=now_iso(), type=event_type, detail=detail)
            )

    def _execute(
        self,
        run: RunRecord,
        crew: CrewDefinition,
        cancel: threading.Event,
        done: threading.Event,
    ) -> None:
        run.status = RunStatus.RUNNING
        self._emit(
            run,
            EventType.RUN_STARTED,
            {"crew_id": crew.id, "process": crew.process.value, "agents": [a.role for a in crew.agents]},
        )
        try:
            output = self._executor.kickoff(
                crew, run.inputs, lambda t, d: self._emit(run, t, d), cancel.is_set
            )
        except BaseException as exc:  # noqa: BLE001 - surfaced to the UI verbatim
            if cancel.is_set():
                run.status = RunStatus.CANCELLED
                run.error = "cancelled"
                self._emit(run, EventType.RUN_CANCELLED, {"reason": "cancelled by user"})
            else:
                run.status = RunStatus.FAILED
                run.error = f"{type(exc).__name__}: {exc}"
                self._emit(run, EventType.RUN_FAILED, {"error": run.error})
        else:
            if cancel.is_set():
                run.status = RunStatus.CANCELLED
                self._emit(run, EventType.RUN_CANCELLED, {"reason": "cancelled by user"})
            else:
                run.status = RunStatus.SUCCEEDED
                run.result = output
                self._emit(run, EventType.RUN_COMPLETED, {"result": output})
        finally:
            run.finished_at = now_iso()
            done.set()

    def _trim_locked(self) -> None:
        """Drop the oldest finished runs past the history cap. Caller holds the lock."""
        if len(self._order) <= self._history:
            return
        for run_id in list(self._order):
            if len(self._order) <= self._history:
                break
            record = self._runs.get(run_id)
            if record is not None and not record.status.terminal:
                continue
            self._order.remove(run_id)
            self._runs.pop(run_id, None)
            self._cancel.pop(run_id, None)
            self._done.pop(run_id, None)


class EngineExecutor:
    """Drives the vendored Beholders engine.

    Imports are deferred to ``kickoff`` so the service, its REST layer and its
    tests run on a machine without the engine's heavier dependencies installed —
    the UI then shows a precise error instead of the whole plugin failing to load.
    """

    def kickoff(
        self,
        crew: CrewDefinition,
        inputs: dict[str, Any],
        emit: Emit,
        should_stop: ShouldStop,
    ) -> str:
        try:
            from beholders import Agent, Crew, Process as EngineProcess, Task
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "the Beholders engine is not importable "
                f"({exc}). Install it with: pip install -e packages/beholders"
            ) from exc

        agents: dict[str, Any] = {}
        for spec in crew.agents:
            agents[spec.role] = Agent(
                role=spec.role,
                goal=spec.goal or f"Complete {crew.name} work as {spec.role}.",
                backstory=spec.backstory or f"An experienced {spec.role}.",
                allow_delegation=spec.allow_delegation,
                max_iter=spec.max_iter,
                verbose=spec.verbose,
                tools=[],
            )

        tasks: dict[str, Any] = {}
        for spec in crew.tasks:
            tasks[spec.name] = Task(
                description=spec.description,
                expected_output=spec.expected_output or "A complete, useful result.",
                agent=agents.get(spec.agent) if spec.agent else None,
                context=[tasks[c] for c in spec.context if c in tasks],
                output_file=spec.output_file or None,
            )

        def task_callback(output: Any) -> None:
            name = getattr(output, "name", "") or ""
            emit(
                EventType.TASK_COMPLETED,
                {
                    "task": name,
                    "agent": getattr(output, "agent", "") or "",
                    "summary": str(getattr(output, "raw", "") or "")[:400],
                },
            )

        def step_callback(step: Any) -> None:
            if should_stop():
                raise _Cancelled()
            emit(
                EventType.LOG,
                {
                    "task": getattr(step, "name", "") or "",
                    "agent": getattr(step, "agent", "") or "",
                    "detail": str(getattr(step, "output", "") or "")[:400],
                },
            )

        hierarchical = crew.process.value == "hierarchical"
        manager = None
        workers = list(agents.values())
        if hierarchical:
            # The engine refuses a hierarchical crew without a manager, and
            # refuses one that also appears in `agents`. A definition therefore
            # names its lead via `manager_role` and that role steps OUT of the
            # worker list — "Review Lead" delegates to the specialists, it does
            # not also work the queue.
            role = crew.manager_role or crew.agents[0].role
            manager = agents.get(role)
            if manager is None:
                raise RuntimeError(f"manager_role {role!r} is not one of this crew's agents")
            workers = [a for r, a in agents.items() if r != role]
            if not workers:
                raise RuntimeError(
                    f"hierarchical crew {crew.name!r} has no workers left after "
                    f"removing manager {role!r}; add at least one other agent"
                )

        engine_crew = Crew(
            agents=workers,
            tasks=list(tasks.values()),
            process=EngineProcess.hierarchical if hierarchical else EngineProcess.sequential,
            manager_agent=manager,
            task_callback=task_callback,
            step_callback=step_callback,
            verbose=False,
        )

        for spec in crew.tasks:
            emit(EventType.TASK_STARTED, {"task": spec.name, "agent": spec.agent})
            if should_stop():
                raise _Cancelled()

        result = engine_crew.kickoff(inputs=inputs or {})
        return str(getattr(result, "raw", result))


class _Cancelled(RuntimeError):
    """Internal: raised inside the engine callbacks to unwind a cancelled run."""
