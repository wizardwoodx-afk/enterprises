"""SelfFint's request handling.

`dispatch(method, path, body) -> (status, payload)` — the same shape the
Beholders service uses, so the gateway mounts both the same way and both are
testable as plain Python.

Three rules this module keeps:

* every path is relative to the mount point, so nothing here knows where it
  lives;
* every response is `{"ok": bool, ...}` — a failure is a payload, not a stack
  trace, because the client renders it in a pane;
* the only write that reaches a **live** site is a *draft* sales invoice, and it
  is created on the site first, then mirrored. A dashboard must not post to the
  ledger, and a failed write must not leave a ghost document behind.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Callable
from urllib.parse import parse_qs, unquote

from .client import FrappeClient, FrappeError, Site
from .demo import DEMO_2B, DEMO_SITE_ID, seed_demo
from .recon import parse_2b, reconcile_2b
from .reports import DASHBOARD_DOCTYPES, ar_aging, gst_summary, payroll_summary
from .store import MirrorStore
from .sync import SYNCED_DOCTYPES, sync_site

__all__ = ["API_PREFIX", "SelfFintApi", "Response"]

API_PREFIX = "/api/plugins/self-fint"

Response = tuple[int, dict[str, Any]]

_SITE_ONE = re.compile(r"^/sites/(?P<id>[^/]+)$")
_DOC_ONE = re.compile(r"^/documents/(?P<doctype>[^/]+)/(?P<name>[^/]+)$")


def _q(value: list[str] | None, default: str = "") -> str:
    return (value[0] if value else default) or default


def _bad(message: str, status: int = 400) -> Response:
    return status, {"ok": False, "error": message}


class SelfFintApi:
    """The service. Pass a `MirrorStore` you own, or let it make the default."""

    def __init__(
        self,
        store: MirrorStore | None = None,
        client_factory: Callable[[Site], FrappeClient] | None = None,
    ) -> None:
        self.store = store or MirrorStore()
        self._client_factory = client_factory or (lambda site: FrappeClient(site))

    # -- helpers ----------------------------------------------------------
    def _site(self, body: dict[str, Any]) -> dict[str, Any] | None:
        site_id = str(body.get("site") or "").strip()
        return self.store.get_site(site_id) if site_id else self.store.default_site()

    def _client_for(self, site: dict[str, Any]) -> FrappeClient:
        secret = self.store.get_site(site["id"]) or {}
        # api_key/api_secret never leave the store through the API surface.
        stored = self._credentials(site["id"])
        if not stored:
            raise FrappeError("this site has no API credentials stored; reconnect it")
        _key, _secret = stored
        return self._client_factory(
            Site(
                url=secret.get("url", site["url"]),
                api_key=_key,
                api_secret=_secret,
                label=secret.get("label", site["label"]),
            )
        )

    def _credentials(self, site_id: str) -> tuple[str, str] | None:
        row = self.store._conn.execute(  # noqa: SLF001 — same package, internal read
            "SELECT api_key, api_secret FROM sites WHERE id = ?", (site_id,)
        ).fetchone()
        if not row or not row["api_key"] or not row["api_secret"]:
            return None
        return str(row["api_key"]), str(row["api_secret"])

    def _ensure_site(self) -> dict[str, Any]:
        """A first run has no site; seed the demo one so the page has a shape."""
        site = self.store.default_site()
        if site is None:
            seed_demo(self.store)
            site = self.store.get_site(DEMO_SITE_ID)
        assert site is not None  # seed_demo guarantees it
        return site

    # -- dispatch ---------------------------------------------------------
    def dispatch(self, method: str, path: str, body: dict[str, Any] | None = None) -> Response:
        method = (method or "GET").upper()
        body = body or {}
        raw_path, _, query = (path or "/").partition("?")
        params = parse_qs(query)
        route = raw_path.rstrip("/") or "/"

        try:
            return self._route(method, route, params, body)
        except FrappeError as error:
            return 502, {"ok": False, "error": error.message, **error.as_dict()}
        except ValueError as error:
            return _bad(str(error))
        except Exception as error:  # pragma: no cover — defensive, never leaks a trace
            return 500, {"ok": False, "error": f"{type(error).__name__}: {error}"}

    def _route(self, method: str, route: str, params: dict[str, list[str]], body: dict[str, Any]) -> Response:
        if route == "/health":
            return 200, {"ok": True, "service": "selffint", "version": "1.0.0"}

        if route == "/status" and method == "GET":
            return self._status()

        if route == "/sites":
            if method == "GET":
                self._ensure_site()
                return 200, {"ok": True, "sites": self.store.sites(), "default": self.store.default_site()}
            return _bad("use POST /connect to add a site", 405)

        site_one = _SITE_ONE.match(route)
        if site_one and method == "DELETE":
            site_id = unquote(site_one.group("id"))
            if not self.store.get_site(site_id):
                return _bad("no such site", 404)
            self.store.delete_site(site_id)
            return 200, {"ok": True, "deleted": site_id}

        if route == "/connect" and method == "POST":
            return self._connect(body)

        if route == "/sync" and method == "POST":
            return self._sync(body)

        if route == "/demo/seed" and method == "POST":
            return 200, {"ok": True, **seed_demo(self.store)}

        if route == "/invoices":
            if method == "GET":
                return self._invoices(params)
            if method == "POST":
                return self._create_invoice(body)
            return _bad("method not allowed", 405)

        if route == "/parties" and method == "GET":
            return self._parties(params)

        doc_one = _DOC_ONE.match(route)
        if doc_one and method == "GET":
            doctype = unquote(doc_one.group("doctype"))
            name = unquote(doc_one.group("name"))
            site = self._ensure_site()
            doc = self.store.one(site["id"], doctype, name)
            if doc is None:
                return _bad("document not in the mirror yet — run a sync", 404)
            return 200, {"ok": True, "document": doc}

        if route == "/reports/ar-aging" and method == "GET":
            return self._ar_aging(params)

        if route == "/reports/gst" and method == "GET":
            return self._gst(params)

        if route == "/reports/payroll" and method == "GET":
            return self._payroll(params)

        if route == "/reconcile/2b" and method == "POST":
            return self._reconcile(body)

        return _bad(f"no route for {method} {route}", 404)

    # -- handlers ---------------------------------------------------------
    def _status(self) -> Response:
        site = self._ensure_site()
        counts = {doctype: self.store.count(site["id"], doctype) for doctype in DASHBOARD_DOCTYPES}
        syncs = self.store.sync_state(site["id"])
        warnings: list[str] = []
        if site["mode"] == "demo":
            warnings.append("This is the demo company — fixture data, not your books.")
        if site["mode"] != "demo" and counts["Sales Invoice"] == 0:
            warnings.append("No documents yet — run a sync against the site.")
        failed = [sync["doctype"] for sync in syncs if not sync["ok"]]
        if failed:
            warnings.append(f"Last sync failed for: {', '.join(failed)}")
        return 200, {
            "ok": True,
            "service": "selffint",
            "version": "1.0.0",
            "site": site,
            "sites": self.store.sites(),
            "counts": counts,
            "syncs": syncs,
            "last_sync": max((sync["synced_at"] for sync in syncs), default=""),
            "warnings": warnings,
            "supported_doctypes": list(SYNCED_DOCTYPES),
        }

    def _connect(self, body: dict[str, Any]) -> Response:
        url = str(body.get("url") or "").strip()
        api_key = str(body.get("api_key") or "").strip()
        api_secret = str(body.get("api_secret") or "").strip()
        label = str(body.get("label") or "").strip() or url
        if not url or not api_key or not api_secret:
            return _bad("url, api_key and api_secret are required")
        try:
            site = Site(url=url, api_key=api_key, api_secret=api_secret, label=label)
        except ValueError as error:
            return _bad(str(error))

        user = ""
        try:
            user = self._client_factory(site).ping()
        except FrappeError as error:
            return 502, {"ok": False, "error": error.message, **error.as_dict()}

        site_id = str(body.get("site_id") or "").strip() or uuid.uuid4().hex[:12]
        self.store.upsert_site(
            site_id, site.base, label, mode="live", api_key=api_key, api_secret=api_secret
        )
        return 200, {
            "ok": True,
            "site": self.store.get_site(site_id),
            "user": user,
            "message": f"Connected as {user or 'an unnamed user'}",
        }

    def _sync(self, body: dict[str, Any]) -> Response:
        site = self._site(body)
        if site is None:
            return _bad("no site to sync", 404)
        if site["mode"] == "demo":
            return 200, {"ok": True, "mode": "demo", "message": "The demo site is already local.", "doctypes": []}
        doctypes = body.get("doctypes") or None
        if doctypes is not None and not isinstance(doctypes, list):
            return _bad("doctypes must be a list")
        report = sync_site(
            self._client_for(site),
            self.store,
            site["id"],
            doctypes=doctypes,
            full=bool(body.get("full")),
            page_size=int(body.get("page_size") or 200),
            hydrate_limit=int(body.get("hydrate_limit") or 200),
        )
        return 200, {"mode": "live", **report}

    def _invoices(self, params: dict[str, list[str]]) -> Response:
        site = self._ensure_site()
        limit = int(_q(params.get("limit"), "200"))
        rows = self.store.docs(
            site["id"],
            "Sales Invoice",
            search=_q(params.get("search")),
            status=_q(params.get("status")),
            limit=limit,
        )
        return 200, {
            "ok": True,
            "mode": site["mode"],
            "invoices": [
                {
                    "name": doc.get("name"),
                    "customer": doc.get("customer") or doc.get("customer_name") or "",
                    "posting_date": doc.get("posting_date") or "",
                    "due_date": doc.get("due_date") or "",
                    "grand_total": float(doc.get("grand_total") or 0),
                    "outstanding_amount": float(doc.get("outstanding_amount") or 0),
                    "status": doc.get("status") or "",
                    "docstatus": int(doc.get("docstatus") or 0),
                    "currency": doc.get("currency") or "INR",
                }
                for doc in rows
            ],
        }

    def _parties(self, params: dict[str, list[str]]) -> Response:
        site = self._ensure_site()
        kind = (_q(params.get("kind"), "customer") or "customer").lower()
        doctype = "Supplier" if kind.startswith("sup") else "Customer"
        rows = self.store.docs(site["id"], doctype, search=_q(params.get("search")), limit=500)
        return 200, {
            "ok": True,
            "kind": kind,
            "parties": [
                {
                    "name": doc.get("name"),
                    "display": doc.get("customer_name") or doc.get("supplier_name") or doc.get("name"),
                    "group": doc.get("customer_group") or doc.get("supplier_group") or "",
                    "territory": doc.get("territory") or "",
                }
                for doc in rows
            ],
        }

    def _ar_aging(self, params: dict[str, list[str]]) -> Response:
        site = self._ensure_site()
        invoices = self.store.docs(site["id"], "Sales Invoice", limit=2000)
        report = ar_aging(invoices, as_of=_q(params.get("as_of")) or None)
        return 200, {"ok": True, "mode": site["mode"], **report}

    def _gst(self, params: dict[str, list[str]]) -> Response:
        site = self._ensure_site()
        invoices = self.store.docs(site["id"], "Sales Invoice", limit=2000)
        report = gst_summary(
            invoices,
            date_from=_q(params.get("from")) or None,
            date_to=_q(params.get("to")) or None,
        )
        return 200, {"ok": True, "mode": site["mode"], **report}

    def _payroll(self, params: dict[str, list[str]]) -> Response:
        site = self._ensure_site()
        slips = self.store.docs(site["id"], "Salary Slip", limit=2000)
        report = payroll_summary(slips, month=_q(params.get("month")))
        return 200, {"ok": True, "mode": site["mode"], **report}

    def _reconcile(self, body: dict[str, Any]) -> Response:
        site = self._ensure_site()
        payload = body.get("payload")
        rows = body.get("rows")
        if payload is not None:
            portal = parse_2b(payload)
        elif isinstance(rows, list):
            portal = rows
        elif site["mode"] == "demo" and body.get("use_demo"):
            portal = DEMO_2B
        else:
            return _bad("send the GSTR-2B file as `payload`, or rows as `rows`")
        books = body.get("books")
        if not isinstance(books, list):
            books = [
                {
                    "name": doc.get("name"),
                    "supplier_gstin": doc.get("supplier_gstin") or "",
                    "bill_no": doc.get("bill_no") or doc.get("name"),
                    "posting_date": doc.get("posting_date"),
                    "base_net_total": doc.get("base_net_total"),
                    "total_taxes_and_charges": doc.get("total_taxes_and_charges"),
                }
                for doc in self.store.docs(site["id"], "Purchase Invoice", limit=2000)
            ]
        result = reconcile_2b(
            books,
            portal,
            period=str(body.get("period") or ""),
            tolerance=body.get("tolerance", 1),
            fuzzy=bool(body.get("fuzzy", True)),
        )
        return 200, {"ok": True, "mode": site["mode"], **result.to_dict()}

    def _create_invoice(self, body: dict[str, Any]) -> Response:
        customer = str(body.get("customer") or "").strip()
        items = body.get("items")
        if not customer:
            return _bad("customer is required")
        if not isinstance(items, list) or not items:
            return _bad("at least one item is required")
        cleaned: list[dict[str, Any]] = []
        for item in items:
            try:
                rate = float(item.get("rate") or 0)
                qty = float(item.get("qty") or 1)
            except (TypeError, ValueError):
                return _bad("item rate and qty must be numbers")
            if rate <= 0:
                return _bad("every item needs a rate above zero")
            cleaned.append(
                {
                    "item_code": str(item.get("item_code") or "SERVICE"),
                    "description": str(item.get("description") or "Services"),
                    "qty": qty,
                    "rate": rate,
                }
            )
        site = self._ensure_site()
        values = {
            "doctype": "Sales Invoice",
            "customer": customer,
            "posting_date": str(body.get("posting_date") or ""),
            "due_date": str(body.get("due_date") or ""),
            "items": cleaned,
            "docstatus": 0,
        }
        values = {key: value for key, value in values.items() if value not in ("", None)}

        if site["mode"] == "demo":
            taxable = round(sum(item["qty"] * item["rate"] for item in cleaned), 2)
            doc = {
                **values,
                "name": f"SINV-DEMO-{uuid.uuid4().hex[:6].upper()}",
                "docstatus": 0,
                "status": "Draft",
                "base_net_total": taxable,
                "total_taxes_and_charges": round(taxable * 0.18, 2),
                "grand_total": round(taxable * 1.18, 2),
                "outstanding_amount": round(taxable * 1.18, 2),
                "currency": "INR",
                "modified": "2026-10-25 12:00:00",
                "taxes": [
                    {"account_head": "CGST - DEMO", "rate": 9, "tax_amount": round(taxable * 0.09, 2)},
                    {"account_head": "SGST - DEMO", "rate": 9, "tax_amount": round(taxable * 0.09, 2)},
                ],
            }
            self.store.upsert_docs(site["id"], "Sales Invoice", [doc])
            return 201, {"ok": True, "mode": "demo", "document": doc,
                         "message": "Draft created locally (demo site — nothing was sent anywhere)."}

        created = self._client_for(site).create_doc("Sales Invoice", values)
        self.store.upsert_docs(site["id"], "Sales Invoice", [created])
        return 201, {
            "ok": True,
            "mode": "live",
            "document": created,
            "message": f"Draft {created.get('name', '')} created on the site — not submitted.",
        }
