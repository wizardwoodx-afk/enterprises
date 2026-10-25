"""The SQLite mirror.

Why a mirror at all: a dashboard that calls the ERP on every render is slow,
hammers a production system, and dies when the site is down. SelfFint keeps the
documents it needs locally, keyed by `(site, doctype, name)`, and every report
reads from here.

The mirror is **read-mostly**. Draft invoices are created on the site
(write-through) and only then mirrored, so a failed write never leaves a
document that exists nowhere.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

__all__ = ["MirrorStore", "default_home", "mirror_path"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
  id          TEXT PRIMARY KEY,
  url         TEXT NOT NULL,
  label       TEXT NOT NULL,
  mode        TEXT NOT NULL DEFAULT 'live',
  api_key     TEXT NOT NULL DEFAULT '',
  api_secret  TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS docs (
  site_id    TEXT NOT NULL,
  doctype    TEXT NOT NULL,
  name       TEXT NOT NULL,
  modified   TEXT,
  docstatus  INTEGER,
  payload    TEXT NOT NULL,
  PRIMARY KEY (site_id, doctype, name)
);
CREATE INDEX IF NOT EXISTS docs_modified ON docs (site_id, doctype, modified);
CREATE TABLE IF NOT EXISTS syncs (
  site_id    TEXT NOT NULL,
  doctype    TEXT NOT NULL,
  watermark  TEXT,
  rows       INTEGER NOT NULL DEFAULT 0,
  synced_at  TEXT,
  ok         INTEGER NOT NULL DEFAULT 1,
  error      TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (site_id, doctype)
);
"""


def default_home() -> Path:
    """Where the mirror lives. Follows the app's own home, not the cwd."""
    root = os.environ.get("BEYOND_HOME") or os.environ.get("SELFFINT_HOME")
    if root:
        return Path(root) / "selffint"
    return Path.home() / ".beyond" / "selffint"


def mirror_path() -> Path:
    return default_home() / "mirror.db"


class MirrorStore:
    """Thin, explicit SQLite wrapper. No ORM, no migrations framework — the
    schema is three tables and `IF NOT EXISTS` is the migration."""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        raw = str(path) if path is not None else str(mirror_path())
        self.path = raw
        if raw != ":memory:":
            Path(raw).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(raw, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        if raw != ":memory:":
            # The mirror holds an API secret; keep it private to this user.
            try:
                os.chmod(raw, 0o600)
            except OSError:
                pass

    def close(self) -> None:
        self._conn.close()

    # -- sites ------------------------------------------------------------
    def upsert_site(
        self,
        site_id: str,
        url: str,
        label: str,
        *,
        mode: str = "live",
        api_key: str = "",
        api_secret: str = "",
    ) -> None:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                """INSERT INTO sites (id, url, label, mode, api_key, api_secret, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     url=excluded.url, label=excluded.label, mode=excluded.mode,
                     api_key=excluded.api_key, api_secret=excluded.api_secret""",
                (site_id, url.rstrip("/"), label, mode, api_key, api_secret, _now()),
            )
        self._conn.commit()

    def get_site(self, site_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM sites WHERE id = ?", (site_id,)).fetchone()
        return _site_dict(row) if row else None

    def sites(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM sites ORDER BY created_at").fetchall()
        return [_site_dict(row) for row in rows]

    def default_site(self) -> dict[str, Any] | None:
        sites = self.sites()
        return sites[0] if sites else None

    def delete_site(self, site_id: str) -> None:
        with closing(self._conn.cursor()) as cur:
            cur.execute("DELETE FROM docs WHERE site_id = ?", (site_id,))
            cur.execute("DELETE FROM syncs WHERE site_id = ?", (site_id,))
            cur.execute("DELETE FROM sites WHERE id = ?", (site_id,))
        self._conn.commit()

    # -- documents --------------------------------------------------------
    def upsert_docs(self, site_id: str, doctype: str, docs: Iterable[dict[str, Any]]) -> int:
        """Insert or replace by `(site, doctype, name)`. Rows without a name are
        skipped rather than stored under an empty key."""
        rows: list[tuple[Any, ...]] = []
        for doc in docs:
            name = doc.get("name")
            if not name:
                continue
            try:
                docstatus = int(doc.get("docstatus", 0))
            except (TypeError, ValueError):
                docstatus = 0
            rows.append(
                (site_id, doctype, str(name), doc.get("modified"), docstatus, json.dumps(doc, default=str))
            )
        if not rows:
            return 0
        with closing(self._conn.cursor()) as cur:
            cur.executemany(
                """INSERT INTO docs (site_id, doctype, name, modified, docstatus, payload)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(site_id, doctype, name) DO UPDATE SET
                     modified=excluded.modified, docstatus=excluded.docstatus, payload=excluded.payload""",
                rows,
            )
        self._conn.commit()
        return len(rows)

    def docs(
        self,
        site_id: str,
        doctype: str,
        *,
        search: str = "",
        status: str = "",
        limit: int = 200,
        offset: int = 0,
        order: str = "modified desc",
    ) -> list[dict[str, Any]]:
        """Filtered reads. Filters are `LIKE` over the payload rather than
        `json_extract`, so an old SQLite without JSON1 still works."""
        clauses = ["site_id = ?", "doctype = ?"]
        params: list[Any] = [site_id, doctype]
        if search:
            clauses.append("(name LIKE ? OR payload LIKE ?)")
            needle = f"%{search}%"
            params.extend([needle, needle])
        if status:
            clauses.append("payload LIKE ?")
            params.append(f'%"status": "{status}"%')
        direction = "ASC" if order.lower().endswith("asc") else "DESC"
        params.extend([max(1, min(2000, int(limit))), max(0, int(offset))])
        sql = (
            f"SELECT payload FROM docs WHERE {' AND '.join(clauses)} "
            f"ORDER BY modified {direction}, name {direction} LIMIT ? OFFSET ?"
        )
        return [json.loads(row["payload"]) for row in self._conn.execute(sql, params).fetchall()]

    def one(self, site_id: str, doctype: str, name: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT payload FROM docs WHERE site_id = ? AND doctype = ? AND name = ?",
            (site_id, doctype, name),
        ).fetchone()
        return json.loads(row["payload"]) if row else None

    def count(self, site_id: str, doctype: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM docs WHERE site_id = ? AND doctype = ?", (site_id, doctype)
        ).fetchone()
        return int(row["n"]) if row else 0

    def names_missing_taxes(self, site_id: str, doctype: str, limit: int = 200) -> list[str]:
        """Invoices whose child `taxes` table was never hydrated."""
        rows = self._conn.execute(
            """SELECT name FROM docs
               WHERE site_id = ? AND doctype = ? AND payload NOT LIKE '%"taxes"%'
               ORDER BY modified DESC LIMIT ?""",
            (site_id, doctype, max(1, int(limit))),
        ).fetchall()
        return [row["name"] for row in rows]

    # -- sync state -------------------------------------------------------
    def watermark(self, site_id: str, doctype: str) -> str:
        row = self._conn.execute(
            "SELECT watermark FROM syncs WHERE site_id = ? AND doctype = ?", (site_id, doctype)
        ).fetchone()
        return (row["watermark"] or "") if row else ""

    def record_sync(
        self,
        site_id: str,
        doctype: str,
        *,
        watermark: str,
        rows: int,
        ok: bool = True,
        error: str = "",
    ) -> None:
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                """INSERT INTO syncs (site_id, doctype, watermark, rows, synced_at, ok, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(site_id, doctype) DO UPDATE SET
                     watermark=CASE WHEN excluded.ok = 1 THEN excluded.watermark
                                    ELSE syncs.watermark END,
                     rows=excluded.rows, synced_at=excluded.synced_at,
                     ok=excluded.ok, error=excluded.error""",
                (site_id, doctype, watermark, int(rows), _now(), 1 if ok else 0, error),
            )
        self._conn.commit()

    def sync_state(self, site_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM syncs WHERE site_id = ? ORDER BY doctype", (site_id,)
        ).fetchall()
        return [
            {
                "doctype": row["doctype"],
                "watermark": row["watermark"] or "",
                "rows": row["rows"],
                "synced_at": row["synced_at"] or "",
                "ok": bool(row["ok"]),
                "error": row["error"] or "",
            }
            for row in rows
        ]


def _site_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "url": row["url"],
        "label": row["label"],
        "mode": row["mode"],
        "has_credentials": bool(row["api_key"] and row["api_secret"]),
        "created_at": row["created_at"],
    }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
