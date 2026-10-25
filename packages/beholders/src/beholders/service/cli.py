"""``beholders`` command line: serve the gateway, inspect crews, run one."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .api import BeholdersApi
from .models import CrewDefinition
from .runs import RunRegistry
from .store import CrewStore


def _print(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import API_PREFIX, serve

    print(f"Beholders service listening on http://{args.host}:{args.port}{API_PREFIX}", flush=True)
    serve(args.host, args.port)
    return 0


def cmd_crews(args: argparse.Namespace) -> int:
    api, _ = _api()
    status, payload = api.dispatch("GET", "/crews")
    _print(payload)
    return 0 if status < 400 else 1


def cmd_create(args: argparse.Namespace) -> int:
    api, _ = _api()
    data = json.loads(args.file) if args.file.startswith("{") else json.load(open(args.file))
    status, payload = api.dispatch("POST", "/crews", data)
    _print(payload)
    return 0 if status < 400 else 1


def cmd_run(args: argparse.Namespace) -> int:
    api, runs = _api()
    worker = RunRegistry()
    crew = api.store.get(args.crew)
    record = worker.start(crew, json.loads(args.inputs) if args.inputs else {})
    print(f"run {record.id} ({record.crew_name}) — waiting…", file=sys.stderr)
    worker.wait(record.id, timeout=args.timeout)
    _print(worker.get(record.id).to_dict())
    return 0 if worker.get(record.id).status.value == "succeeded" else 1


def _api() -> tuple[BeholdersApi, RunRegistry]:
    runs = RunRegistry()
    return BeholdersApi(store=CrewStore(), runs=runs), runs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="beholders", description="The Beholders crew runtime.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="expose the crew API over HTTP")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    serve.set_defaults(func=cmd_serve)

    crews = sub.add_parser("crews", help="list crew definitions")
    crews.set_defaults(func=cmd_crews)

    create = sub.add_parser("create", help="create a crew from a JSON file or inline object")
    create.add_argument("file", help="path to JSON, or an inline JSON object")
    create.set_defaults(func=cmd_create)

    run = sub.add_parser("run", help="run a crew and print its record")
    run.add_argument("crew")
    run.add_argument("--inputs", default="", help="JSON object passed to the crew")
    run.add_argument("--timeout", type=float, default=600)
    run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
