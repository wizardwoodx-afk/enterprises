"""`selffint` on the command line — the same service, no desktop.

    selffint status
    selffint demo
    selffint connect --url https://erp.example.com --key K --secret S
    selffint sync [--full]
    selffint report ar|gst|payroll [--from D --to D --month M]

Useful for cron: a nightly `selffint sync` keeps the mirror warm so the desktop
opens to numbers instead of a spinner.
"""

from __future__ import annotations

import argparse
import json
import sys

from .api import SelfFintApi


def _print(payload: dict) -> None:
    print(json.dumps(payload, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="selffint", description="SelfFint finance service")
    parser.add_argument("--home", help="mirror database path")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="what the service knows")
    sub.add_parser("demo", help="seed the demo company")

    connect = sub.add_parser("connect", help="add a site")
    connect.add_argument("--url", required=True)
    connect.add_argument("--key", required=True)
    connect.add_argument("--secret", required=True)
    connect.add_argument("--label", default="")

    sync = sub.add_parser("sync", help="pull documents into the mirror")
    sync.add_argument("--full", action="store_true")

    report = sub.add_parser("report", help="run a report")
    report.add_argument("kind", choices=["ar", "gst", "payroll", "2b"])
    report.add_argument("--from", dest="date_from", default="")
    report.add_argument("--to", dest="date_to", default="")
    report.add_argument("--month", default="")

    args = parser.parse_args(argv)
    api = SelfFintApi()

    if args.command == "status":
        status, payload = api.dispatch("GET", "/status")
    elif args.command == "demo":
        status, payload = api.dispatch("POST", "/demo/seed", {})
    elif args.command == "connect":
        status, payload = api.dispatch(
            "POST", "/connect", {"url": args.url, "api_key": args.key, "api_secret": args.secret, "label": args.label}
        )
    elif args.command == "sync":
        status, payload = api.dispatch("POST", "/sync", {"full": args.full})
    elif args.kind == "ar":
        status, payload = api.dispatch("GET", "/reports/ar-aging", {})
    elif args.kind == "gst":
        status, payload = api.dispatch("GET", f"/reports/gst?from={args.date_from}&to={args.date_to}", {})
    elif args.kind == "payroll":
        status, payload = api.dispatch("GET", f"/reports/payroll?month={args.month}", {})
    else:
        status, payload = api.dispatch("POST", "/reconcile/2b", {"use_demo": True})

    _print(payload)
    return 0 if status < 400 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
