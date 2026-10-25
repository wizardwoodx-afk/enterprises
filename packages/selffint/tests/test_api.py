"""The HTTP-shaped surface: routes, modes, validation, and the write-through.

`SelfFintApi` is plain Python — no server, no client library. That is deliberate:
the same object backs the ASGI mount, the CLI and these tests.
"""

from __future__ import annotations

import pytest

from selffint.api import SelfFintApi
from selffint.client import FrappeClient
from selffint.demo import DEMO_SITE_ID
from selffint.store import MirrorStore


@pytest.fixture()
def api():
    store = MirrorStore(":memory:")
    yield SelfFintApi(store)
    store.close()


def test_health(api):
    status, payload = api.dispatch("GET", "/health")
    assert status == 200 and payload["ok"] and payload["service"] == "selffint"


def test_first_run_seeds_the_demo_company(api):
    status, payload = api.dispatch("GET", "/status")
    assert status == 200
    assert payload["site"]["mode"] == "demo"
    assert payload["counts"]["Sales Invoice"] > 0
    assert any("demo" in warning.lower() for warning in payload["warnings"])


def test_status_never_returns_credentials(api):
    api.dispatch("GET", "/status")
    _, payload = api.dispatch("GET", "/sites")
    assert all("api_secret" not in site and "api_key" not in site for site in payload["sites"])


def test_invoice_list_carries_the_fields_the_page_renders(api):
    status, payload = api.dispatch("GET", "/invoices")
    assert status == 200
    invoice = payload["invoices"][0]
    assert set(invoice) >= {
        "name", "customer", "posting_date", "due_date", "grand_total",
        "outstanding_amount", "status", "docstatus", "currency",
    }


def test_invoice_search(api):
    _, payload = api.dispatch("GET", "/invoices?search=Nilgiri")
    assert payload["invoices"] and all("Nilgiri" in row["customer"] for row in payload["invoices"])


def test_parties_switch_between_customers_and_suppliers(api):
    _, customers = api.dispatch("GET", "/parties?kind=customer")
    _, suppliers = api.dispatch("GET", "/parties?kind=supplier")
    assert customers["parties"] and suppliers["parties"]
    assert customers["kind"] == "customer"


def test_aging_report_is_reachable_over_the_api(api):
    status, payload = api.dispatch("GET", "/reports/ar-aging?as_of=2026-10-20")
    assert status == 200
    assert payload["total"] > 0 and len(payload["buckets"]) == 5


def test_gst_report_is_reachable_over_the_api(api):
    status, payload = api.dispatch("GET", "/reports/gst?from=2026-07-01&to=2026-09-30")
    assert status == 200
    assert payload["total_tax"] > 0
    assert payload["unallocated"] > 0   # SINV-0006 was never hydrated, and says so


def test_payroll_report_is_reachable_over_the_api(api):
    status, payload = api.dispatch("GET", "/reports/payroll?month=2026-09")
    assert status == 200 and payload["slips"] == 2


def test_reconcile_uses_the_demo_2b_file(api):
    status, payload = api.dispatch("POST", "/reconcile/2b", {"use_demo": True, "period": "2026-09"})
    assert status == 200
    assert payload["summary"]["itc_at_risk"] == 14400.0
    assert payload["rows"]


def test_reconcile_without_input_is_a_400(api):
    status, payload = api.dispatch("POST", "/reconcile/2b", {})
    assert status == 400 and payload["ok"] is False


def test_document_lookup(api):
    _, invoices = api.dispatch("GET", "/invoices")
    name = invoices["invoices"][0]["name"]
    status, payload = api.dispatch("GET", f"/documents/Sales%20Invoice/{name}")
    assert status == 200 and payload["document"]["name"] == name


def test_document_lookup_for_something_absent_is_a_404(api):
    api.dispatch("GET", "/status")
    status, payload = api.dispatch("GET", "/documents/Sales%20Invoice/NOPE")
    assert status == 404 and payload["ok"] is False


def test_unknown_route_and_wrong_method(api):
    assert api.dispatch("GET", "/nope")[0] == 404
    assert api.dispatch("PUT", "/invoices")[0] == 405


def test_creating_an_invoice_in_demo_mode_stays_local(api):
    status, payload = api.dispatch(
        "POST",
        "/invoices",
        {
            "customer": "Acme Textiles",
            "posting_date": "2026-10-25",
            "items": [{"description": "Consulting", "qty": 2, "rate": 5000}],
        },
    )
    assert status == 201
    assert payload["document"]["docstatus"] == 0
    assert payload["document"]["base_net_total"] == 10000.0
    assert payload["document"]["grand_total"] == 11800.0
    _, listed = api.dispatch("GET", "/invoices?search=SINV-DEMO")
    assert listed["invoices"]


def test_invoice_validation(api):
    assert api.dispatch("POST", "/invoices", {})[0] == 400
    assert api.dispatch("POST", "/invoices", {"customer": "X"})[0] == 400
    assert api.dispatch("POST", "/invoices", {"customer": "X", "items": []})[0] == 400
    assert api.dispatch("POST", "/invoices", {"customer": "X", "items": [{"rate": 0}]})[0] == 400
    assert api.dispatch("POST", "/invoices", {"customer": "X", "items": [{"rate": "abc"}]})[0] == 400


def test_a_demo_site_can_be_removed(api):
    api.dispatch("GET", "/status")
    status, payload = api.dispatch("DELETE", f"/sites/{DEMO_SITE_ID}")
    assert status == 200 and payload["deleted"] == DEMO_SITE_ID
    assert api.dispatch("DELETE", f"/sites/{DEMO_SITE_ID}")[0] == 404


# ---------------------------------------------------------------- live mode


@pytest.fixture()
def live_api(fake_site):
    store = MirrorStore(":memory:")
    api = SelfFintApi(store, client_factory=lambda site: FrappeClient(site, transport=fake_site))
    yield api, fake_site, store
    store.close()


def test_connect_pings_the_site_then_stores_it(live_api):
    api, fake_site, store = live_api
    status, payload = api.dispatch(
        "POST",
        "/connect",
        {"url": "https://erp.example.com", "api_key": "k", "api_secret": "s", "label": "Prod"},
    )
    assert status == 200
    assert payload["user"] == "integration@demo.example"
    assert payload["site"]["mode"] == "live"
    assert store.get_site(payload["site"]["id"])["has_credentials"] is True


def test_connect_rejects_a_bad_credential_pair(live_api):
    api, fake_site, _ = live_api
    fake_site.fail.clear()

    class Refusing:
        def request(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            return 401, {}, b'{"message": "Invalid login"}'

    api._client_factory = lambda site: FrappeClient(site, transport=Refusing())  # noqa: SLF001
    status, payload = api.dispatch(
        "POST", "/connect", {"url": "https://erp.example.com", "api_key": "k", "api_secret": "bad"}
    )
    assert status == 502 and payload["ok"] is False


def test_connect_requires_all_three_values(live_api):
    api, _, _ = live_api
    assert api.dispatch("POST", "/connect", {"url": "https://x"})[0] == 400


def test_sync_pulls_into_the_mirror_and_reports_per_doctype(live_api):
    api, _, store = live_api
    _, connected = api.dispatch(
        "POST", "/connect", {"url": "https://erp.example.com", "api_key": "k", "api_secret": "s"}
    )
    site_id = connected["site"]["id"]
    status, payload = api.dispatch("POST", "/sync", {"site": site_id, "doctypes": ["Customer", "Sales Invoice"]})
    assert status == 200 and payload["ok"] is True
    assert store.count(site_id, "Customer") == 2
    assert store.count(site_id, "Sales Invoice") == 2


def test_sync_of_the_demo_site_is_a_no_op(live_api):
    api, _, _ = live_api
    api.dispatch("GET", "/status")
    status, payload = api.dispatch("POST", "/sync", {})
    assert status == 200 and payload["mode"] == "demo"


def test_creating_an_invoice_on_a_live_site_writes_through(live_api):
    api, fake_site, store = live_api
    _, connected = api.dispatch(
        "POST", "/connect", {"url": "https://erp.example.com", "api_key": "k", "api_secret": "s"}
    )
    site_id = connected["site"]["id"]
    status, payload = api.dispatch(
        "POST",
        "/invoices",
        {"customer": "Acme Textiles", "items": [{"description": "Work", "qty": 1, "rate": 2500}]},
    )
    assert status == 201
    posted = [
        call
        for call in fake_site.calls
        if call["method"] == "POST" and "Sales%20Invoice" in call["path"]
    ]
    assert posted and posted[-1]["body"]["docstatus"] == 0
    assert store.count(site_id, "Sales Invoice") == 1


def test_an_unreachable_site_fails_inside_the_sync_report(live_api):
    api, _, _ = live_api
    # Connect with a working site, then break the transport: the point is that a
    # site that *was* reachable going down surfaces as a payload, not a crash.
    api.dispatch("POST", "/connect", {"url": "https://erp.example.com", "api_key": "k", "api_secret": "s"})

    class Broken:
        def request(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            from selffint.client import FrappeError

            raise FrappeError("cannot reach the site: timed out")

    api._client_factory = lambda site: FrappeClient(site, transport=Broken())  # noqa: SLF001
    status, payload = api.dispatch("POST", "/sync", {})
    # Per-doctype isolation: the sync answers, and says which doctypes failed.
    assert status == 200 and payload["ok"] is False
    assert payload["doctypes"] and all(not entry["ok"] for entry in payload["doctypes"])
    assert "cannot reach" in payload["doctypes"][0]["error"]


def test_deleting_a_live_site_removes_its_documents(live_api):
    api, _, store = live_api
    _, connected = api.dispatch(
        "POST", "/connect", {"url": "https://erp.example.com", "api_key": "k", "api_secret": "s"}
    )
    site_id = connected["site"]["id"]
    api.dispatch("POST", "/sync", {"site": site_id, "doctypes": ["Customer"]})
    assert store.count(site_id, "Customer") == 2
    api.dispatch("DELETE", f"/sites/{site_id}")
    assert store.count(site_id, "Customer") == 0
