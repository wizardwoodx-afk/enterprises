"""The Frappe client: paging, error taxonomy, and the child-table rule."""

from __future__ import annotations

import pytest

from selffint.client import (
    DEFAULT_PAGE,
    FrappeAuthError,
    FrappeClient,
    FrappeError,
    FrappeNotFound,
    FrappePermissionError,
    FrappeRateLimited,
    FrappeServerError,
    FrappeValidationError,
    Response,
    Site,
)


def client(fake_site):  # noqa: ANN001, ANN201
    return FrappeClient(Site(url="https://erp.example.com", api_key="k", api_secret="s"), transport=fake_site)


def test_site_requires_http_and_credentials():
    with pytest.raises(ValueError):
        Site(url="erp.example.com", api_key="k", api_secret="s")
    with pytest.raises(ValueError):
        Site(url="https://erp.example.com", api_key="", api_secret="s")


def test_site_repr_never_leaks_the_secret():
    site = Site(url="https://erp.example.com", api_key="key-123", api_secret="secret-456")
    assert "secret-456" not in repr(site)
    assert "key-123" not in repr(site)


def test_ping_identifies_the_user(fake_site):
    assert client(fake_site).ping() == "integration@demo.example"


def test_every_request_carries_the_token(fake_site):
    client(fake_site).list_docs("Customer")
    assert fake_site.calls[0]["auth"] == "token k:s"


def test_list_always_sends_an_explicit_page_length(fake_site):
    """The server default is 20; forgetting this is the classic silent truncation."""
    client(fake_site).list_docs("Sales Invoice")
    query = fake_site.calls[-1]["query"]
    assert query["limit_page_length"] == [str(DEFAULT_PAGE)]
    assert query["order_by"] == ["modified asc"]


def test_list_encodes_fields_and_filters(fake_site):
    client(fake_site).list_docs("Sales Invoice", fields=["name"], filters=[["status", "=", "Unpaid"]])
    query = fake_site.calls[-1]["query"]
    assert query["fields"] == ['["name"]']
    assert query["filters"] == ['[["status", "=", "Unpaid"]]']


def test_empty_filters_are_not_sent(fake_site):
    """A full sync sends no filter at all rather than an empty array."""
    client(fake_site).list_docs("Customer", filters=[])
    assert "filters" not in fake_site.calls[-1]["query"]


def test_page_length_is_capped(fake_site):
    client(fake_site).list_docs("Customer", limit_page_length=99_999)
    assert fake_site.calls[-1]["query"]["limit_page_length"] == ["1000"]


def test_fetch_all_pages_until_a_short_page(fake_site):
    fake_site.docs["Customer"] = [
        {"name": f"C-{index:03d}", "modified": f"2026-09-01 10:{index:02d}:00"} for index in range(45)
    ]
    pages = list(client(fake_site).fetch_all("Customer", page_size=20))
    assert [len(page) for page in pages] == [20, 20, 5]


def test_fetch_all_stops_at_the_page_cap(fake_site):
    fake_site.docs["Customer"] = [
        {"name": f"C-{index:04d}", "modified": f"2026-09-01 10:00:{index % 60:02d}"} for index in range(500)
    ]
    pages = list(client(fake_site).fetch_all("Customer", page_size=10, max_pages=3))
    assert len(pages) == 3


def test_get_doc_includes_child_tables_that_the_list_hides(fake_site):
    api = client(fake_site)
    listed = api.list_docs("Sales Invoice")
    assert all("taxes" not in row for row in listed)
    one = api.get_doc("Sales Invoice", "SINV-1")
    assert len(one["taxes"]) == 2


def test_create_doc_posts_and_returns_the_created_document(fake_site):
    created = client(fake_site).create_doc("Sales Invoice", {"customer": "Acme Textiles", "docstatus": 0})
    assert created["customer"] == "Acme Textiles"
    assert fake_site.calls[-1]["method"] == "POST"


def test_missing_document_is_a_not_found(fake_site):
    with pytest.raises(FrappeNotFound):
        client(fake_site).get_doc("Sales Invoice", "nope")


def test_permission_error_is_its_own_type(fake_site):
    fake_site.fail.add("Salary Slip")
    with pytest.raises(FrappePermissionError):
        client(fake_site).list_docs("Salary Slip")


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, FrappeAuthError),
        (403, FrappePermissionError),
        (404, FrappeNotFound),
        (417, FrappeValidationError),
        (429, FrappeRateLimited),
        (500, FrappeServerError),
        (503, FrappeServerError),
    ],
)
def test_status_codes_map_to_the_taxonomy(status, expected):
    transport = _Fixed(status, {"exc_type": "X", "message": "boom"})
    api = FrappeClient(Site(url="https://erp.example.com", api_key="k", api_secret="s"), transport=transport)
    with pytest.raises(expected) as caught:
        api.list_docs("Customer")
    assert caught.value.status == status
    assert "boom" in caught.value.message


def test_server_messages_are_flattened_for_the_user():
    transport = _Fixed(
        417,
        {
            "exc_type": "ValidationError",
            "_server_messages": '["{\\"message\\": \\"Customer is mandatory\\"}"]',
        },
    )
    api = FrappeClient(Site(url="https://erp.example.com", api_key="k", api_secret="s"), transport=transport)
    with pytest.raises(FrappeValidationError) as caught:
        api.create_doc("Sales Invoice", {})
    assert "Customer is mandatory" in caught.value.message


def test_non_json_error_bodies_do_not_crash_the_client():
    transport = _Fixed(502, None, raw=b"<html>bad gateway</html>")
    api = FrappeClient(Site(url="https://erp.example.com", api_key="k", api_secret="s"), transport=transport)
    with pytest.raises(FrappeServerError) as caught:
        api.list_docs("Customer")
    assert "bad gateway" in caught.value.message


def test_docstring_contract_of_response_helper():
    status, headers, body = Response(200, {"data": []}).as_tuple()
    assert status == 200 and headers["content-type"] == "application/json" and body.startswith(b"{")


def test_unreachable_site_surfaces_as_a_frappe_error(monkeypatch):
    from selffint import client as module

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise FrappeError("cannot reach the site: refused")

    monkeypatch.setattr(module.urllib.request, "urlopen", boom)
    api = FrappeClient(Site(url="https://erp.example.com", api_key="k", api_secret="s"))
    with pytest.raises(FrappeError) as caught:
        api.list_docs("Customer")
    assert "cannot reach" in caught.value.message


class _Fixed:
    def __init__(self, status: int, payload, raw: bytes | None = None) -> None:
        self.status = status
        self.payload = payload
        self.raw = raw

    def request(self, method, url, headers, body, timeout):  # noqa: ANN001, ANN201, D102
        import json

        raw = self.raw if self.raw is not None else json.dumps(self.payload or {}).encode()
        return self.status, {"content-type": "application/json"}, raw
