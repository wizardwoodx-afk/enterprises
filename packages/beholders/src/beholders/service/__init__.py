"""The Beholders service: the bridge between the engine and Beyond's surfaces.

Three doors onto one set of handlers:

* :mod:`beholders.service.api`    — mount-relative REST (desktop plugin router)
* :mod:`beholders.service.server` — stdlib HTTP adapter for ``beholders serve``
* :mod:`beholders.service.rpc`    — ``crew.*`` JSON-RPC methods on the gateway
"""
from __future__ import annotations

from .api import BLUEPRINTS, BeholdersApi, Response
from .models import (
    AgentSpec,
    CrewDefinition,
    EventType,
    Process,
    RunEvent,
    RunRecord,
    RunStatus,
    TaskSpec,
)
from .runs import EngineExecutor, Executor, RunRegistry
from .store import CrewNotFound, CrewStore, default_home

__all__ = [
    "AgentSpec",
    "BLUEPRINTS",
    "BeholdersApi",
    "CrewDefinition",
    "CrewNotFound",
    "CrewStore",
    "EngineExecutor",
    "EventType",
    "Executor",
    "Process",
    "Response",
    "RunEvent",
    "RunRecord",
    "RunRegistry",
    "RunStatus",
    "TaskSpec",
    "default_home",
]
