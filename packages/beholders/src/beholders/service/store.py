"""Crew definition storage.

One JSON file per crew under ``$BEHOLDERS_HOME/crews/<id>.json`` — the same
"plain files in the user data directory" convention the rest of the stack uses,
so a crew survives restarts and is trivially diffable/backupable. Writes are
atomic (tmp + os.replace) so a crash mid-save can't truncate a crew.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import CrewDefinition, now_iso


def default_home() -> Path:
    """Resolve the data directory: ``$BEHOLDERS_HOME`` else ``~/.beholders``."""
    env = os.environ.get("BEHOLDERS_HOME")
    if env:
        return Path(env).expanduser()
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "beholders"
    return Path.home() / ".beholders"


class CrewNotFound(KeyError):
    pass


class CrewStore:
    """Filesystem-backed crew definitions."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else default_home() / "crews"
        self.root.mkdir(parents=True, exist_ok=True)

    # -- paths ---------------------------------------------------------
    def _path(self, crew_id: str) -> Path:
        # Guard the write path: ids come off the wire.
        if not crew_id or "/" in crew_id or "\\" in crew_id or crew_id.startswith("."):
            raise ValueError(f"invalid crew id {crew_id!r}")
        return self.root / f"{crew_id}.json"

    # -- reads ---------------------------------------------------------
    def list(self) -> list[CrewDefinition]:
        crews: list[CrewDefinition] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                crews.append(CrewDefinition.from_dict(data))
            except (OSError, ValueError, json.JSONDecodeError):
                # A malformed file must not take the whole list down.
                continue
        return sorted(crews, key=lambda c: c.name.lower())

    def get(self, crew_id: str) -> CrewDefinition:
        path = self._path(crew_id)
        if not path.exists():
            raise CrewNotFound(crew_id)
        return CrewDefinition.from_dict(json.loads(path.read_text(encoding="utf-8")))

    # -- writes --------------------------------------------------------
    def save(self, crew: CrewDefinition) -> CrewDefinition:
        path = self._path(crew.id)
        payload = crew.to_dict()
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                payload["created_at"] = existing.get("created_at", crew.created_at)
            except (OSError, json.JSONDecodeError):
                pass
        payload["updated_at"] = now_iso()
        self._atomic_write(path, payload)
        return CrewDefinition.from_dict(payload)

    def create(self, data: dict) -> CrewDefinition:
        crew = CrewDefinition.from_dict(data)
        if self._path(crew.id).exists():
            raise ValueError(f"crew {crew.id!r} already exists")
        return self.save(crew)

    def delete(self, crew_id: str) -> None:
        path = self._path(crew_id)
        if not path.exists():
            raise CrewNotFound(crew_id)
        path.unlink()

    @staticmethod
    def _atomic_write(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
