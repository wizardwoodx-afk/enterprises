"""Wire models for the Beholders crew service.

These mirror the shared TypeScript contract in
``apps/shared/src/crew-contract.ts`` — keep the two in step. Every model is a
plain dataclass with ``to_dict`` so the service stays dependency-free: the REST
layer, the JSON-RPC adapter and the tests all speak the same dict shapes.

Vocabulary note: ``Crew``, ``Agent``, ``Task``, ``Flow`` and ``kickoff`` are the
engine's domain API and are deliberately **not** renamed. Only the product name
moved (see ``docs/BEHOLDERS.md``).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


def now_iso() -> str:
    """UTC timestamp, second precision — matches the desktop's ISO handling."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class Process(str, Enum):
    """Execution strategy for a crew. Mirrors the engine's ``Process`` enum."""

    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED)


class EventType(str, Enum):
    """Lifecycle events a run emits. The pane renders these as a timeline."""

    RUN_STARTED = "crew.run.started"
    TASK_STARTED = "crew.task.started"
    TASK_COMPLETED = "crew.task.completed"
    TASK_FAILED = "crew.task.failed"
    LOG = "crew.log"
    RUN_COMPLETED = "crew.run.completed"
    RUN_FAILED = "crew.run.failed"
    RUN_CANCELLED = "crew.run.cancelled"


@dataclass(frozen=True)
class AgentSpec:
    """One role in the crew: who does the work."""

    role: str
    goal: str = ""
    backstory: str = ""
    tools: tuple[str, ...] = ()
    allow_delegation: bool = False
    max_iter: int = 15
    verbose: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentSpec:
        role = str(data.get("role") or "").strip()
        if not role:
            raise ValueError("agent.role is required")
        return cls(
            role=role,
            goal=str(data.get("goal") or ""),
            backstory=str(data.get("backstory") or ""),
            tools=tuple(str(t) for t in (data.get("tools") or ())),
            allow_delegation=bool(data.get("allow_delegation", False)),
            max_iter=int(data.get("max_iter", 15)),
            verbose=bool(data.get("verbose", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "tools": list(self.tools),
            "allow_delegation": self.allow_delegation,
            "max_iter": self.max_iter,
            "verbose": self.verbose,
        }


@dataclass(frozen=True)
class TaskSpec:
    """One unit of work: what gets done, and by which role."""

    name: str
    description: str
    expected_output: str = ""
    agent: str = ""
    # Names of earlier tasks whose output feeds this one.
    context: tuple[str, ...] = ()
    output_file: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskSpec:
        name = str(data.get("name") or "").strip()
        description = str(data.get("description") or "").strip()
        if not name:
            raise ValueError("task.name is required")
        if not description:
            raise ValueError(f"task {name!r}: description is required")
        return cls(
            name=name,
            description=description,
            expected_output=str(data.get("expected_output") or ""),
            agent=str(data.get("agent") or ""),
            context=tuple(str(c) for c in (data.get("context") or ())),
            output_file=str(data.get("output_file") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "expected_output": self.expected_output,
            "agent": self.agent,
            "context": list(self.context),
            "output_file": self.output_file,
        }


@dataclass(frozen=True)
class CrewDefinition:
    """A reusable team: agents + tasks + process."""

    id: str
    name: str
    agents: tuple[AgentSpec, ...]
    tasks: tuple[TaskSpec, ...]
    description: str = ""
    process: Process = Process.SEQUENTIAL
    manager_role: str = ""
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrewDefinition:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("crew.name is required")
        agents = tuple(AgentSpec.from_dict(a) for a in (data.get("agents") or ()))
        tasks = tuple(TaskSpec.from_dict(t) for t in (data.get("tasks") or ()))
        if not agents:
            raise ValueError("a crew needs at least one agent")
        if not tasks:
            raise ValueError("a crew needs at least one task")
        roles = {a.role for a in agents}
        for task in tasks:
            if task.agent and task.agent not in roles:
                raise ValueError(
                    f"task {task.name!r} is assigned to unknown agent {task.agent!r}"
                )
        try:
            process = Process(str(data.get("process") or "sequential"))
        except ValueError as exc:
            raise ValueError(
                f"unknown process {data.get('process')!r}; expected one of "
                f"{', '.join(p.value for p in Process)}"
            ) from exc
        manager_role = str(data.get("manager_role") or "")
        if manager_role and manager_role not in roles:
            raise ValueError(f"manager_role {manager_role!r} is not one of this crew's agents")
        return cls(
            id=str(data.get("id") or new_id("crew")),
            name=name,
            agents=agents,
            tasks=tasks,
            description=str(data.get("description") or ""),
            process=process,
            manager_role=manager_role,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "process": self.process.value,
            "manager_role": self.manager_role,
            "agents": [a.to_dict() for a in self.agents],
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def summary(self) -> dict[str, Any]:
        """List-view shape: enough to render a card without the full body."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "process": self.process.value,
            "agent_count": len(self.agents),
            "task_count": len(self.tasks),
            "roles": [a.role for a in self.agents],
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class RunEvent:
    """One timeline entry. ``seq`` is monotonic per run, so a poller can resume."""

    seq: int
    at: str
    type: EventType
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"seq": self.seq, "at": self.at, "type": self.type.value, **self.detail}


@dataclass
class RunRecord:
    """A single execution of a crew."""

    id: str
    crew_id: str
    crew_name: str
    status: RunStatus = RunStatus.QUEUED
    started_at: str = field(default_factory=now_iso)
    finished_at: str | None = None
    result: str = ""
    error: str = ""
    events: list[RunEvent] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_events: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "crew_id": self.crew_id,
            "crew_name": self.crew_name,
            "status": self.status.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
            "event_count": len(self.events),
            "inputs": self.inputs,
        }
        if include_events:
            payload["events"] = [e.to_dict() for e in self.events]
        return payload

    def summary(self) -> dict[str, Any]:
        return self.to_dict(include_events=False)
