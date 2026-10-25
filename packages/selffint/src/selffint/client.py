"""The Frappe / ERPNext REST client.

Two deliberate choices:

* **urllib, not requests.** The gateway imports this package; adding an HTTP
  library to a desktop app's plugin graph is how you get two TLS stacks and a
  version conflict on someone else's machine.
* **A Transport seam.** `FrappeClient(site, transport=...)` takes anything with
  `request(method, url, headers, body, timeout) -> (status, bytes)`. That is
  what makes the whole service testable without a server, and what lets the
  demo site answer from fixtures.

The API surface implemented is the subset ERPNext integrations actually need:
list with filters/fields/paging, read one document (child tables included),
create a document, and call a whitelisted method. Everything is built from
Frappe's documented contract — `/api/resource/<DocType>` with
`Authorization: token <api_key>:<api_secret>`.

One thing this client refuses to hide: **the server's default page length is
20.** `list_docs` always sends an explicit `limit_page_length`, and `fetch_all`
pages until a short page, so "the ledger is missing rows" cannot happen here.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

__all__ = [
    "DEFAULT_PAGE",
    "FrappeAuthError",
    "FrappeClient",
    "FrappeError",
    "FrappeNotFound",
    "FrappePermissionError",
    "FrappeRateLimited",
    "FrappeServerError",
    "FrappeValidationError",
    "Response",
    "Site",
    "UrllibTransport",
]

DEFAULT_PAGE = 200
MAX_PAGE = 1000


# --------------------------------------------------------------------------- #
# Errors — a taxonomy, not a string
# --------------------------------------------------------------------------- #


class FrappeError(Exception):
    """Base class: carries the HTTP status and Frappe's ``exc_type``."""

    def __init__(self, message: str, status: int = 0, exc_type: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.exc_type = exc_type

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "exc_type": self.exc_type, "message": self.message}


class FrappeAuthError(FrappeError):
    """401 — the key/secret pair is wrong or was revoked."""


class FrappePermissionError(FrappeError):
    """403 — the integration user may not read that doctype."""


class FrappeNotFound(FrappeError):
    """404 — no such document (or the site is not a Frappe site)."""


class FrappeValidationError(FrappeError):
    """417 — Frappe's validation failure, e.g. a mandatory field is missing."""


class FrappeRateLimited(FrappeError):
    """429 — back off; the retry-after header is in ``retry_after``."""

    def __init__(self, message: str, status: int = 429, retry_after: float = 0.0) -> None:
        super().__init__(message, status)
        self.retry_after = retry_after


class FrappeServerError(FrappeError):
    """5xx — the site is up but unhappy; retrying later is reasonable."""


_STATUS_MAP = {
    401: FrappeAuthError,
    403: FrappePermissionError,
    404: FrappeNotFound,
    417: FrappeValidationError,
}


def _error_for(status: int, payload: dict[str, Any], raw: bytes) -> FrappeError:
    message = ""
    exc_type = ""
    if isinstance(payload, dict):
        server_messages = payload.get("_server_messages")
        if server_messages:
            try:
                messages = json.loads(server_messages) if isinstance(server_messages, str) else server_messages
                message = " ".join(str(json.loads(m).get("message", m)) for m in messages)
            except (TypeError, ValueError):
                message = str(server_messages)
        message = message or str(payload.get("exception") or payload.get("message") or "").strip()
        exc_type = str(payload.get("exc_type") or "")
    if not message:
        message = raw.decode("utf-8", "replace")[:400] or f"HTTP {status}"
    if status == 429:
        return FrappeRateLimited(message, status)
    if status >= 500:
        return FrappeServerError(message, status, exc_type)
    cls = _STATUS_MAP.get(status, FrappeError)
    return cls(message, status, exc_type)


# --------------------------------------------------------------------------- #
# Transport
# --------------------------------------------------------------------------- #


class Transport(Protocol):
    def request(
        self, method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float
    ) -> tuple[int, dict[str, str], bytes]: ...


class UrllibTransport:
    """The real one. ``verify_tls`` maps to a per-request SSL context."""

    def __init__(self, verify_tls: bool = True) -> None:
        import ssl

        self._context = ssl.create_default_context()
        if not verify_tls:
            self._context.check_hostname = False
            self._context.verify_mode = ssl.CERT_NONE

    def request(  # noqa: D102 — the Protocol is the documentation
        self, method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float
    ) -> tuple[int, dict[str, str], bytes]:
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=self._context) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as error:
            return error.code, dict(error.headers or {}), error.read()
        except urllib.error.URLError as error:
            raise FrappeError(f"cannot reach the site: {error.reason}") from error


class Response:
    """What a fake transport can return without importing urllib."""

    def __init__(self, status: int, payload: Any = None, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self.payload = payload
        self.headers = headers or {}

    def as_tuple(self) -> tuple[int, dict[str, str], bytes]:
        body = b"" if self.payload is None else json.dumps(self.payload).encode()
        return self.status, {"content-type": "application/json", **self.headers}, body


# --------------------------------------------------------------------------- #
# Site + client
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Site:
    """One ERPNext/Frappe site. ``label`` is what the UI shows."""

    url: str
    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)
    label: str = "ERP site"
    verify_tls: bool = True
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("site url must start with http:// or https://")
        if not self.api_key or not self.api_secret:
            raise ValueError("both an api key and an api secret are required")

    @property
    def base(self) -> str:
        return self.url.rstrip("/")

    def __repr__(self) -> str:  # never leak the secret into a log line
        return f"Site(url={self.base!r}, label={self.label!r}, key=***)"


def _quote(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")


class FrappeClient:
    """Token-authenticated read/write client for one site."""

    def __init__(self, site: Site, transport: Transport | None = None) -> None:
        self.site = site
        self.transport: Transport = transport or UrllibTransport(site.verify_tls)

    # -- plumbing ---------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self.site.api_key}:{self.site.api_secret}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, body: Any = None, params: dict[str, str] | None = None):
        url = f"{self.site.base}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        payload = None if body is None else json.dumps(body).encode()
        status, _headers, raw = self.transport.request(
            method, url, self._headers(), payload, self.site.timeout
        )
        parsed: Any = None
        if raw:
            try:
                parsed = json.loads(raw)
            except ValueError:
                parsed = None
        if status >= 400:
            raise _error_for(status, parsed or {}, raw)
        return parsed if parsed is not None else {}

    # -- reads ------------------------------------------------------------
    def ping(self) -> str:
        """The logged-in user, or an auth error. The cheapest possible probe."""
        payload = self._request("GET", "/api/method/frappe.auth.get_logged_user")
        return str(payload.get("message", ""))

    def list_docs(
        self,
        doctype: str,
        *,
        fields: Iterable[str] | None = None,
        filters: Iterable[Iterable[Any]] | None = None,
        order_by: str = "modified asc",
        limit_start: int = 0,
        limit_page_length: int = DEFAULT_PAGE,
    ) -> list[dict[str, Any]]:
        """One page. ``limit_page_length`` is always explicit — never the 20 default."""
        params: dict[str, str] = {
            "order_by": order_by,
            "limit_start": str(max(0, int(limit_start))),
            "limit_page_length": str(min(MAX_PAGE, max(1, int(limit_page_length)))),
        }
        if fields is not None:
            params["fields"] = json.dumps(list(fields))
        if filters:
            params["filters"] = json.dumps([list(f) for f in filters])
        payload = self._request("GET", f"/api/resource/{_quote(doctype)}", params=params)
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    def fetch_all(
        self,
        doctype: str,
        *,
        fields: Iterable[str] | None = None,
        filters: Iterable[Iterable[Any]] | None = None,
        page_size: int = DEFAULT_PAGE,
        max_pages: int = 500,
    ) -> Iterable[list[dict[str, Any]]]:
        """Yield pages until a short one. Stops at ``max_pages`` rather than
        looping forever against a buggy filter."""
        start = 0
        for _ in range(max_pages):
            page = self.list_docs(
                doctype,
                fields=fields,
                filters=filters,
                limit_start=start,
                limit_page_length=page_size,
            )
            if page:
                yield page
            if len(page) < page_size:
                return
            start += page_size

    def get_doc(self, doctype: str, name: str) -> dict[str, Any]:
        """One document, child tables included (the only way to read them)."""
        payload = self._request("GET", f"/api/resource/{_quote(doctype)}/{_quote(name)}")
        return payload.get("data", {}) or {}

    def count(self, doctype: str, filters: Iterable[Iterable[Any]] | None = None) -> int:
        body: dict[str, Any] = {"doctype": doctype}
        if filters is not None:
            body["filters"] = [list(f) for f in filters]
        payload = self._request("POST", "/api/method/frappe.client.get_count", body)
        try:
            return int(payload.get("message", 0))
        except (TypeError, ValueError):
            return 0

    # -- writes -----------------------------------------------------------
    def create_doc(self, doctype: str, values: dict[str, Any]) -> dict[str, Any]:
        """Create a document. Callers pass ``docstatus: 0`` — a draft — because a
        desktop dashboard is not allowed to post to the ledger on its own."""
        payload = self._request("POST", f"/api/resource/{_quote(doctype)}", values)
        return payload.get("data", {}) or {}

    def submit_doc(self, doctype: str, name: str) -> dict[str, Any]:
        """Submit a draft through Frappe's own state machine."""
        payload = self._request("POST", "/api/method/frappe.client.submit", {"doc": {"doctype": doctype, "name": name}})
        return payload.get("message", {}) or {}

    def call(self, method: str, **params: Any) -> Any:
        """Any whitelisted method: ``call("frappe.auth.get_logged_user")``."""
        payload = self._request("POST", f"/api/method/{method}", params or {})
        return payload.get("message", payload)
