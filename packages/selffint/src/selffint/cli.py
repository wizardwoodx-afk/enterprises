"""`selffint` on the command line — the same service, no desktop.

    selffint status
    selffint demo
    selffint connect --url https://erp.example.com --key K --secret S
    selffint sync [--full]
    selffint report ar [--as-of 2026-10-20]
    selffint report gst --from 2026-04-01 --to 2026-09-30
    selffint report payroll [--month 2026-09]
    selffint report 2b
    selffint invoice create --customer "Acme Textiles" --item "Consulting:1:50000"
    selffint serve --port 8790

Useful for cron: a nightly `selffint sync` keeps the mirror warm, so the desktop
opens to numbers instead of a spinner.

Every command prints the JSON payload the HTTP door would return and exits
non-zero on a 4xx/5xx, so shell scripts can branch on it without parsing prose.
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urlencode

from .api import SelfFintApi
from .store import MirrorStore


def _print(payload: dict) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _query(**params: str) -> str:
    pairs = {key: value for key, value in params.items() if value}
    return f"?{urlencode(pairs)}" if pairs else ""


def _parse_item(raw: str) -> dict:
    """`description:qty:rate` — the shape a shell can type without JSON quoting."""
    parts = raw.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("an item is 'description:qty:rate'")
    description, qty, rate = parts
    try:
        return {"description": description, "qty": float(qty), "rate": float(rate)}
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"qty and rate must be numbers: {error}") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="selffint", description="SelfFint finance service")
    parser.add_argument("--home", help="mirror database path (default: $BEYOND_HOME/selffint)")
    # `--compact` rides on every subcommand rather than the root: a shell user
    # types `selffint report ar --compact`, not the flag before the verb.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--compact", action="store_true", help="print JSON on one line")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", parents=[common], help="what the service knows")
    sub.add_parser("demo", parents=[common], help="seed the demo company")

    connect = sub.add_parser("connect", parents=[common], help="add a site")
    connect.add_argument("--url", required=True)
    connect.add_argument("--key", required=True)
    connect.add_argument("--secret", required=True)
    connect.add_argument("--label", default="")

    sync = sub.add_parser("sync", parents=[common], help="pull documents into the mirror")
    sync.add_argument("--full", action="store_true", help="ignore the watermark and re-read everything")

    report = sub.add_parser("report", parents=[common], help="run a report")
    report.add_argument("kind", choices=["ar", "gst", "payroll", "2b"])
    report.add_argument("--as-of", dest="as_of", default="", help="age receivables as at this date")
    report.add_argument("--from", dest="date_from", default="")
    report.add_argument("--to", dest="date_to", default="")
    report.add_argument("--month", default="")

    invoice = sub.add_parser("invoice", parents=[common], help="draft invoices")
    invoice_sub = invoice.add_subparsers(dest="invoice_command", required=True)
    create = invoice_sub.add_parser("create", help="create a DRAFT sales invoice on the site")
    create.add_argument("--customer", required=True)
    create.add_argument("--item", action="append", type=_parse_item, default=[], metavar="DESC:QTY:RATE")
    create.add_argument("--posting-date", default="")
    create.add_argument("--due-date", default="")

    serve = sub.add_parser("serve", parents=[common], help="run the HTTP adapter")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8790)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        from .server import serve as run_server

        # `serve` blocks, so it builds its own API with the store path resolved
        # the same way every other command resolves it.
        api = SelfFintApi(MirrorStore(args.home) if args.home else None)
        run_server(api, host=args.host, port=args.port)
        return 0

    api = SelfFintApi(MirrorStore(args.home) if args.home else None)

    if args.command == "status":
        status, payload = api.dispatch("GET", "/status")
    elif args.command == "demo":
        status, payload = api.dispatch("POST", "/demo/seed", {})
    elif args.command == "connect":
        status, payload = api.dispatch(
            "POST",
            "/connect",
            {"url": args.url, "api_key": args.key, "api_secret": args.secret, "label": args.label},
        )
    elif args.command == "sync":
        status, payload = api.dispatch("POST", "/sync", {"full": args.full})
    elif args.command == "invoice":
        if not args.item:
            parser.error("invoice create needs at least one --item DESC:QTY:RATE")
        body = {"customer": args.customer, "items": args.item}
        if args.posting_date:
            body["posting_date"] = args.posting_date
        if args.due_date:
            body["due_date"] = args.due_date
        status, payload = api.dispatch("POST", "/invoices", body)
    elif args.kind == "ar":
        status, payload = api.dispatch("GET", f"/reports/ar-aging{_query(as_of=args.as_of)}")
    elif args.kind == "gst":
        status, payload = api.dispatch(
            "GET", f"/reports/gst{_query(**{'from': args.date_from, 'to': args.date_to})}"
        )
    elif args.kind == "payroll":
        status, payload = api.dispatch("GET", f"/reports/payroll{_query(month=args.month)}")
    else:
        status, payload = api.dispatch("POST", "/reconcile/2b", {"use_demo": True, "period": args.month})

    if args.compact:
        print(json.dumps(payload, default=str))
    else:
        _print(payload)
    return 0 if status < 400 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
