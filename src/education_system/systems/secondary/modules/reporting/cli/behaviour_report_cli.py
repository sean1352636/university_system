"""Behaviour Report in the terminal.

1 Set filters (dates, year, form) and run, 2 Summary, 3 Breakdown (by type,
year, form, subject, staff, weekday, hour, severity, location), 4 Trend by
week, 5 Pupils of concern, 6 All pupils, 7 Detentions, 8 Suspensions &
exclusions, 9 One pupil, 10 Export CSV. Rules:
:mod:`modules.reporting.domain.behaviour_report`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.reporting.cli import report_prompts as RP
from education_system.systems.secondary.modules.reporting.domain import behaviour_report as BR
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt

_state: dict[str, Any] = {}


def _report(principal: Principal, *, fresh: bool = False) -> BR.Report:
    if fresh or "report" not in _state:
        f = _state.setdefault("filters", {})
        _state["report"] = BR.build(principal, f.get("from") or None, f.get("to") or None,
                                    year_group=f.get("year") or None,
                                    form=f.get("form") or None)
    return _state["report"]


def _run(principal: Principal) -> None:
    RP.filters(_state.setdefault("filters", {}))
    r = _report(principal, fresh=True)
    t = r.totals()
    print(f"\n  {r.scope}, {r.start} to {r.end}: {t['positive']} positive, {t['negative']} "
          f"negative, {t['detentions_set']} detentions, {t['suspensions']} suspensions")


def _section(section: str):
    def show(principal: Principal) -> None:
        r = _report(principal)
        by = "type"
        if section == "breakdown":
            by = prompts.pick("Break down by", list(BR.BREAKDOWNS),
                              _state.get("by", "type")) or "type"
            _state["by"] = by
        print(f"\n  {BR.SECTIONS[section]} - {r.scope}, {r.start} to {r.end}")
        RP.table(*BR.table(r, section, by))
    return show


def _pupil(principal: Principal) -> None:
    pid = RP.pupil_id()
    if pid is not None:
        print()
        print(BR.pupil_text(_report(principal), pid))


def _export(principal: Principal) -> None:
    r = _report(principal)
    section = prompts.pick("Section", list(BR.SECTIONS), "summary") or "summary"
    if section not in BR.SECTIONS:
        print("  Unknown section.")
        return
    by = _state.get("by", "type")
    if section == "breakdown":
        by = prompts.pick("Break down by", list(BR.BREAKDOWNS), by) or "type"
    path = RP.csv_path(f"behaviour_{section}.csv")
    if path:
        print(f"  Exported {BR.export_csv(path, r, section, actor=principal, by=by)} row(s).")


_OPTIONS = {"1": _run, "2": _section("summary"), "3": _section("breakdown"),
            "4": _section("weeks"), "5": _section("concern"), "6": _section("pupils"),
            "7": _section("detentions"), "8": _section("exclusions"), "9": _pupil,
            "10": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("behaviour_report.view")
        print("\n  ── Behaviour Report ──")
        print("    1) Set filters and run\n    2) Summary\n    3) Breakdown\n    4) Trend by "
              "week\n    5) Pupils of concern\n    6) All pupils\n    7) Detentions"
              "\n    8) Suspensions & exclusions\n    9) One pupil\n   10) Export CSV")
        print("    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except RP.ERRORS as e:
            prompts.problem(e)
        _pause()
