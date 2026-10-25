"""Framework-agnostic request handling for the Beholders service.

Deliberately not a web framework: ``dispatch`` maps a method + path + body to a
``(status, payload)`` tuple. That keeps the surface testable as plain Python,
and lets the very same handler back three doors:

* the desktop plugin's REST router  (``/api/plugins/beholders/...``)
* the standalone ``beholders serve`` HTTP adapter  (``server.py``)
* the gateway's JSON-RPC ``crew.*`` methods  (``rpc.py``)

Paths are matched relative to the mount point, so nothing here needs to know
where it is mounted.
"""
from __future__ import annotations

import re
from typing import Any

from .models import CrewDefinition, Process, RunStatus
from .runs import RunRegistry
from .store import CrewNotFound, CrewStore

Response = tuple[int, dict[str, Any]]

_CREW_RUNS = re.compile(r"^/crews/(?P<id>[^/]+)/runs$")
_CREW_ONE = re.compile(r"^/crews/(?P<id>[^/]+)$")
_RUN_ONE = re.compile(r"^/runs/(?P<id>[^/]+)$")
_RUN_CANCEL = re.compile(r"^/runs/(?P<id>[^/]+)/cancel$")


BLUEPRINTS: tuple[dict[str, Any], ...] = (
    {
        "id": "blueprint.research-desk",
        "name": "Research Desk",
        "description": "Scope a question, gather evidence, then write the brief.",
        "process": "sequential",
        "agents": [
            {
                "role": "Researcher",
                "goal": "Find primary sources and separate fact from claim.",
                "backstory": "A patient investigator who cites everything.",
            },
            {
                "role": "Analyst",
                "goal": "Turn raw findings into a defensible argument.",
                "backstory": "A skeptic who names the weakest link in any case.",
            },
            {
                "role": "Writer",
                "goal": "Produce a brief a busy reader can act on.",
                "backstory": "An editor who cuts anything that does not earn its line.",
            },
        ],
        "tasks": [
            {
                "name": "gather",
                "description": "Collect evidence about {topic}. Note sources and dates.",
                "expected_output": "A bulleted evidence list with citations.",
                "agent": "Researcher",
            },
            {
                "name": "analyze",
                "description": "Weigh the evidence for {topic}. Name the strongest and weakest claims.",
                "expected_output": "An argument outline with confidence levels.",
                "agent": "Analyst",
                "context": ["gather"],
            },
            {
                "name": "write",
                "description": "Write the brief on {topic} for an executive audience.",
                "expected_output": "Markdown, under 600 words, with a recommendation.",
                "agent": "Writer",
                "context": ["analyze"],
            },
        ],
    },
    {
        "id": "blueprint.code-review",
        "name": "Code Review Board",
        "description": "A hierarchical review: a lead delegates to specialists.",
        "process": "hierarchical",
        "manager_role": "Review Lead",
        "agents": [
            {
                "role": "Review Lead",
                "goal": "Route the diff to the right specialist and reconcile their findings.",
                "backstory": "A staff engineer known for blunt, useful reviews.",
                "allow_delegation": True,
            },
            {
                "role": "Security Reviewer",
                "goal": "Find injection, auth and secret-handling defects.",
                "backstory": "A pentester who reads every diff as hostile input.",
            },
            {
                "role": "Performance Reviewer",
                "goal": "Find needless work on the hot path.",
                "backstory": "Someone who has been paged at 3am by an N+1 query.",
            },
        ],
        "tasks": [
            {
                "name": "review",
                "description": "Review the change described here: {diff}. Cite file and line.",
                "expected_output": "Findings grouped by severity, each with a concrete fix.",
                "agent": "Review Lead",
            },
        ],
    },
    {
        "id": "blueprint.release-notes",
        "name": "Release Notes",
        "description": "Turn a commit range into notes a user can read.",
        "process": "sequential",
        "agents": [
            {
                "role": "Historian",
                "goal": "Reconstruct what changed and why.",
                "backstory": "Reads commit archaeology for fun.",
            },
            {
                "role": "Technical Writer",
                "goal": "Explain the change in the user's language, not the implementer's.",
                "backstory": "Deletes jargon on sight.",
            },
        ],
        "tasks": [
            {
                "name": "collect",
                "description": "Summarise the changes in {range}.",
                "expected_output": "Grouped change list (added / changed / fixed).",
                "agent": "Historian",
            },
            {
                "name": "publish",
                "description": "Write user-facing release notes from the change list.",
                "expected_output": "Markdown release notes with a one-line headline.",
                "agent": "Technical Writer",
                "context": ["collect"],
            },
        ],
    },
)


def _error(status: int, message: str) -> Response:
    return status, {"ok": False, "error": message}


class BeholdersApi:
    """All Beholders routes, mount-relative."""

    def __init__(self, store: CrewStore | None = None, runs: RunRegistry | None = None) -> None:
        self.store = store or CrewStore()
        self.runs = runs or RunRegistry()

    # -- entry point ---------------------------------------------------
    def dispatch(self, method: str, path: str, body: dict[str, Any] | None = None) -> Response:
        method = method.upper()
        path = "/" + path.strip("/")
        body = body or {}

        if path == "/health":
            return 200, {
                "ok": True,
                "service": "beholders",
                "crew_count": len(self.store.list()),
                "active_runs": sum(
                    1 for r in self.runs.list(limit=200) if not r.status.terminal
                ),
            }
        if path == "/blueprints":
            return 200, {"ok": True, "blueprints": [dict(b) for b in BLUEPRINTS]}

        if path == "/crews":
            if method == "GET":
                return 200, {"ok": True, "crews": [c.summary() for c in self.store.list()]}
            if method == "POST":
                return self._create(body)
            return _error(405, f"{method} /crews is not allowed")

        if match := _CREW_RUNS.match(path):
            if method != "POST":
                return _error(405, f"{method} {path} is not allowed")
            return self._start_run(match["id"], body)

        if match := _CREW_ONE.match(path):
            crew_id = match["id"]
            if method == "GET":
                return self._read(crew_id)
            if method in ("PUT", "PATCH"):
                return self._update(crew_id, body)
            if method == "DELETE":
                return self._delete(crew_id)
            return _error(405, f"{method} {path} is not allowed")

        if path == "/runs":
            if method != "GET":
                return _error(405, f"{method} /runs is not allowed")
            crew_id = body.get("crew_id") or None
            limit = int(body.get("limit") or 50)
            return 200, {
                "ok": True,
                "runs": [r.summary() for r in self.runs.list(crew_id=crew_id, limit=limit)],
            }

        if match := _RUN_CANCEL.match(path):
            if method != "POST":
                return _error(405, f"{method} {path} is not allowed")
            try:
                record = self.runs.cancel(match["id"])
            except KeyError:
                return _error(404, f"unknown run {match['id']!r}")
            return 200, {"ok": True, "run": record.summary()}

        if match := _RUN_ONE.match(path):
            if method != "GET":
                return _error(405, f"{method} {path} is not allowed")
            try:
                record = self.runs.get(match["id"])
            except KeyError:
                return _error(404, f"unknown run {match['id']!r}")
            return 200, {"ok": True, "run": record.to_dict()}

        return _error(404, f"no route for {method} {path}")

    # -- handlers ------------------------------------------------------
    def _create(self, body: dict[str, Any]) -> Response:
        try:
            crew = self.store.create(body)
        except ValueError as exc:
            return _error(400, str(exc))
        return 201, {"ok": True, "crew": crew.to_dict()}

    def _read(self, crew_id: str) -> Response:
        try:
            crew = self.store.get(crew_id)
        except (CrewNotFound, ValueError):
            return _error(404, f"unknown crew {crew_id!r}")
        return 200, {"ok": True, "crew": crew.to_dict()}

    def _update(self, crew_id: str, body: dict[str, Any]) -> Response:
        try:
            self.store.get(crew_id)
        except (CrewNotFound, ValueError):
            return _error(404, f"unknown crew {crew_id!r}")
        try:
            merged = {**body, "id": crew_id}
            crew = self.store.save(CrewDefinition.from_dict(merged))
        except ValueError as exc:
            return _error(400, str(exc))
        return 200, {"ok": True, "crew": crew.to_dict()}

    def _delete(self, crew_id: str) -> Response:
        try:
            self.store.delete(crew_id)
        except (CrewNotFound, ValueError):
            return _error(404, f"unknown crew {crew_id!r}")
        return 200, {"ok": True, "deleted": crew_id}

    def _start_run(self, crew_id: str, body: dict[str, Any]) -> Response:
        try:
            crew = self.store.get(crew_id)
        except (CrewNotFound, ValueError):
            return _error(404, f"unknown crew {crew_id!r}")
        record = self.runs.start(crew, body.get("inputs") or {})
        return 202, {"ok": True, "run": record.summary()}


__all__ = ["BeholdersApi", "BLUEPRINTS", "Response", "RunStatus", "Process"]
