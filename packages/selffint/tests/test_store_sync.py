"""The mirror and the sync: idempotence, incremental watermarks, isolation."""

from __future__ import annotations

import pytest

from selffint.client import FrappeClient, Site
from selffint.demo import seed_demo
from selffint.store import MirrorStore
from selffint.sync import sync_site


@pytest.fixture()
def store():
    store = MirrorStore(":memory:")
    store.upsert_site("s1", "https://erp.example.com", "Test site")
    yield store
    store.close()


def client(fake_site):  # noqa: ANN001, ANN201
    return FrappeClient(Site(url="https://erp.example.com", api_key="k", api_secret="s"), transport=fake_site)


def test_upsert_is_idempotent(store):
    doc = {"name": "A", "modified": "2026-09-01 10:00:00", "grand_total": 10}
    assert store.upsert_docs("s1", "Sales Invoice", [doc]) == 1
    assert store.upsert_docs("s1", "Sales Invoice", [doc]) == 1
    assert store.count("s1", "Sales Invoice") == 1


def test_upsert_updates_in_place(store):
    store.upsert_docs("s1", "Sales Invoice", [{"name": "A", "modified": "1", "grand_total": 10}])
    store.upsert_docs("s1", "Sales Invoice", [{"name": "A", "modified": "2", "grand_total": 20}])
    assert store.one("s1", "Sales Invoice", "A")["grand_total"] == 20


def test_rows_without_a_name_are_skipped(store):
    assert store.upsert_docs("s1", "Sales Invoice", [{"grand_total": 10}]) == 0


def test_sites_round_trip_without_exposing_the_secret(store):
    store.upsert_site("s2", "https://x.example.com", "X", api_key="key", api_secret="secret")
    site = store.get_site("s2")
    assert site["has_credentials"] is True
    assert "secret" not in {k for k in site}
    assert "secret" not in str(site)


def test_delete_site_removes_its_documents(store):
    seed_demo(store, "demo")
    assert store.count("demo", "Sales Invoice") > 0
    store.delete_site("demo")
    assert store.get_site("demo") is None
    assert store.count("demo", "Sales Invoice") == 0


def test_search_and_status_filters(store):
    seed_demo(store, "demo")
    assert store.docs("demo", "Sales Invoice", search="Acme")
    assert all("Acme" in doc["customer"] for doc in store.docs("demo", "Sales Invoice", search="Acme"))
    overdue = store.docs("demo", "Sales Invoice", status="Overdue")
    assert overdue and all(doc["status"] == "Overdue" for doc in overdue)


def test_sync_writes_documents_and_a_watermark(store, fake_site):
    report = sync_site(client(fake_site), store, "s1", doctypes=["Customer", "Sales Invoice"])
    assert report["ok"] is True
    assert store.count("s1", "Customer") == 2
    assert store.count("s1", "Sales Invoice") == 2
    assert store.watermark("s1", "Sales Invoice") == "2026-09-10 10:00:00"


def test_second_sync_only_asks_for_what_changed(store, fake_site):
    sync_site(client(fake_site), store, "s1", doctypes=["Customer"])
    fake_site.calls.clear()
    sync_site(client(fake_site), store, "s1", doctypes=["Customer"])
    filters = fake_site.calls[-1]["query"].get("filters", ["[]"])[0]
    assert "modified" in filters and ">" in filters


def test_full_sync_ignores_the_watermark(store, fake_site):
    sync_site(client(fake_site), store, "s1", doctypes=["Customer"])
    fake_site.calls.clear()
    sync_site(client(fake_site), store, "s1", doctypes=["Customer"], full=True)
    assert "filters" not in fake_site.calls[-1]["query"]


def test_a_permission_error_on_one_doctype_does_not_stop_the_rest(store, fake_site):
    fake_site.fail.add("Salary Slip")
    report = sync_site(client(fake_site), store, "s1", doctypes=["Customer", "Salary Slip"])
    assert report["ok"] is False
    assert store.count("s1", "Customer") == 2
    failed = [entry for entry in report["doctypes"] if not entry["ok"]]
    assert failed and "permission" in failed[0]["error"].lower()
    state = {row["doctype"]: row for row in store.sync_state("s1")}
    assert state["Salary Slip"]["ok"] is False


def test_watermark_does_not_advance_on_failure(store, fake_site):
    sync_site(client(fake_site), store, "s1", doctypes=["Customer"])
    before = store.watermark("s1", "Customer")
    fake_site.fail.add("Customer")
    sync_site(client(fake_site), store, "s1", doctypes=["Customer"])
    assert store.watermark("s1", "Customer") == before


def test_invoices_are_hydrated_with_their_child_taxes(store, fake_site):
    """The list endpoint hides `taxes`; the GST report needs them."""
    report = sync_site(client(fake_site), store, "s1", doctypes=["Sales Invoice"])
    assert report["doctypes"][0]["hydrated"] == 2
    doc = store.one("s1", "Sales Invoice", "SINV-1")
    assert len(doc["taxes"]) == 2


def test_hydration_is_bounded(store, fake_site):
    report = sync_site(client(fake_site), store, "s1", doctypes=["Sales Invoice"], hydrate_limit=1)
    assert report["doctypes"][0]["hydrated"] == 1
    assert store.names_missing_taxes("s1", "Sales Invoice")


def test_unknown_doctype_is_rejected_before_any_request(store, fake_site):
    with pytest.raises(ValueError):
        sync_site(client(fake_site), store, "s1", doctypes=["GL Entry"])
    assert fake_site.calls == []


def test_progress_callback_sees_each_doctype(store, fake_site):
    seen: list[str] = []
    sync_site(client(fake_site), store, "s1", doctypes=["Customer", "Salary Slip"],
              on_progress=lambda entry: seen.append(entry["doctype"]))
    assert seen == ["Customer", "Salary Slip"]


def test_paging_is_honoured_across_many_rows(store, fake_site):
    fake_site.docs["Customer"] = [
        {"name": f"C-{index:03d}", "modified": f"2026-09-{index % 28 + 1:02d} 10:00:00"} for index in range(450)
    ]
    report = sync_site(client(fake_site), store, "s1", doctypes=["Customer"], page_size=100)
    assert store.count("s1", "Customer") == 450
    assert report["doctypes"][0]["rows"] == 450
