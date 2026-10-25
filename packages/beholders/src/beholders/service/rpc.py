"""JSON-RPC adapter: the ``crew.*`` method surface on the Beyond gateway.

Beyond's desktop already speaks JSON-RPC 2.0 over its gateway channel
(``apps/shared/src/json-rpc-channel.ts``). Rather than inventing a second
protocol for crews, this maps the very same ``BeholdersApi`` handlers onto
method names, so a crew is reachable from the same connection — and from any
future surface — using the transport that already has reconnects, heartbeats,
timeouts and replay.

Method shapes are documented in ``docs/BEHOLDERS.md`` and mirrored in
``apps/shared/src/crew-contract.ts``.
"""
from __future__ import annotations

from typing import Any

from .api import BeholdersApi
from .store import CrewNotFound

# JSON-RPC 2.0 error codes we use.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Beyond's own application error band (mirrors the gateway's reserved range).
APP_NOT_FOUND = -32004
APP_INVALID = -32022


class RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _params(params: Any) -> dict[str, Any]:
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise RpcError(INVALID_PARAMS, "params must be an object")
    return params


class CrewRpc:
    """Dispatches ``crew.*`` JSON-RPC methods onto :class:`BeholdersApi`."""

    def __init__(self, api: BeholdersApi | None = None) -> None:
        self.api = api or BeholdersApi()

    def methods(self) -> list[str]:
        return [
            "crew.blueprints",
            "crew.create",
            "crew.delete",
            "crew.get",
            "crew.list",
            "crew.run",
            "crew.runs",
            "crew.runs.cancel",
            "crew.runs.get",
            "crew.status",
            "crew.update",
        ]

    def dispatch(self, method: str, params: Any = None) -> dict[str, Any]:
        args = _params(params)
        handler = {
            "crew.status": self._status,
            "crew.blueprints": self._blueprints,
            "crew.list": self._list,
            "crew.get": self._get,
            "crew.create": self._create,
            "crew.update": self._update,
            "crew.delete": self._delete,
            "crew.run": self._run,
            "crew.runs": self._runs,
            "crew.runs.get": self._runs_get,
            "crew.runs.cancel": self._runs_cancel,
        }.get(method)
        if handler is None:
            raise RpcError(METHOD_NOT_FOUND, f"unknown method {method!r}")
        return handler(args)

    # -- methods -------------------------------------------------------
    def _status(self, _args: dict[str, Any]) -> dict[str, Any]:
        status, payload = self.api.dispatch("GET", "/health")
        return payload

    def _blueprints(self, _args: dict[str, Any]) -> dict[str, Any]:
        return self.api.dispatch("GET", "/blueprints")[1]

    def _list(self, _args: dict[str, Any]) -> dict[str, Any]:
        return self.api.dispatch("GET", "/crews")[1]

    def _get(self, args: dict[str, Any]) -> dict[str, Any]:
        crew_id = args.get("crew_id") or args.get("id")
        if not crew_id:
            raise RpcError(INVALID_PARAMS, "crew.get needs crew_id")
        status, payload = self.api.dispatch("GET", f"/crews/{crew_id}")
        if status == 404:
            raise RpcError(APP_NOT_FOUND, payload["error"])
        return payload

    def _create(self, args: dict[str, Any]) -> dict[str, Any]:
        crew = args.get("crew")
        if not isinstance(crew, dict):
            raise RpcError(INVALID_PARAMS, "crew.create needs a crew object")
        status, payload = self.api.dispatch("POST", "/crews", crew)
        if status >= 400:
            raise RpcError(APP_INVALID, payload["error"])
        return payload

    def _update(self, args: dict[str, Any]) -> dict[str, Any]:
        crew_id = args.get("crew_id") or args.get("id")
        crew = args.get("crew")
        if not crew_id or not isinstance(crew, dict):
            raise RpcError(INVALID_PARAMS, "crew.update needs crew_id and crew")
        status, payload = self.api.dispatch("PUT", f"/crews/{crew_id}", crew)
        if status == 404:
            raise RpcError(APP_NOT_FOUND, payload["error"])
        if status >= 400:
            raise RpcError(APP_INVALID, payload["error"])
        return payload

    def _delete(self, args: dict[str, Any]) -> dict[str, Any]:
        crew_id = args.get("crew_id") or args.get("id")
        if not crew_id:
            raise RpcError(INVALID_PARAMS, "crew.delete needs crew_id")
        status, payload = self.api.dispatch("DELETE", f"/crews/{crew_id}")
        if status == 404:
            raise RpcError(APP_NOT_FOUND, payload["error"])
        return payload

    def _run(self, args: dict[str, Any]) -> dict[str, Any]:
        crew_id = args.get("crew_id") or args.get("id")
        if not crew_id:
            raise RpcError(INVALID_PARAMS, "crew.run needs crew_id")
        status, payload = self.api.dispatch(
            "POST", f"/crews/{crew_id}/runs", {"inputs": args.get("inputs") or {}}
        )
        if status == 404:
            raise RpcError(APP_NOT_FOUND, payload["error"])
        if status >= 400:
            raise RpcError(APP_INVALID, payload["error"])
        return payload

    def _runs(self, args: dict[str, Any]) -> dict[str, Any]:
        params = {"limit": args.get("limit", 50)}
        if args.get("crew_id"):
            params["crew_id"] = args["crew_id"]
        return self.api.dispatch("GET", "/runs", params)[1]

    def _runs_get(self, args: dict[str, Any]) -> dict[str, Any]:
        run_id = args.get("run_id")
        if not run_id:
            raise RpcError(INVALID_PARAMS, "crew.runs.get needs run_id")
        status, payload = self.api.dispatch("GET", f"/runs/{run_id}")
        if status == 404:
            raise RpcError(APP_NOT_FOUND, payload["error"])
        return payload

    def _runs_cancel(self, args: dict[str, Any]) -> dict[str, Any]:
        run_id = args.get("run_id")
        if not run_id:
            raise RpcError(INVALID_PARAMS, "crew.runs.cancel needs run_id")
        status, payload = self.api.dispatch("POST", f"/runs/{run_id}/cancel", {})
        if status == 404:
            raise RpcError(APP_NOT_FOUND, payload["error"])
        return payload


def handle_request(rpc: CrewRpc, request: dict[str, Any]) -> dict[str, Any]:
    """Handle one JSON-RPC 2.0 request envelope, returning the response envelope."""
    req_id = request.get("id")
    method = request.get("method")
    if not isinstance(method, str):
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": INVALID_REQUEST, "message": "method must be a string"},
        }
    try:
        result = rpc.dispatch(method, request.get("params"))
    except RpcError as exc:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": exc.code, "message": exc.message}}
    except CrewNotFound as exc:  # defensive: handlers translate these already
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": APP_NOT_FOUND, "message": f"unknown crew {exc.args[0]!r}"},
        }
    except Exception as exc:  # noqa: BLE001 - never leak a stack to the wire
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": INTERNAL_ERROR, "message": f"{type(exc).__name__}: {exc}"},
        }
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


# Notifications the service can emit on a run's lifecycle. Shapes match the
# gateway's `{method, params: {type, ...}}` notification framing.
NOTIFICATION_METHOD = "crew.event"
