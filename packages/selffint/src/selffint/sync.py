"""Incremental sync from the site into the mirror.

Design points that matter in production:

* **Incremental by `modified`.** Each doctype keeps a watermark; the next run
  asks only for `modified > watermark`. A full sync is opt-in, not the default.
* **Per-doctype isolation.** A permission error on `Salary Slip` must not stop
  invoices syncing. Failures are recorded per doctype and reported, not raised.
* **Child tables are hydrated.** Frappe's list endpoint never returns child
  tables, and GST lives in `Sales Invoice.taxes`. Invoices are re-fetched one by
  one — bounded by `hydrate_limit` per run — so the GST report has real tax rows
  instead of a single opaque total.
* **Watermarks only advance on success.** A half-finished page must not be
  recorded as synced, or the missing window is lost forever.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from .client import FrappeClient, FrappeError
from .store import MirrorStore

__all__ = ["FIELDS", "HYDRATED_DOCTYPES", "SYNCED_DOCTYPES", "sync_site"]

SYNCED_DOCTYPES: tuple[str, ...] = (
    "Customer",
    "Supplier",
    "Sales Invoice",
    "Purchase Invoice",
    "Payment Entry",
    "Employee",
    "Salary Slip",
)

HYDRATED_DOCTYPES: tuple[str, ...] = ("Sales Invoice", "Purchase Invoice")

FIELDS: dict[str, list[str]] = {
    "Customer": ["name", "customer_name", "customer_group", "territory", "modified"],
    "Supplier": ["name", "supplier_name", "supplier_group", "territory", "modified"],
    "Sales Invoice": [
        "name", "customer", "customer_name", "posting_date", "due_date", "grand_total",
        "base_grand_total", "base_net_total", "total_taxes_and_charges", "outstanding_amount",
        "status", "docstatus", "currency", "company", "modified",
    ],
    "Purchase Invoice": [
        "name", "supplier", "supplier_name", "bill_no", "bill_date", "posting_date", "due_date",
        "grand_total", "base_grand_total", "base_net_total", "total_taxes_and_charges",
        "outstanding_amount", "status", "docstatus", "currency", "company", "modified",
    ],
    "Payment Entry": [
        "name", "party", "party_type", "posting_date", "paid_amount", "received_amount",
        "payment_type", "docstatus", "modified",
    ],
    "Employee": ["name", "employee_name", "department", "designation", "status", "modified"],
    "Salary Slip": [
        "name", "employee", "employee_name", "posting_date", "gross_pay", "total_deduction",
        "net_pay", "status", "docstatus", "modified",
    ],
}


def sync_site(
    client: FrappeClient,
    store: MirrorStore,
    site_id: str,
    *,
    doctypes: Iterable[str] | None = None,
    page_size: int = 200,
    full: bool = False,
    hydrate_limit: int = 200,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Pull documents into the mirror and return a per-doctype report."""
    selected = tuple(doctypes or SYNCED_DOCTYPES)
    unknown = [doctype for doctype in selected if doctype not in FIELDS]
    if unknown:
        raise ValueError(f"unsupported doctype(s): {', '.join(unknown)}")

    report: dict[str, Any] = {"site": site_id, "doctypes": [], "rows": 0, "ok": True}
    for doctype in selected:
        entry: dict[str, Any] = {"doctype": doctype, "rows": 0, "hydrated": 0, "ok": True, "error": ""}
        watermark = "" if full else store.watermark(site_id, doctype)
        filters = [["modified", ">", watermark]] if watermark else []
        latest = watermark
        written = 0
        try:
            for page in client.fetch_all(doctype, fields=FIELDS[doctype], filters=filters, page_size=page_size):
                written += store.upsert_docs(site_id, doctype, page)
                for doc in page:
                    modified = str(doc.get("modified") or "")
                    if modified > latest:
                        latest = modified
            if doctype in HYDRATED_DOCTYPES and hydrate_limit > 0:
                entry["hydrated"] = _hydrate(client, store, site_id, doctype, hydrate_limit)
        except FrappeError as error:
            entry.update({"ok": False, "error": error.message})
            report["ok"] = False
            store.record_sync(site_id, doctype, watermark=watermark, rows=0, ok=False, error=error.message)
            report["doctypes"].append(entry)
            if on_progress:
                on_progress(entry)
            continue
        store.record_sync(site_id, doctype, watermark=latest, rows=written, ok=True)
        entry["rows"] = written
        entry["watermark"] = latest
        report["rows"] += written
        report["doctypes"].append(entry)
        if on_progress:
            on_progress(entry)
    return report


def _hydrate(
    client: FrappeClient, store: MirrorStore, site_id: str, doctype: str, limit: int
) -> int:
    """Fetch full documents for invoices missing their child `taxes` table."""
    hydrated = 0
    for name in store.names_missing_taxes(site_id, doctype, limit=limit):
        try:
            doc = client.get_doc(doctype, name)
        except FrappeError:
            continue
        if doc:
            written = store.upsert_docs(site_id, doctype, [doc])
            hydrated += written
    return hydrated
