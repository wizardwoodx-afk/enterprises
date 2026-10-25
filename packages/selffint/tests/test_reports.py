"""Reports: receivables aging, GST by rate, payroll cost.

Every case here is a decision about what a finance number means, so the tests
read as statements: drafts are not books, aging is past-due not invoice age,
unallocated tax is shown rather than guessed.
"""

from __future__ import annotations

from datetime import date

from selffint.demo import demo_documents
from selffint.reports import ar_aging, gst_summary, payroll_summary


def demo(doctype: str):  # noqa: ANN201
    return demo_documents()[doctype]


def test_aging_buckets_by_days_past_due_not_invoice_age():
    report = ar_aging(demo("Sales Invoice"), as_of="2026-10-20")
    buckets = {bucket["key"]: bucket for bucket in report["buckets"]}
    # SINV-0003 due 2 Oct, as-of 20 Oct -> 18 days past due -> the 1-30 bucket.
    assert buckets["d1_30"]["amount"] == 236000.0
    # SINV-0002 due 9 Sep -> 41 days past due -> 31-60.
    assert buckets["d31_60"]["amount"] == 52500.0
    # SINV-0004 due 19 Jun -> 123 days past due -> over 90.
    assert buckets["d90_plus"]["amount"] == 29500.0
    # SINV-0006 due 20 Oct -> not yet due on the as-of date.
    assert buckets["current"]["amount"] == 47200.0


def test_not_yet_due_lands_in_current():
    report = ar_aging(demo("Sales Invoice"), as_of="2026-09-01")
    buckets = {bucket["key"]: bucket for bucket in report["buckets"]}
    assert buckets["current"]["amount"] > 0
    assert buckets["d61_90"]["count"] > 0   # SINV-0004 is 74 days past due on this date


def test_drafts_and_paid_invoices_are_not_receivables():
    report = ar_aging(demo("Sales Invoice"), as_of="2026-10-20")
    # The draft SINV-0005 is 106,200 and the paid SINV-0001 is nil.
    assert report["total"] == 52500.0 + 236000.0 + 29500.0 + 47200.0
    assert report["open_invoices"] == 4


def test_aging_totals_add_up_to_the_buckets():
    report = ar_aging(demo("Sales Invoice"), as_of="2026-10-20")
    assert round(sum(bucket["amount"] for bucket in report["buckets"]), 2) == report["total"]


def test_overdue_is_a_subset_of_total():
    report = ar_aging(demo("Sales Invoice"), as_of="2026-10-20")
    assert 0 < report["overdue"] <= report["total"]


def test_customer_view_is_sorted_by_exposure():
    report = ar_aging(demo("Sales Invoice"), as_of="2026-10-20")
    amounts = [entry["amount"] for entry in report["by_customer"]]
    assert amounts == sorted(amounts, reverse=True)
    assert {entry["customer"] for entry in report["by_customer"]} == {
        "Acme Textiles", "Nilgiri Foods", "Bharat Components"
    }


def test_aging_defaults_to_today_without_a_crash():
    report = ar_aging(demo("Sales Invoice"))
    assert report["as_of"] == date.today().isoformat()


def test_empty_book_is_zero_not_a_division_by_zero():
    report = ar_aging([], as_of="2026-10-20")
    assert report["total"] == 0 and report["buckets"][0]["share"] == 0.0


def test_gst_groups_the_sales_book_by_rate():
    report = gst_summary(demo("Sales Invoice"))
    rates = {row["rate"]: row for row in report["rows"]}
    assert set(rates) == {9.0, 2.5, 18.0}
    assert rates[9.0]["cgst"] == 9000.0 + 2250.0
    assert rates[18.0]["igst"] == 36000.0


def test_gst_totals_match_the_rows():
    report = gst_summary(demo("Sales Invoice"))
    assert round(sum(row["cgst"] for row in report["rows"]), 2) == report["cgst"]
    assert round(sum(row["sgst"] for row in report["rows"]), 2) == report["sgst"]


def test_gst_excludes_drafts():
    with_draft = gst_summary(demo("Sales Invoice"))
    only_draft = gst_summary([demo("Sales Invoice")[4]])
    assert with_draft["invoices"] == 5
    assert only_draft["invoices"] == 0


def test_gst_respects_the_date_window():
    report = gst_summary(demo("Sales Invoice"), date_from="2026-09-01", date_to="2026-09-30")
    assert report["invoices"] == 2          # SINV-0003 and SINV-0006
    assert report["from"] == "2026-09-01" and report["to"] == "2026-09-30"


def test_a_document_without_child_taxes_is_reported_as_unallocated():
    """Guessing a rate for an un-hydrated invoice would be a confident, wrong return."""
    unhydrated = [doc for doc in demo("Sales Invoice") if doc["name"] == "SINV-2026-0006"]
    report = gst_summary(unhydrated)
    assert report["unallocated"] == 7200.0
    assert report["rows"] == []


def test_exempt_turnover_is_separate_from_taxable_turnover():
    report = gst_summary([{"name": "X", "posting_date": "2026-09-01", "docstatus": 1,
                           "base_net_total": 1000.0, "total_taxes_and_charges": 0.0}])
    assert report["exempt"] == 1000.0
    assert report["unallocated"] == 0.0


def test_tax_heads_are_classified_from_the_account_name():
    report = gst_summary([{
        "name": "X", "posting_date": "2026-09-01", "docstatus": 1,
        "base_net_total": 1000.0, "total_taxes_and_charges": 180.0,
        "taxes": [
            {"account_head": "Output Tax IGST - ACME", "rate": 18, "tax_amount": 180.0},
        ],
    }])
    assert report["igst"] == 180.0


def test_payroll_sums_submitted_slips():
    report = payroll_summary(demo("Salary Slip"))
    assert report["slips"] == 2
    assert report["gross"] == 97000.0
    assert report["net"] == 85360.0
    assert report["employer_contribution"] == 11640.0
    assert report["cost_to_company"] == 108640.0


def test_payroll_month_filter():
    assert payroll_summary(demo("Salary Slip"), month="2026-08")["slips"] == 0
    assert payroll_summary(demo("Salary Slip"), month="2026-09")["slips"] == 2


def test_payroll_ignores_drafts():
    draft = [{**demo("Salary Slip")[0], "docstatus": 0}]
    assert payroll_summary(draft)["slips"] == 0


def test_payroll_by_employee_is_sorted_by_gross():
    employees = payroll_summary(demo("Salary Slip"))["employees"]
    assert [entry["employee"] for entry in employees] == ["Meera Raghavan", "Arun Kumar"]
