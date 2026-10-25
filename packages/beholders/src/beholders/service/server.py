"""Standalone HTTP adapter — ``beholders serve``.

Stdlib only (``http.server``), so the service runs anywhere the engine's own
dependencies are not installed yet, and the desktop plugin has something to talk
to during development. In production the same ``BeholdersApi`` is mounted by the
gateway's plugin router instead; this module is the development and
single-binary path, not a second implementation.
"""
from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .api import BeholdersApi

log = logging.getLogger("beholders.service")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
API_PREFIX = "/api/plugins/beholders"
MAX_BODY = 4 * 1024 * 1024


def _make_handler(api: BeholdersApi):
    class Handler(BaseHTTPRequestHandler):
        server_version = "BeholdersService/1"

        # -- plumbing --------------------------------------------------
        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            # The desktop renderer is a different origin from this dev server.
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            if length > MAX_BODY:
                raise ValueError("request body too large")
            raw = self.rfile.read(length)
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid JSON body: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValueError("request body must be a JSON object")
            return parsed

        def _route(self, method: str) -> None:
            path = urlparse(self.path).path
            if path.startswith(API_PREFIX):
                path = path[len(API_PREFIX):] or "/"
            elif path in ("/health", "/healthz"):
                path = "/health"
            else:
                return self._send(404, {"ok": False, "error": f"no route for {path}"})
            try:
                body = self._read_body() if method in ("POST", "PUT", "PATCH", "DELETE") else {}
            except ValueError as exc:
                return self._send(400, {"ok": False, "error": str(exc)})
            # GET query strings carry the filters the RPC path passes as params.
            if method == "GET":
                query = urlparse(self.path).query
                if query:
                    from urllib.parse import parse_qs

                    body = {k: v[0] for k, v in parse_qs(query).items()}
            status, payload = api.dispatch(method, path, body)
            self._send(status, payload)

        # -- verbs -----------------------------------------------------
        def do_OPTIONS(self) -> None:  # noqa: N802 - http.server API
            self._send(204, {})

        def do_GET(self) -> None:  # noqa: N802
            self._route("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._route("POST")

        def do_PUT(self) -> None:  # noqa: N802
            self._route("PUT")

        def do_PATCH(self) -> None:  # noqa: N802
            self._route("PATCH")

        def do_DELETE(self) -> None:  # noqa: N802
            self._route("DELETE")

        def log_message(self, fmt: str, *args: Any) -> None:  # quieter default
            log.debug("%s - %s", self.address_string(), fmt % args)

    return Handler


def make_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, api: BeholdersApi | None = None):
    api = api or BeholdersApi()
    return ThreadingHTTPServer((host, port), _make_handler(api))


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    httpd = make_server(host, port)
    log.info("Beholders service on http://%s:%d%s", host, port, API_PREFIX)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
