"""Every declared boundary resolves to a real adapter at both ends.

A handover spec whose end has no adapter is a route that exists only on
paper. It fails at the boundary the day a learner first uses it, not the
day it was wired. For each spec in ``handover.HANDOVER_SPECS``, this
checks two things:

* the source is declared in the launcher's ``_PHASE_ADAPTERS`` table, and
  its adapter implements ``export_handover`` and ``close_enrolment``;
* the destination is declared too, and implements ``create_applicant``
  and ``create_enrolment``.

The table and the adapter modules are read as *source*, not imported.
Importing the university package writes an audit row at import time,
and a wiring check has no business touching any database.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import education_system
from education_system.platform.cross_system import handover, identity_service, progression
from education_system.platform.cross_system.adapters import registry

_SRC = Path(education_system.__file__).parent

SOURCE_SIDE = {"export_handover", "close_enrolment"}
DESTINATION_SIDE = {"create_applicant", "create_enrolment"}
CONTRACT = SOURCE_SIDE | DESTINATION_SIDE


def _phase_adapter_table() -> dict[str, str]:
    tree = ast.parse((_SRC / "launcher" / "systems.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_PHASE_ADAPTERS"
                for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("launcher/systems.py has no _PHASE_ADAPTERS table")


def _module_file(dotted: str) -> Path:
    head, *rest = dotted.split(".")
    assert head == "education_system", dotted
    return _SRC.joinpath(*rest).with_suffix(".py")


def _adapter_methods(system: str, dotted: str) -> set[str] | None:
    """The contract methods defined by the class in ``dotted`` whose
    ``system`` key is ``system``; ``None`` if no such class exists."""
    tree = ast.parse(_module_file(dotted).read_text(encoding="utf-8"))
    constants = {
        target.id: node.value.value
        for node in tree.body if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        for target in node.targets if isinstance(target, ast.Name)
    }

    def resolve(value: ast.expr) -> str | None:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        if isinstance(value, ast.Name):
            return constants.get(value.id)
        return None

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        keys = {resolve(item.value) for item in node.body
                if isinstance(item, ast.Assign)
                for target in item.targets
                if isinstance(target, ast.Name) and target.id == "system"}
        if system in keys:
            return {item.name for item in node.body
                    if isinstance(item, ast.FunctionDef) and item.name in CONTRACT}
    return None


_TABLE = _phase_adapter_table()


def test_every_journey_system_declares_an_adapter():
    assert set(identity_service.SYSTEM_SLOTS) <= set(_TABLE)


@pytest.mark.parametrize("system", sorted(_TABLE))
def test_each_declared_module_holds_that_systems_adapter(system):
    assert _module_file(_TABLE[system]).is_file(), _TABLE[system]
    assert _adapter_methods(system, _TABLE[system]) is not None, (
        f"{_TABLE[system]} has no adapter class with system = {system!r}")


@pytest.mark.parametrize("source,destination", sorted(handover.HANDOVER_SPECS))
def test_declared_boundary_resolves_at_both_ends(source, destination):
    assert source in _TABLE, f"{source} -> {destination}: no source adapter"
    assert destination in _TABLE, f"{source} -> {destination}: no destination adapter"
    exports = _adapter_methods(source, _TABLE[source]) or set()
    receives = _adapter_methods(destination, _TABLE[destination]) or set()
    assert SOURCE_SIDE <= exports, (
        f"{source} cannot send: missing {sorted(SOURCE_SIDE - exports)}")
    assert DESTINATION_SIDE <= receives, (
        f"{destination} cannot receive: missing {sorted(DESTINATION_SIDE - receives)}")


@pytest.mark.parametrize("destination", ["employment", "training", "gap_year"])
def test_non_phase_destinations_need_no_adapter(destination):
    # A move to employment is recorded and completed by the workflow
    # itself; there is no system on the other side to call.
    assert progression.is_non_phase_destination(destination)
    assert destination not in _TABLE


def test_registry_loads_a_declared_adapter_on_first_use():
    registry.clear_for_test()
    try:
        registry.declare("primary", _TABLE["primary"])
        assert registry.get("primary") is None
        adapter = registry.require("primary")
        assert adapter.system == "primary"
        assert registry.get("primary") is adapter
    finally:
        registry.clear_for_test()
