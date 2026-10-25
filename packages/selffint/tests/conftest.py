"""A fake Frappe site, so the client, the sync and the API can be tested without
a database, a network or a 20 GB ERP.

`FakeFrappe` implements the same `Transport` protocol as `UrllibTransport`, and
it deliberately reproduces the two behaviours that break real integrations:

* the **list endpoint does not return child tables** (`taxes`, `items`) — only
  the single-document endpoint does;
* the server's **default page length is 20** when the caller forgets to ask.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

import pytest


class FakeFrappe:
    def __init__(self, docs: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.docs: dict[str, list[dict[str, Any]]] = {k: list(v) for k, v in (docs or {}).items()}
        self.calls: list[dict[str, Any]] = []
        self.fail: set[str] = set()
        self.default_page = 20

    # -- transport --------------------------------------------------------
    def request(self, method, url, headers, body, timeout):  # noqa: ANN001, D102
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        self.calls.append(
            {
                "method": method,
                "path": parsed.path,
                "query": query,
                "body": json.loads(body) if body else None,
                "auth": headers.get("Authorization", ""),
            }
        )
        if not headers.get("Authorization", "").startswith("token "):
            return _response(401, {"exc_type": "AuthenticationError", "message": "no token"})

        if parsed.path == "/api/method/frappe.auth.get_logged_user":
            return _response(200, {"message": "integration@demo.example"})

        if parsed.path == "/api/method/frappe.client.get_count":
            payload = json.loads(body or b"{}")
            return _response(200, {"message": len(self.docs.get(payload.get("doctype", ""), []))})

        match = re.match(r"^/api/resource/(?P<doctype>[^/]+)(?:/(?P<name>[^/]+))?$", parsed.path)
        if not match:
            return _response(404, {"exc_type": "NotFound", "message": "no route"})

        doctype = urllib.parse.unquote(match.group("doctype"))
        if doctype in self.fail:
            return _response(403, {"exc_type": "PermissionError", "message": f"no permission on {doctype}"})

        name = urllib.parse.unquote(match.group("name")) if match.group("name") else ""

        if name:
            for doc in self.docs.get(doctype, []):
                if doc["name"] == name:
                    return _response(200, {"data": doc})
            return _response(404, {"exc_type": "DoesNotExistError", "message": f"{doctype} {name} not found"})

        if method == "POST":
            payload = json.loads(body or b"{}")
            created = {**payload, "name": payload.get("name") or f"{doctype.replace(' ', '')}-NEW"}
            created.setdefault("docstatus", 0)
            created.setdefault("modified", "2026-10-25 10:00:00")
            self.docs.setdefault(doctype, []).append(created)
            return _response(200, {"data": created})

        rows = self._filtered(doctype, query)
        start = int(query.get("limit_start", ["0"])[0])
        length = int(query.get("limit_page_length", [str(self.default_page)])[0])
        page = rows[start : start + length]
        # The list endpoint strips child tables — same as the real thing.
        page = [{k: v for k, v in row.items() if k not in {"taxes", "items"}} for row in page]
        return _response(200, {"data": page})

    # -- helpers ----------------------------------------------------------
    def _filtered(self, doctype: str, query: dict[str, list[str]]) -> list[dict[str, Any]]:
        rows = list(self.docs.get(doctype, []))
        raw = query.get("filters", ["[]"])[0]
        for field, operator, value in json.loads(raw or "[]"):
            if operator == ">":
                rows = [row for row in rows if str(row.get(field) or "") > str(value)]
            elif operator == "=":
                rows = [row for row in rows if row.get(field) == value]
        return sorted(rows, key=lambda row: str(row.get("modified") or ""))

    def calls_to(self, needle: str) -> list[dict[str, Any]]:
        return [call for call in self.calls if needle in call["path"]]


def _response(status: int, payload: dict[str, Any]) -> tuple[int, dict[str, str], bytes]:
    return status, {"content-type": "application/json"}, json.dumps(payload).encode()


@pytest.fixture()
def fake_docs() -> dict[str, list[dict[str, Any]]]:
    """Two customers, two invoices (one hydrated, one not), one salary slip."""
    return {
        "Customer": [
            {"name": "Acme Textiles", "customer_name": "Acme Textiles", "modified": "2026-09-01 10:00:00"},
            {"name": "Nilgiri Foods", "customer_name": "Nilgiri Foods", "modified": "2026-09-02 10:00:00"},
        ],
        "Sales Invoice": [
            {
                "name": "SINV-1",
                "customer": "Acme Textiles",
                "posting_date": "2026-09-01",
                "due_date": "2026-10-01",
                "docstatus": 1,
                "status": "Unpaid",
                "grand_total": 118000.0,
                "base_net_total": 100000.0,
                "total_taxes_and_charges": 18000.0,
                "outstanding_amount": 118000.0,
                "modified": "2026-09-01 10:00:00",
                "taxes": [
                    {"account_head": "CGST - X", "rate": 9, "tax_amount": 9000.0},
                    {"account_head": "SGST - X", "rate": 9, "tax_amount": 9000.0},
                ],
            },
            {
                "name": "SINV-2",
                "customer": "Nilgiri Foods",
                "posting_date": "2026-09-10",
                "due_date": "2026-10-10",
                "docstatus": 1,
                "status": "Unpaid",
                "grand_total": 59000.0,
                "base_net_total": 50000.0,
                "total_taxes_and_charges": 9000.0,
                "outstanding_amount": 59000.0,
                "modified": "2026-09-10 10:00:00",
                "taxes": [{"account_head": "IGST - X", "rate": 18, "tax_amount": 9000.0}],
            },
        ],
        "Salary Slip": [
            {
                "name": "SS-1",
                "employee": "EMP-1",
                "employee_name": "Meera",
                "posting_date": "2026-09-30",
                "gross_pay": 65000.0,
                "total_deduction": 7800.0,
                "net_pay": 57200.0,
                "docstatus": 1,
                "modified": "2026-09-30 18:00:00",
            }
        ],
    }


@pytest.fixture()
def fake_site(fake_docs):  # noqa: ANN001, ANN201
    return FakeFrappe(fake_docs)
