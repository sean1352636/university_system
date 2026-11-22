"""Attendance Report in the terminal.

1 Set filters (dates, year, form) and run, 2 DfE-style summary, 3 Pupils,
4 Persistent absence, 5 Severe absence, 6 By code, 7 By weekday and session,
8 Trend by week, 9 Groups, 10 Year groups, 11 Forms, 12 One pupil (drill
down), 13 Export a section to CSV. Rules:
:mod:`modules.reporting.domain.attendance_report`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.reporting.cli import report_prompts as RP
from education_system.systems.secondary.modules.reporting.domain import attendance_report as AR
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt

_state: dict[str, Any] = {}


def _report(principal: Principal, *, fresh: bool = False) -> AR.Report:
    if fresh or "report" not in _state:
        f = _state.setdefault("filters", {})
        _state["report"] = AR.build(principal, f.get("from") or None, f.get("to") or None,
                                    year_group=f.get("year") or None,
                                    form=f.get("form") or None)
    return _state["report"]


def _run(principal: Principal) -> None:
    RP.filters(_state.setdefault("filters", {}))
    r = _report(principal, fresh=True)
    print(f"\n  {r.scope}, {r.start} to {r.end}: {len(r.pupils)} pupil(s), attendance "
          f"{AR.RC.show(r.overall.attendance_pct)}%")


def _section(section: str):
    def show(principal: Principal) -> None:
        r = _report(principal)
        print(f"\n  {AR.SECTIONS[section]} - {r.scope}, {r.start} to {r.end}")
        RP.table(*AR.table(r, section))
    return show


def _pupil(principal: Principal) -> None:
    pid = RP.pupil_id()
    if pid is None:
        return
    f = _state.get("filters", {})
    print()
    print(AR.pupil_text(AR.pupil_detail(principal, pid, f.get("from") or None,
                                        f.get("to") or None)))


def _export(principal: Principal) -> None:
    r = _report(principal)
    section = prompts.pick("Section", list(AR.SECTIONS), "pupils") or "pupils"
    if section not in AR.SECTIONS:
        print("  Unknown section.")
        return
    path = RP.csv_path(f"attendance_{section}.csv")
    if path:
        print(f"  Exported {AR.export_csv(path, r, section, actor=principal)} row(s).")


_OPTIONS = {"1": _run, "2": _section("summary"), "3": _section("pupils"),
            "4": _section("persistent"), "5": _section("severe"), "6": _section("codes"),
            "7": _section("weekdays"), "8": _section("weeks"), "9": _section("groups"),
            "10": _section("years"), "11": _section("forms"), "12": _pupil, "13": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("attendance_report.view")
        print("\n  ── Attendance Report ──")
        print("    1) Set filters and run\n    2) DfE-style summary\n    3) Pupils"
              "\n    4) Persistent absence\n    5) Severe absence\n    6) By code"
              "\n    7) By weekday and session\n    8) Trend by week\n    9) Groups"
              "\n   10) Year groups\n   11) Forms\n   12) One pupil\n   13) Export CSV")
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
