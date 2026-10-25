"""The demo site: a small Indian company, as documents.

SelfFint talks to ERPNext over HTTP, which means the page is useless until you
have a site with real books in it. That is a bad first run, and an impossible
test target. So the service can seed a **fixture company** into the mirror: a
read-only demonstration site, clearly labelled `mode: "demo"` everywhere it
surfaces, with GST-bearing invoices, overdue receivables, a purchase register
and a payroll run.

Nothing here pretends to be real data. The UI badges it, the API reports the
mode, and `DELETE /sites/<id>` removes it.
"""

from __future__ import annotations

from typing import Any

from .store import MirrorStore

__all__ = ["DEMO_2B", "DEMO_SITE_ID", "demo_documents", "seed_demo"]

DEMO_SITE_ID = "demo"
DEMO_LABEL = "Demo company — fixture data"

GSTIN_A = "33AAACC1206D1ZN"
GSTIN_B = "27AAPFU0939F1ZV"
GSTIN_C = "29AABCU9603R1ZJ"


def _tax(head: str, rate: float, amount: float) -> dict[str, Any]:
    return {"account_head": f"{head} - DEMO", "charge_type": "On Net Total",
            "rate": rate, "tax_amount": amount}


def demo_documents() -> dict[str, list[dict[str, Any]]]:
    """Doctypes → documents, shaped exactly as the Frappe REST API returns them."""
    customers = [
        {"name": "Acme Textiles", "customer_name": "Acme Textiles", "customer_group": "Commercial",
         "territory": "Tamil Nadu", "modified": "2026-09-01 09:00:00"},
        {"name": "Nilgiri Foods", "customer_name": "Nilgiri Foods", "customer_group": "Commercial",
         "territory": "Tamil Nadu", "modified": "2026-09-02 09:00:00"},
        {"name": "Bharat Components", "customer_name": "Bharat Components", "customer_group": "Commercial",
         "territory": "Maharashtra", "modified": "2026-09-03 09:00:00"},
    ]
    suppliers = [
        {"name": "Kaveri Traders", "supplier_name": "Kaveri Traders", "supplier_group": "Local",
         "territory": "Tamil Nadu", "modified": "2026-09-01 09:00:00"},
        {"name": "Deccan Metals", "supplier_name": "Deccan Metals", "supplier_group": "Local",
         "territory": "Karnataka", "modified": "2026-09-02 09:00:00"},
    ]

    sales = [
        # Intra-state, one rate, paid.
        {"name": "SINV-2026-0001", "customer": "Acme Textiles", "customer_name": "Acme Textiles",
         "posting_date": "2026-07-05", "due_date": "2026-08-04", "docstatus": 1, "status": "Paid",
         "base_net_total": 100000.0, "total_taxes_and_charges": 18000.0, "grand_total": 118000.0,
         "outstanding_amount": 0.0, "currency": "INR", "modified": "2026-07-05 10:00:00",
         "taxes": [_tax("CGST", 9, 9000.0), _tax("SGST", 9, 9000.0)]},
        # Intra-state, overdue 40 days at the as-of date used by the page.
        {"name": "SINV-2026-0002", "customer": "Nilgiri Foods", "customer_name": "Nilgiri Foods",
         "posting_date": "2026-08-10", "due_date": "2026-09-09", "docstatus": 1, "status": "Overdue",
         "base_net_total": 50000.0, "total_taxes_and_charges": 2500.0, "grand_total": 52500.0,
         "outstanding_amount": 52500.0, "currency": "INR", "modified": "2026-08-10 11:00:00",
         "taxes": [_tax("CGST", 2.5, 1250.0), _tax("SGST", 2.5, 1250.0)]},
        # Inter-state (Maharashtra), 18 %.
        {"name": "SINV-2026-0003", "customer": "Bharat Components", "customer_name": "Bharat Components",
         "posting_date": "2026-09-02", "due_date": "2026-10-02", "docstatus": 1, "status": "Unpaid",
         "base_net_total": 200000.0, "total_taxes_and_charges": 36000.0, "grand_total": 236000.0,
         "outstanding_amount": 236000.0, "currency": "INR", "modified": "2026-09-02 12:00:00",
         "taxes": [_tax("IGST", 18, 36000.0)]},
        # Deeply overdue, small.
        {"name": "SINV-2026-0004", "customer": "Acme Textiles", "customer_name": "Acme Textiles",
         "posting_date": "2026-05-20", "due_date": "2026-06-19", "docstatus": 1, "status": "Overdue",
         "base_net_total": 25000.0, "total_taxes_and_charges": 4500.0, "grand_total": 29500.0,
         "outstanding_amount": 29500.0, "currency": "INR", "modified": "2026-05-20 13:00:00",
         "taxes": [_tax("CGST", 9, 2250.0), _tax("SGST", 9, 2250.0)]},
        # Draft: must be excluded from every report.
        {"name": "SINV-2026-0005", "customer": "Nilgiri Foods", "customer_name": "Nilgiri Foods",
         "posting_date": "2026-10-01", "due_date": "2026-10-31", "docstatus": 0, "status": "Draft",
         "base_net_total": 90000.0, "total_taxes_and_charges": 16200.0, "grand_total": 106200.0,
         "outstanding_amount": 106200.0, "currency": "INR", "modified": "2026-10-01 09:00:00",
         "taxes": [_tax("CGST", 9, 8100.0), _tax("SGST", 9, 8100.0)]},
        # Hydration fixture: no child taxes, only the document total.
        {"name": "SINV-2026-0006", "customer": "Acme Textiles", "customer_name": "Acme Textiles",
         "posting_date": "2026-09-20", "due_date": "2026-10-20", "docstatus": 1, "status": "Unpaid",
         "base_net_total": 40000.0, "total_taxes_and_charges": 7200.0, "grand_total": 47200.0,
         "outstanding_amount": 47200.0, "currency": "INR", "modified": "2026-09-20 10:00:00"},
    ]

    purchases = [
        {"name": "PINV-2026-0001", "supplier": "Kaveri Traders", "supplier_name": "Kaveri Traders",
         "supplier_gstin": GSTIN_A, "bill_no": "KT/118", "posting_date": "2026-08-12", "docstatus": 1, "status": "Paid",
         "base_net_total": 60000.0, "total_taxes_and_charges": 10800.0, "grand_total": 70800.0,
         "outstanding_amount": 0.0, "currency": "INR", "modified": "2026-08-12 10:00:00",
         "taxes": [_tax("CGST", 9, 5400.0), _tax("SGST", 9, 5400.0)]},
        {"name": "PINV-2026-0002", "supplier": "Deccan Metals", "supplier_name": "Deccan Metals",
         "supplier_gstin": GSTIN_C, "bill_no": "DM-4471", "posting_date": "2026-09-05", "docstatus": 1, "status": "Unpaid",
         "base_net_total": 150000.0, "total_taxes_and_charges": 27000.0, "grand_total": 177000.0,
         "outstanding_amount": 177000.0, "currency": "INR", "modified": "2026-09-05 10:00:00",
         "taxes": [_tax("IGST", 18, 27000.0)]},
        {"name": "PINV-2026-0003", "supplier": "Kaveri Traders", "supplier_name": "Kaveri Traders",
         "supplier_gstin": GSTIN_A, "bill_no": "KT/131", "posting_date": "2026-09-18", "docstatus": 1, "status": "Unpaid",
         "base_net_total": 30000.0, "total_taxes_and_charges": 5400.0, "grand_total": 35400.0,
         "outstanding_amount": 35400.0, "currency": "INR", "modified": "2026-09-18 10:00:00",
         "taxes": [_tax("CGST", 9, 2700.0), _tax("SGST", 9, 2700.0)]},
    ]

    payments = [
        {"name": "PE-2026-0001", "party": "Acme Textiles", "party_type": "Customer",
         "posting_date": "2026-08-05", "paid_amount": 118000.0, "received_amount": 118000.0,
         "payment_type": "Receive", "docstatus": 1, "modified": "2026-08-05 15:00:00"},
        {"name": "PE-2026-0002", "party": "Kaveri Traders", "party_type": "Supplier",
         "posting_date": "2026-08-20", "paid_amount": 70800.0, "received_amount": 70800.0,
         "payment_type": "Pay", "docstatus": 1, "modified": "2026-08-20 15:00:00"},
    ]

    employees = [
        {"name": "EMP-001", "employee_name": "Meera Raghavan", "department": "Finance",
         "designation": "Accountant", "status": "Active", "modified": "2026-04-01 09:00:00"},
        {"name": "EMP-002", "employee_name": "Arun Kumar", "department": "Operations",
         "designation": "Supervisor", "status": "Active", "modified": "2026-04-01 09:00:00"},
    ]

    salary = [
        {"name": "SS-2026-09-001", "employee": "EMP-001", "employee_name": "Meera Raghavan",
         "posting_date": "2026-09-30", "gross_pay": 65000.0, "total_deduction": 7800.0,
         "net_pay": 57200.0, "total_employer_contribution": 7800.0, "status": "Submitted",
         "docstatus": 1, "modified": "2026-09-30 18:00:00"},
        {"name": "SS-2026-09-002", "employee": "EMP-002", "employee_name": "Arun Kumar",
         "posting_date": "2026-09-30", "gross_pay": 32000.0, "total_deduction": 3840.0,
         "net_pay": 28160.0, "total_employer_contribution": 3840.0, "status": "Submitted",
         "docstatus": 1, "modified": "2026-09-30 18:00:00"},
    ]

    return {
        "Customer": customers,
        "Supplier": suppliers,
        "Sales Invoice": sales,
        "Purchase Invoice": purchases,
        "Payment Entry": payments,
        "Employee": employees,
        "Salary Slip": salary,
    }


#: A GSTR-2B file for September, already flattened to rows, against which the
#: three demo purchases reconcile: one matches, one has a short tax, one is
#: absent — and one invoice (GUJ-77) was filed by a supplier this company never
#: booked. GSTINs are the suppliers' own, which is the whole point of the match.
DEMO_2B: list[dict[str, Any]] = [
    {"gstin": GSTIN_A, "invoice_number": "KT/118", "date": "2026-08-12", "taxable": 60000.0, "tax": 10800.0},
    {"gstin": GSTIN_C, "invoice_number": "DM-4471", "date": "2026-09-05", "taxable": 150000.0, "tax": 18000.0},
    {"gstin": GSTIN_B, "invoice_number": "GUJ-77", "date": "2026-09-11", "taxable": 80000.0, "tax": 14400.0},
]


def seed_demo(store: MirrorStore, site_id: str = DEMO_SITE_ID) -> dict[str, Any]:
    """Create (or refresh) the demo site in the mirror."""
    store.upsert_site(site_id, "demo://company", DEMO_LABEL, mode="demo")
    counts = {
        doctype: store.upsert_docs(site_id, doctype, docs)
        for doctype, docs in demo_documents().items()
    }
    return {"site": site_id, "mode": "demo", "documents": counts, "total": sum(counts.values())}
