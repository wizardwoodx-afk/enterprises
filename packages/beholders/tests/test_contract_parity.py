"""Parity between the Python service and the TypeScript contract.

`apps/shared/src/crew-contract.ts` is the shape the desktop renders;
`beholders/service/models.py` is the shape the engine runs. They are two
hand-written files describing one wire format, so this test makes the drift
loud: a field added on one side and not the other fails here rather than
surfacing as `undefined` in a React render.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from beholders.service.api import BLUEPRINTS
from beholders.service.models import AgentSpec, CrewDefinition, RunRecord, TaskSpec
from beholders.service.rpc import CrewRpc

CONTRACT = Path(__file__).resolve().parents[3] / "apps/shared/src/crew-contract.ts"


@pytest.fixture(scope="module")
def contract() -> str:
    if not CONTRACT.exists():
        pytest.skip(f"contract not found at {CONTRACT}")
    return CONTRACT.read_text(encoding="utf-8")


def ts_interface(source: str, name: str) -> str:
    """Return the body of `interface <name> { … }` from the contract."""
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.S)
    assert match, f"interface {name} missing from the contract"
    return match.group(1)


def ts_fields(body: str) -> set[str]:
    return set(re.findall(r"^\s{2}([a-z_]+)\??:", body, re.M))


@pytest.mark.parametrize(
    ("interface", "model", "extra"),
    [
        ("CrewAgentSpec", AgentSpec, set()),
        ("CrewTaskSpec", TaskSpec, set()),
        ("CrewDefinition", CrewDefinition, set()),
        ("CrewRun", RunRecord, {"event_count", "events"}),
    ],
)
def test_python_model_fields_appear_in_the_typescript_contract(contract, interface, model, extra):
    fields = {f.name for f in model.__dataclass_fields__.values()}
    declared = ts_fields(ts_interface(contract, interface))

    missing = fields - declared - extra
    assert not missing, f"{model.__name__} fields absent from {interface}: {sorted(missing)}"


def test_run_summary_is_the_run_without_events(contract):
    assert "CrewRunSummary = Omit<CrewRun, 'events'>" in contract


def test_rpc_methods_match_both_sides(contract):
    block = re.search(r"CREW_RPC_METHODS = \[(.*?)\] as const", contract, re.S)
    assert block, "CREW_RPC_METHODS missing from the contract"
    declared = set(re.findall(r"'(crew\.[a-z.]+)'", block.group(1)))
    actual = set(CrewRpc().methods())

    assert declared == actual, f"only in TS: {sorted(declared - actual)}; only in Py: {sorted(actual - declared)}"


def test_blueprints_only_use_fields_the_contract_declares(contract):
    agent_fields = ts_fields(ts_interface(contract, "CrewAgentSpec"))
    task_fields = ts_fields(ts_interface(contract, "CrewTaskSpec"))

    for blueprint in BLUEPRINTS:
        for agent in blueprint["agents"]:
            assert set(agent) <= agent_fields, (blueprint["id"], set(agent) - agent_fields)
        for task in blueprint["tasks"]:
            assert set(task) <= task_fields, (blueprint["id"], set(task) - task_fields)


def test_process_values_match(contract):
    assert "export type CrewProcess = 'hierarchical' | 'sequential'" in contract

    from beholders.service.models import Process

    assert {p.value for p in Process} == {"hierarchical", "sequential"}


def test_terminal_statuses_match(contract):
    block = re.search(r"TERMINAL_RUN_STATUSES[^=]*=\s*\[(.*?)\]", contract, re.S)
    assert block
    declared = set(re.findall(r"'([a-z]+)'", block.group(1)))

    from beholders.service.models import RunStatus

    assert {s.value for s in RunStatus if s.terminal} == declared


def test_poll_constants_match(contract):

    # The service does not poll; this only guards that the contract documents a
    # cadence the UI actually uses. Kept here so a change is deliberate.
    assert "CREW_POLL_ACTIVE_MS = 2_000" in contract
    assert "CREW_POLL_IDLE_MS = 15_000" in contract
