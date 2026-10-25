"""GSTR-2B reconciliation: the portal's JSON, the four buckets, ITC at risk."""

from __future__ import annotations

from selffint.demo import DEMO_2B, demo_documents
from selffint.recon import (
    MATCHED,
    MISSING_IN_2B,
    MISSING_IN_BOOKS,
    PROBABLE,
    TAX_MISMATCH,
    normalise_invoice_number,
    parse_2b,
    reconcile_2b,
)


def books():  # noqa: ANN201
    return [
        {
            "name": "PINV-1",
            "supplier_gstin": "33AAACC1206D1ZN",
            "bill_no": "KT/118",
            "posting_date": "2026-08-12",
            "base_net_total": 60000,
            "total_taxes_and_charges": 10800,
        },
        {
            "name": "PINV-2",
            "supplier_gstin": "29AABCU9603R1ZJ",
            "bill_no": "DM-4471",
            "posting_date": "2026-09-05",
            "base_net_total": 150000,
            "total_taxes_and_charges": 27000,
        },
        {
            "name": "PINV-3",
            "supplier_gstin": "33AAACC1206D1ZN",
            "bill_no": "KT/131",
            "posting_date": "2026-09-18",
            "base_net_total": 30000,
            "total_taxes_and_charges": 5400,
        },
    ]


def test_normalisation_cleans_punctuation_but_never_digits():
    assert normalise_invoice_number("KT/118") == "KT118"
    assert normalise_invoice_number("  kt-118 ") == "KT118"
    assert normalise_invoice_number("00042") == "42"
    assert normalise_invoice_number("") == "0"


def test_every_demo_book_invoice_lands_in_a_bucket():
    result = reconcile_2b(books(), DEMO_2B, period="2026-09")
    summary = result.summary()
    assert summary["matched"] == 1                 # KT/118 agrees
    assert summary["tax_mismatch"] == 1            # DM-4471: 27,000 booked vs 18,000 in 2B
    assert summary["missing_in_2b"] == 1           # KT/131 never filed
    assert summary["missing_in_books"] == 1        # GUJ-77 not booked


def test_itc_at_risk_is_the_shortfall_plus_the_absent_invoice():
    result = reconcile_2b(books(), DEMO_2B)
    # 9,000 short on DM-4471 plus the whole 5,400 on KT/131.
    assert result.summary()["itc_at_risk"] == 14400.0


def test_tolerance_absorbs_rounding_only():
    portal = [{"gstin": "33AAACC1206D1ZN", "invoice_number": "KT/118", "date": "2026-08-12",
               "taxable": 60000, "tax": 10800.99}]
    assert reconcile_2b(books()[:1], portal, tolerance=1).summary()["matched"] == 1
    assert reconcile_2b(books()[:1], portal, tolerance=0).summary()["tax_mismatch"] == 1


def test_duplicates_are_merged_and_declared():
    portal = [
        {"gstin": "33AAACC1206D1ZN", "invoice_number": "KT/118", "date": "2026-08-12",
         "taxable": 60000, "tax": 10800},
        {"gstin": "33AAACC1206D1ZN", "invoice_number": "KT/118", "date": "2026-08-12",
         "taxable": 60000, "tax": 10800},
    ]
    summary = reconcile_2b(books()[:1], portal).summary()
    assert summary["duplicates"] == 1
    assert summary["tax_mismatch"] == 1


def test_fuzzy_match_stays_inside_one_gstin():
    portal = [{"gstin": "29AABCU9603R1ZJ", "invoice_number": "DM-4471A", "date": "2026-09-06",
               "taxable": 150000, "tax": 27000}]
    assert reconcile_2b(books()[1:2], portal).summary()["probable"] == 1
    other = [{"gstin": "33AAACC1206D1ZN", "invoice_number": "DM-4471A", "date": "2026-09-06",
              "taxable": 150000, "tax": 27000}]
    assert reconcile_2b(books()[1:2], other).summary()["probable"] == 0


def test_fuzzy_respects_the_date_window():
    portal = [{"gstin": "29AABCU9603R1ZJ", "invoice_number": "DM-4471A", "date": "2027-03-06",
               "taxable": 150000, "tax": 27000}]
    result = reconcile_2b(books()[1:2], portal, date_window_days=10)
    assert result.summary()["probable"] == 0
    assert result.summary()["missing_in_2b"] == 1


def test_parse_2b_reads_the_downloaded_portal_file():
    payload = {
        "data": {
            "docdata": {
                "b2b": [
                    {
                        "ctin": "33AAACC1206D1ZN",
                        "inv": [
                            {
                                "inum": "KT/118",
                                "dt": "12-08-2026",
                                "val": 70800,
                                "txval": 60000,
                                "itms": [
                                    {"itm_det": {"rt": 9, "txval": 60000, "camt": 5400, "samt": 5400}}
                                ],
                            }
                        ],
                    }
                ]
            }
        }
    }
    rows = parse_2b(payload)
    assert len(rows) == 1
    assert rows[0]["gstin"] == "33AAACC1206D1ZN"
    assert rows[0]["invoice_number"] == "KT/118"
    assert float(rows[0]["tax"]) == 10800.0
    assert rows[0]["date"].isoformat() == "2026-08-12"


def test_parse_2b_accepts_a_bare_b2b_block_and_flat_rows():
    bare = {"b2b": [{"ctin": "X", "inv": [{"inum": "1", "dt": "01-09-2026", "txval": 100, "camt": 9, "samt": 9}]}]}
    assert float(parse_2b(bare)[0]["tax"]) == 18.0
    flat = [{"gstin": "Y", "invoice_number": "2", "date": "2026-09-01", "taxable": 5, "tax": 0.9}]
    assert float(parse_2b(flat)[0]["tax"]) == 0.9
    assert parse_2b("nonsense") == []


def test_result_serialises_for_the_wire():
    payload = reconcile_2b(books(), DEMO_2B).to_dict()
    assert set(payload) == {"summary", "rows"}
    assert isinstance(payload["rows"][0]["itc_at_risk"], float)
    assert "book" not in payload["rows"][0]


def test_demo_purchases_match_the_demo_2b_file():
    purchases = [
        {
            "name": doc["name"],
            "supplier_gstin": doc["supplier_gstin"],
            "bill_no": doc["bill_no"],
            "posting_date": doc["posting_date"],
            "base_net_total": doc["base_net_total"],
            "total_taxes_and_charges": doc["total_taxes_and_charges"],
        }
        for doc in demo_documents()["Purchase Invoice"]
    ]
    summary = reconcile_2b(purchases, DEMO_2B).summary()
    assert summary["book_tax"] == 10800.0 + 27000.0 + 5400.0
    assert summary["portal_tax"] == 10800.0 + 18000.0 + 14400.0
    statuses = {row.status for row in reconcile_2b(purchases, DEMO_2B).rows}
    assert statuses == {MATCHED, TAX_MISMATCH, MISSING_IN_2B, MISSING_IN_BOOKS}
