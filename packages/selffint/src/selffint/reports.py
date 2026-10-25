"""The four reports, computed from mirror documents.

Pure functions over lists of dictionaries — no database, no HTTP, no clock
except the `as_of` you pass in. That is what makes them testable and what lets
the same code serve the API, the CLI and a test fixture.

Field names follow ERPNext's own documents (`Sales Invoice`, `Salary Slip`), so
the payloads in the mirror are stored as the site returned them and nothing has
to be translated on the way in.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

__all__ = ["DASHBOARD_DOCTYPES", "ar_aging", "gst_summary", "payroll_summary"]

D = Decimal
_TWO = D("0.01")


def _money(value: Any) -> D:
    try:
        return D(str(value or 0)).quantize(_TWO, rounding=ROUND_HALF_UP)
    except Exception:
        return D("0.00")


def _num(value: Any) -> Decimal:
    try:
        return D(str(value))
    except Exception:
        return D("0")


def _date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _submitted(doc: dict[str, Any]) -> bool:
    """Only submitted documents are books. Drafts and cancelled are not."""
    try:
        return int(doc.get("docstatus", 0)) == 1
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- #
# Receivables
# --------------------------------------------------------------------------- #

BUCKETS: tuple[tuple[str, str, int, float], ...] = (
    ("current", "Not yet due", float("-inf"), 0),
    ("d1_30", "1–30 days", 1, 30),
    ("d31_60", "31–60 days", 31, 60),
    ("d61_90", "61–90 days", 61, 90),
    ("d90_plus", "Over 90 days", 91, float("inf")),
)

DASHBOARD_DOCTYPES = ("Sales Invoice", "Purchase Invoice", "Customer", "Supplier", "Employee", "Salary Slip")


def ar_aging(invoices: Iterable[dict[str, Any]], as_of: str | date | None = None) -> dict[str, Any]:
    """Age the receivables book by days *past due*, not by invoice age.

    90 % of "aging" reports age the invoice; the number a finance team collects
    on is days past due, so that is what the buckets read.
    """
    today = _date(as_of) or date.today()
    buckets = {key: {"key": key, "label": label, "amount": D("0.00"), "count": 0} for key, label, _, _ in BUCKETS}
    by_customer: dict[str, dict[str, Any]] = {}
    total = D("0.00")
    overdue = D("0.00")
    counted = 0

    for invoice in invoices:
        if not _submitted(invoice):
            continue
        outstanding = _money(invoice.get("outstanding_amount", 0))
        if outstanding <= 0:
            continue
        counted += 1
        total += outstanding
        due = _date(invoice.get("due_date")) or _date(invoice.get("posting_date")) or today
        days_late = (today - due).days
        key = next(k for k, _label, low, high in BUCKETS if low <= days_late <= high)
        buckets[key]["amount"] += outstanding
        buckets[key]["count"] += 1
        if days_late > 0:
            overdue += outstanding
        customer = str(invoice.get("customer") or invoice.get("party") or "—")
        entry = by_customer.setdefault(
            customer, {"customer": customer, "amount": D("0.00"), "oldest_days": 0, "invoices": 0}
        )
        entry["amount"] += outstanding
        entry["invoices"] += 1
        entry["oldest_days"] = max(entry["oldest_days"], max(0, days_late))

    customers = sorted(by_customer.values(), key=lambda entry: entry["amount"], reverse=True)
    return {
        "as_of": today.isoformat(),
        "currency": "INR",
        "total": float(_money(total)),
        "overdue": float(_money(overdue)),
        "open_invoices": counted,
        "buckets": [
            {
                "key": bucket["key"],
                "label": bucket["label"],
                "amount": float(_money(bucket["amount"])),
                "count": bucket["count"],
                "share": float(_money(bucket["amount"] / total * 100)) if total else 0.0,
            }
            for bucket in buckets.values()
        ],
        "by_customer": [
            {
                "customer": entry["customer"],
                "amount": float(_money(entry["amount"])),
                "oldest_days": entry["oldest_days"],
                "invoices": entry["invoices"],
            }
            for entry in customers[:25]
        ],
    }


# --------------------------------------------------------------------------- #
# GST
# --------------------------------------------------------------------------- #

_HEADS = ("CGST", "SGST", "IGST", "CESS")


def _tax_rows(invoice: dict[str, Any]) -> list[tuple[str, Decimal, Decimal]]:
    """(head, rate, amount) from the child `taxes` table.

    ERPNext stores a tax as an account head such as `IGST - ACME`, not a head
    enum. Classifying by substring is what the data actually supports; documents
    hydrated from the site always carry `taxes`, and the list endpoint's
    documents fall back to the document total (reported as `unallocated`).
    """
    rows: list[tuple[str, Decimal, Decimal]] = []
    for tax in invoice.get("taxes") or []:
        amount = _money(tax.get("tax_amount", tax.get("amount", 0)))
        head = ""
        account = str(tax.get("account_head") or "").upper()
        charge = str(tax.get("charge_type") or "").upper()
        for candidate in _HEADS:
            if candidate in account or candidate in charge:
                head = candidate
                break
        if not head and charge in {"ON NET TOTAL", "ACTUAL", "ON PREVIOUS ROW TOTAL AND NET TOTAL"}:
            head = "OTHER"
        if not head:
            head = "OTHER"
        rows.append((head, _num(tax.get("rate", 0)), amount))
    return rows


def gst_summary(
    invoices: Iterable[dict[str, Any]],
    *,
    date_from: str | date | None = None,
    date_to: str | date | None = None,
) -> dict[str, Any]:
    """Output tax from the sales book, grouped by rate.

    Returns `unallocated` separately instead of quietly folding it into a rate:
    a document synced from the list endpoint has no child taxes, and pretending
    otherwise would produce a confident, wrong GSTR-3B.
    """
    start = _date(date_from)
    end = _date(date_to)
    by_rate: dict[str, dict[str, Any]] = {}
    unallocated = D("0.00")
    totals = {"taxable": D("0.00"), "cgst": D("0.00"), "sgst": D("0.00"), "igst": D("0.00"), "cess": D("0.00")}
    invoices_counted = 0
    exempt = D("0.00")

    for invoice in invoices:
        if not _submitted(invoice):
            continue
        posting = _date(invoice.get("posting_date"))
        if start and (posting is None or posting < start):
            continue
        if end and (posting is None or posting > end):
            continue
        invoices_counted += 1
        taxable = _money(invoice.get("base_net_total") or invoice.get("net_total") or 0)
        tax_rows = _tax_rows(invoice)
        taxes_total = _money(invoice.get("total_taxes_and_charges", 0))
        if not tax_rows:
            if taxes_total > 0:
                unallocated += taxes_total
            elif taxable > 0:
                exempt += taxable
            continue

        grouped: dict[Decimal, dict[str, Decimal]] = {}
        for head, rate, amount in tax_rows:
            bucket = grouped.setdefault(rate, {key: D("0.00") for key in ("cgst", "sgst", "igst", "cess")})
            if head == "CGST":
                bucket["cgst"] += amount
            elif head == "SGST":
                bucket["sgst"] += amount
            elif head == "IGST":
                bucket["igst"] += amount
            elif head == "CESS":
                bucket["cess"] += amount
            else:
                unallocated += amount

        # Split the taxable value across rate buckets proportionally to tax —
        # an invoice with two rates pays tax at both, and apportioning by tax is
        # the only split the document itself proves.
        rated_total = sum((sum(b.values()) for b in grouped.values()), D("0.00"))
        for rate, bucket in grouped.items():
            share = (sum(bucket.values()) / rated_total) if rated_total else D("0")
            entry = by_rate.setdefault(
                str(rate),
                {"rate": float(rate), "taxable": D("0.00"), "cgst": D("0.00"), "sgst": D("0.00"),
                 "igst": D("0.00"), "cess": D("0.00"), "invoices": 0},
            )
            entry["taxable"] += _money(taxable * share)
            entry["invoices"] += 1
            for key in ("cgst", "sgst", "igst", "cess"):
                entry[key] += bucket[key]
                totals[key] += bucket[key]
        totals["taxable"] += taxable

    total_tax = sum(totals.values()) - totals["taxable"]
    return {
        "from": start.isoformat() if start else "",
        "to": end.isoformat() if end else "",
        "invoices": invoices_counted,
        "rows": [
            {
                "rate": row["rate"],
                "taxable": float(_money(row["taxable"])),
                "cgst": float(_money(row["cgst"])),
                "sgst": float(_money(row["sgst"])),
                "igst": float(_money(row["igst"])),
                "cess": float(_money(row["cess"])),
                "total": float(_money(sum((row[k] for k in ("cgst", "sgst", "igst", "cess")), D("0")))),
                "invoices": row["invoices"],
            }
            for row in sorted(by_rate.values(), key=lambda entry: entry["rate"])
        ],
        "taxable": float(_money(totals["taxable"])),
        "cgst": float(_money(totals["cgst"])),
        "sgst": float(_money(totals["sgst"])),
        "igst": float(_money(totals["igst"])),
        "cess": float(_money(totals["cess"])),
        "total_tax": float(_money(total_tax)),
        "exempt": float(_money(exempt)),
        "unallocated": float(_money(unallocated)),
    }


# --------------------------------------------------------------------------- #
# Payroll cost
# --------------------------------------------------------------------------- #


def payroll_summary(slips: Iterable[dict[str, Any]], *, month: str = "") -> dict[str, Any]:
    """Cost of payroll from submitted Salary Slips.

    Reports what the site recorded; it does not recompute PF/ESI/PT/TDS. That
    line is deliberate — statutory arithmetic belongs with the payroll engine,
    and a second implementation is a second answer.
    """
    prefix = (month or "").strip()[:7]
    by_employee: dict[str, dict[str, Any]] = {}
    gross = deductions = net = employer = D("0.00")
    counted = 0

    for slip in slips:
        if not _submitted(slip):
            continue
        posting = str(slip.get("posting_date") or "")[:10]
        if prefix and not posting.startswith(prefix):
            continue
        counted += 1
        gross += _money(slip.get("gross_pay", 0))
        deductions += _money(slip.get("total_deduction", 0))
        net += _money(slip.get("net_pay", 0))
        employer += _money(
            slip.get("total_employer_contribution")
            or slip.get("employer_contribution")
            or 0
        )
        who = str(slip.get("employee_name") or slip.get("employee") or "—")
        entry = by_employee.setdefault(
            who, {"employee": who, "gross": D("0.00"), "deductions": D("0.00"), "net": D("0.00"), "slips": 0}
        )
        entry["gross"] += _money(slip.get("gross_pay", 0))
        entry["deductions"] += _money(slip.get("total_deduction", 0))
        entry["net"] += _money(slip.get("net_pay", 0))
        entry["slips"] += 1

    return {
        "month": prefix,
        "slips": counted,
        "gross": float(_money(gross)),
        "deductions": float(_money(deductions)),
        "net": float(_money(net)),
        "employer_contribution": float(_money(employer)),
        "cost_to_company": float(_money(gross + employer)),
        "employees": [
            {
                "employee": entry["employee"],
                "gross": float(_money(entry["gross"])),
                "deductions": float(_money(entry["deductions"])),
                "net": float(_money(entry["net"])),
                "slips": entry["slips"],
            }
            for entry in sorted(by_employee.values(), key=lambda e: e["gross"], reverse=True)
        ],
    }
