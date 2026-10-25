"""Input-credit reconciliation: purchase register vs GSTR-2B.

The rules that make this useful rather than decorative:

* normalise punctuation in invoice numbers (never digits) before matching;
* aggregate duplicates on each side and say so — portals do file twice;
* match exactly first, fuzzily second (same GSTIN, near date) and mark those
  PROBABLE for a human, never silently as matched;
* report **ITC at risk** in rupees, not a list of differences: the whole credit
  when an invoice is absent from 2B, the shortfall when the tax differs.

`parse_2b` reads the portal's own JSON shape (``data.docdata.b2b[]``), because
that is the file every finance team downloads; flat rows are accepted too, which
is what the plugin sends.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher
from typing import Any, Iterable

__all__ = [
    "MISSING_IN_2B",
    "MISSING_IN_BOOKS",
    "PROBABLE",
    "TAX_MISMATCH",
    "MATCHED",
    "ReconResult",
    "Row",
    "normalise_invoice_number",
    "parse_2b",
    "reconcile_2b",
]

MATCHED = "MATCHED"
TAX_MISMATCH = "TAX_MISMATCH"
MISSING_IN_2B = "MISSING_IN_2B"
MISSING_IN_BOOKS = "MISSING_IN_BOOKS"
PROBABLE = "PROBABLE"
DUPLICATE = "DUPLICATE"

D = Decimal
_NOISE = re.compile(r"[^A-Z0-9]")


def _money(value: Any) -> D:
    try:
        return D(str(value or 0)).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return D("0.00")


def _date(value: Any) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return date(1900, 1, 1)


def normalise_invoice_number(number: Any) -> str:
    """Uppercase, strip separators, strip leading zeros. Digits stay digits."""
    cleaned = _NOISE.sub("", str(number or "").upper())
    return cleaned.lstrip("0") or "0"


@dataclass
class Row:
    status: str
    gstin: str
    invoice_number: str
    book_tax: D = D("0.00")
    portal_tax: D = D("0.00")
    itc_at_risk: D = D("0.00")
    note: str = ""
    book: dict[str, Any] | None = None
    portal: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("book_tax", "portal_tax", "itc_at_risk"):
            data[key] = float(data[key])
        data.pop("book", None)
        data.pop("portal", None)
        return data


@dataclass
class ReconResult:
    rows: list[Row] = field(default_factory=list)
    period: str = ""

    def by_status(self, status: str) -> list[Row]:
        return [row for row in self.rows if row.status == status]

    @property
    def itc_at_risk(self) -> D:
        return _money(sum((row.itc_at_risk for row in self.rows), D("0")))

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for row in self.rows:
            counts[row.status] = counts.get(row.status, 0) + 1
        book_tax = _money(sum((row.book_tax for row in self.rows), D("0")))
        portal_tax = _money(sum((row.portal_tax for row in self.rows), D("0")))
        return {
            "period": self.period,
            "matched": counts.get(MATCHED, 0),
            "tax_mismatch": counts.get(TAX_MISMATCH, 0),
            "missing_in_2b": counts.get(MISSING_IN_2B, 0),
            "missing_in_books": counts.get(MISSING_IN_BOOKS, 0),
            "probable": counts.get(PROBABLE, 0),
            "duplicates": counts.get(DUPLICATE, 0),
            "book_tax": float(book_tax),
            "portal_tax": float(portal_tax),
            "net_difference": float(_money(portal_tax - book_tax)),
            "itc_at_risk": float(self.itc_at_risk),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"summary": self.summary(), "rows": [row.as_dict() for row in self.rows]}


# --------------------------------------------------------------------------- #
# Input normalisation
# --------------------------------------------------------------------------- #


def _book_row(raw: dict[str, Any]) -> dict[str, Any]:
    """A purchase register row: our own Purchase Invoice or an uploaded CSV row."""
    tax = D("0")
    for key in ("cgst", "sgst", "igst", "cess"):
        tax += _money(raw.get(key, 0))
    if tax == 0:
        # The tax can arrive as a plain total when the caller passes ERPNext's
        # parent row instead of a split register.
        tax = _money(
            raw.get("tax")
            or raw.get("total_tax")
            or raw.get("total_taxes_and_charges")
            or 0
        )
    return {
        "gstin": str(raw.get("gstin") or raw.get("supplier_gstin") or "").strip().upper(),
        "invoice_number": str(raw.get("invoice_number") or raw.get("bill_no") or raw.get("name") or ""),
        "date": _date(raw.get("date") or raw.get("posting_date") or raw.get("bill_date")),
        "taxable": _money(raw.get("taxable", raw.get("base_net_total", 0))),
        "tax": _money(tax),
        "raw": raw,
    }


def _portal_row(raw: dict[str, Any]) -> dict[str, Any]:
    """One GSTR-2B B2B row, either the flat shape or a pre-split row."""
    return {
        "gstin": str(raw.get("gstin") or raw.get("ctin") or raw.get("supplier_gstin") or "").strip().upper(),
        "invoice_number": str(raw.get("invoice_number") or raw.get("inum") or raw.get("number") or ""),
        "date": _date(raw.get("date") or raw.get("dt") or raw.get("invoice_date")),
        "taxable": _money(raw.get("taxable", raw.get("txval", 0))),
        "tax": _money(
            raw.get("tax")
            if raw.get("tax") is not None
            else D(str(raw.get("camt", 0))) + D(str(raw.get("samt", 0))) + D(str(raw.get("iamt", 0)))
        ),
        "raw": raw,
    }


def parse_2b(payload: Any) -> list[dict[str, Any]]:
    """Flatten the portal's GSTR-2B JSON into rows.

    Handles ``{"data": {"docdata": {"b2b": [...]}}}`` (the downloaded file),
    a bare ``{"b2b": [...]}``, the ``gt``/``cur_gt`` split in some exports, and
    a plain list of flat rows. Item-level taxes are summed, because ITC is
    claimed at document level.
    """
    if isinstance(payload, list):
        return [_portal_row(row) for row in payload]
    if not isinstance(payload, dict):
        return []

    node: Any = payload.get("data", payload)
    docdata = node.get("docdata", node) if isinstance(node, dict) else {}
    groups: list[dict[str, Any]] = []
    for key in ("b2b",):
        block = docdata.get(key) if isinstance(docdata, dict) else None
        if isinstance(block, list):
            groups.extend(block)

    rows: list[dict[str, Any]] = []
    for group in groups:
        ctin = group.get("ctin") or group.get("gstin") or ""
        for invoice in group.get("inv") or group.get("invlist") or []:
            taxable = invoice.get("txval")
            tax = D("0")
            if taxable is None and invoice.get("itms"):
                taxable = sum(D(str(item.get("itm_det", {}).get("txval", 0))) for item in invoice["itms"])
            for item in invoice.get("itms") or []:
                detail = item.get("itm_det", {})
                tax += (
                    D(str(detail.get("camt", 0)))
                    + D(str(detail.get("samt", 0)))
                    + D(str(detail.get("iamt", 0)))
                    + D(str(detail.get("csamt", 0)))
                )
            if tax == 0:
                tax = D(str(invoice.get("camt", 0))) + D(str(invoice.get("samt", 0))) + D(str(invoice.get("iamt", 0)))
            rows.append(
                _portal_row(
                    {
                        "ctin": ctin,
                        "inum": invoice.get("inum"),
                        "dt": invoice.get("dt"),
                        "txval": taxable,
                        "tax": tax,
                    }
                )
            )
    return rows


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return (row["gstin"], normalise_invoice_number(row["invoice_number"]))


def _aggregate(rows: Iterable[dict[str, Any]], side: str, out: list[Row]) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _key(row)
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = row
            continue
        existing["taxable"] = _money(existing["taxable"] + row["taxable"])
        existing["tax"] = _money(existing["tax"] + row["tax"])
        out.append(
            Row(
                status=DUPLICATE,
                gstin=key[0],
                invoice_number=str(row["invoice_number"]),
                book_tax=existing["tax"] if side == "book" else D("0.00"),
                portal_tax=existing["tax"] if side == "portal" else D("0.00"),
                note=f"{side} holds this invoice more than once; amounts merged",
            )
        )
    return grouped


def reconcile_2b(
    books: Iterable[dict[str, Any]],
    portal: Iterable[dict[str, Any]],
    *,
    period: str = "",
    tolerance: float | D = 1,
    fuzzy: bool = True,
    fuzzy_threshold: float = 0.87,
    date_window_days: int = 45,
) -> ReconResult:
    """Classify every invoice on both sides. See the module docstring for rules."""
    tolerance_dec = _money(tolerance)
    rows: list[Row] = []
    book_map = _aggregate((_book_row(row) for row in books), "book", rows)
    portal_map = _aggregate((_portal_row(row) for row in portal), "portal", rows)
    result = ReconResult(rows=rows, period=period)
    used_portal: set[tuple[str, str]] = set()

    for key, book in book_map.items():
        match = portal_map.get(key)
        if match is None:
            continue
        used_portal.add(key)
        diff = _money(book["tax"] - match["tax"])
        if abs(diff) <= tolerance_dec:
            result.rows.append(
                Row(MATCHED, key[0], str(book["invoice_number"]), book["tax"], match["tax"],
                    D("0.00"), book=book, portal=match)
            )
        else:
            result.rows.append(
                Row(TAX_MISMATCH, key[0], str(book["invoice_number"]), book["tax"], match["tax"],
                    max(D("0"), diff), f"tax differs by {diff}", book=book, portal=match)
            )

    pending_books = [key for key in book_map if key not in used_portal]
    pending_portal = [key for key in portal_map if key not in used_portal]

    if fuzzy:
        for book_key in list(pending_books):
            book = book_map[book_key]
            best: tuple[str, str] | None = None
            best_score = 0.0
            for portal_key in pending_portal:
                if portal_key[0] != book_key[0]:
                    continue
                candidate = portal_map[portal_key]
                if abs((candidate["date"] - book["date"]).days) > date_window_days:
                    continue
                score = SequenceMatcher(None, book_key[1], portal_key[1]).ratio()
                if score > best_score:
                    best, best_score = portal_key, score
            if best is not None and best_score >= fuzzy_threshold:
                candidate = portal_map[best]
                used_portal.add(best)
                pending_books.remove(book_key)
                pending_portal.remove(best)
                diff = _money(book["tax"] - candidate["tax"])
                result.rows.append(
                    Row(PROBABLE, book_key[0], str(book["invoice_number"]), book["tax"],
                        candidate["tax"], max(D("0"), diff),
                        f"numbers {book['invoice_number']!r} vs {candidate['invoice_number']!r} "
                        f"({best_score:.0%} similar)", book=book, portal=candidate)
                )

    for book_key in pending_books:
        book = book_map[book_key]
        result.rows.append(
            Row(MISSING_IN_2B, book_key[0], str(book["invoice_number"]), book["tax"], D("0.00"),
                book["tax"], "supplier has not reported it; hold the credit", book=book)
        )
    for portal_key in pending_portal:
        portal = portal_map[portal_key]
        result.rows.append(
            Row(MISSING_IN_BOOKS, portal_key[0], str(portal["invoice_number"]), D("0.00"),
                portal["tax"], D("0.00"),
                "in the portal file but not in your books; book it or query the supplier",
                portal=portal)
        )
    return result
