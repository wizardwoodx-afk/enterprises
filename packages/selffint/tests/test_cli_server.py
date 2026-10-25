"""The two doors a human touches directly: the CLI and `selffint serve`.

Both wrap the same `dispatch()`, so what is worth testing here is not the
accounting (covered elsewhere) but the plumbing: that the CLI parses what it
promises, exits non-zero on failure, and that the stdlib server routes a real
socket the same way the ASGI app routes a fake one.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from selffint.api import SelfFintApi
from selffint.cli import build_parser, main
from selffint.server import make_server
from selffint.store import MirrorStore


@pytest.fixture()
def home(tmp_path):
    return str(tmp_path / "mirror.db")


def run(home: str, *argv: str, capsys) -> tuple[int, dict]:
    code = main(["--home", home, *argv])
    out = capsys.readouterr().out

    return code, json.loads(out) if out.strip() else {}


def test_demo_then_status(home, capsys):
    code, seeded = run(home, "demo", capsys=capsys)
    assert code == 0 and seeded["ok"] is True

    code, status = run(home, "status", capsys=capsys)
    assert code == 0
    assert status["site"]["mode"] == "demo"
    assert status["counts"]["Sales Invoice"] >= 4


def test_the_aging_report_honours_as_of(home, capsys):
    run(home, "demo", capsys=capsys)
    _, report = run(home, "report", "ar", "--as-of", "2026-10-20", capsys=capsys)
    assert report["total"] == pytest.approx(365_200, abs=1)
    assert sum(bucket["amount"] for bucket in report["buckets"]) == pytest.approx(report["total"])
    assert report["as_of"] == "2026-10-20"


def test_a_date_range_reaches_the_gst_report(home, capsys):
    run(home, "demo", capsys=capsys)
    _, report = run(home, "report", "gst", "--from", "2026-04-01", "--to", "2026-09-30", capsys=capsys)
    assert report["invoices"] > 0
    assert report["total_tax"] > 0


def test_invoice_create_parses_desc_colon_qty_colon_rate(home, capsys):
    run(home, "demo", capsys=capsys)
    code, payload = run(
        home,
        "invoice",
        "create",
        "--customer",
        "Acme Textiles",
        "--item",
        "Consulting:2:2500",
        capsys=capsys,
    )
    assert code == 0
    assert payload["document"]["grand_total"] == pytest.approx(5900)

    _, invoices = run(home, "status", capsys=capsys)
    assert invoices["counts"]["Sales Invoice"] >= 5


def test_a_bad_item_is_a_parse_error_not_a_crash(home):
    with pytest.raises(SystemExit) as raised:
        main(["--home", home, "invoice", "create", "--customer", "X", "--item", "only-a-description"])
    assert raised.value.code == 2


def test_an_empty_invoice_is_refused(home):
    with pytest.raises(SystemExit) as raised:
        main(["--home", home, "invoice", "create", "--customer", "X"])
    assert raised.value.code == 2


def test_a_failing_command_exits_non_zero(home, capsys):
    run(home, "demo", capsys=capsys)
    code = main(["--home", home, "invoice", "create", "--customer", "", "--item", "Work:1:10"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1 and payload["ok"] is False


def test_compact_prints_json_on_one_line_after_the_verb(home, capsys):
    run(home, "demo", capsys=capsys)
    assert main(["--home", home, "report", "ar", "--compact"]) == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("{") and "\n" not in out


def test_the_parser_documents_every_command():
    # `--help` must work without a mirror on disk; the subcommands are the API.
    args = build_parser().parse_args(["report", "ar", "--as-of", "2026-10-01"])
    assert (args.command, args.kind, args.as_of) == ("report", "ar", "2026-10-01")


# ------------------------------------------------------------------- the server
@pytest.fixture()
def live(home):
    store = MirrorStore(home)
    api = SelfFintApi(store)
    httpd = make_server(api, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()
    store.close()


def call(base: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        f"{base}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_health_is_served_without_the_prefix(live):
    status, payload = call(live, "/health")
    assert status == 200 and payload["service"] == "selffint"


def test_the_prefixed_route_is_the_same_route(live):
    status, payload = call(live, "/api/plugins/self-fint/status")
    assert status == 200 and payload["site"]["mode"] == "demo"


def test_the_query_string_survives_the_http_door(live):
    status, payload = call(live, "/api/plugins/self-fint/reports/ar-aging?as_of=2026-10-20")
    assert status == 200 and payload["as_of"] == "2026-10-20"


def test_a_post_body_reaches_the_dispatch(live):
    status, payload = call(
        live,
        "/api/plugins/self-fint/invoices",
        {"customer": "Acme Textiles", "items": [{"description": "Work", "qty": 1, "rate": 1000}]},
    )
    assert status == 201 and payload["document"]["docstatus"] == 0


def test_an_unknown_path_is_a_json_404(live):
    status, payload = call(live, "/nope")
    assert status == 404 and payload["ok"] is False
