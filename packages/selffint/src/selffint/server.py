"""Standalone HTTP adapter — ``selffint serve``.

Standard library only (``http.server``), so the service runs anywhere, and the
desktop plugin has something to talk to during development without a gateway.
In production the same ``SelfFintApi`` is mounted as ASGI; this module is the
development and single-binary path, not a second implementation.

Note what this deliberately is *not*: a way to expose a company's books on
0.0.0.0. It binds loopback unless told otherwise, and it has no authentication
of its own — the gateway owns that in production.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .api import API_PREFIX, SelfFintApi

log = logging.getLogger("selffint")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8790
MAX_BODY = 4 * 1024 * 1024


def _make_handler(api: SelfFintApi, prefix: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SelfFintService/1"

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            # The renderer is a different origin from this dev server.
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
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError(f"invalid JSON body: {error}") from error
            if not isinstance(parsed, dict):
                raise ValueError("request body must be a JSON object")
            return parsed

        def _handle(self, method: str) -> None:
            # The query string is kept: `dispatch` reads `?as_of=`, `?from=`, …
            # out of the path itself, so both doors parse the same way.
            full = self.path or "/"
            path = urlparse(full).path
            query = urlparse(full).query
            if path.startswith(prefix):
                route = path[len(prefix):] or "/"
            elif path in ("/health", "/healthz"):
                route = "/health"
            else:
                return self._send(404, {"ok": False, "error": f"no route for {path}"})
            target = f"{route}?{query}" if query else route
            try:
                body = self._read_body() if method in ("POST", "PUT", "PATCH", "DELETE") else {}
            except ValueError as error:
                return self._send(400, {"ok": False, "error": str(error)})
            try:
                status, payload = api.dispatch(method, target, body)
            except Exception as error:  # pragma: no cover — dispatch already guards
                log.exception("unhandled error on %s %s", method, target)
                return self._send(500, {"ok": False, "error": f"{type(error).__name__}: {error}"})
            self._send(status, payload)

        def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's naming
            self._handle("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._handle("POST")

        def do_PUT(self) -> None:  # noqa: N802
            self._handle("PUT")

        def do_DELETE(self) -> None:  # noqa: N802
            self._handle("DELETE")

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send(204, {})

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
            log.debug("%s - %s", self.address_string(), fmt % args)

    return Handler


def make_server(
    api: SelfFintApi, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, prefix: str = API_PREFIX
) -> ThreadingHTTPServer:
    """Build the server without starting it — `port=0` picks a free port, which is
    how the tests get a real socket without guessing a number."""
    return ThreadingHTTPServer((host, port), _make_handler(api, prefix.rstrip("/")))


def serve(api: SelfFintApi, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, prefix: str = API_PREFIX) -> None:
    """Blocking. `Ctrl-C` stops it.

    All interfaces are opt-in: passing ``0.0.0.0`` is a decision the caller has
    to make explicitly, because this door has no auth of its own.
    """
    httpd = make_server(api, host, port, prefix)
    log.info("selffint listening on http://%s:%d%s", host, httpd.server_address[1], prefix)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


__all__ = ["DEFAULT_HOST", "DEFAULT_PORT", "MAX_BODY", "make_server", "serve"]
