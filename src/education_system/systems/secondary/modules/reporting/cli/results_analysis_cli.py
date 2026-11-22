"""Results Analysis in the terminal.

1 Choose what to analyse (assessment point, mock series or exam series) and
filters, 2 Headline, 3 Subjects, 4 Grade distribution, 5 Against target,
6 Groups, 7 Pupils, 8 One pupil, 9 Compare with another source (e.g. mock
vs actual), 10 Attainment 8 / Progress 8, 11 Export CSV. Rules:
:mod:`modules.reporting.domain.results_analysis`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.assessment.domain import headline_measures as HM
from education_system.systems.secondary.modules.reporting.cli import report_prompts as RP
from education_system.systems.secondary.modules.reporting.domain import results_analysis as RA
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt

_state: dict[str, Any] = {}


def _pick_source(principal: Principal, label: str = "Analyse") -> str | None:
    srcs = RA.sources(principal)
    if not srcs:
        print("  No assessment points, mock series or exam series yet.")
        return None
    for i, s in enumerate(srcs, 1):
        print(f"   {i:>2}) {s.label} - {s.detail}")
    n = prompts.ask_int(f"  {label} (number): ")
    if n is None or not 1 <= n <= len(srcs):
        print("  Nothing chosen.")
        return None
    return srcs[n - 1].key


def _analysis(principal: Principal) -> RA.Analysis:
    if "analysis" not in _state:
        raise RA.ValidationError(["Choose what to analyse first (option 1)"])
    return _state["analysis"]


def _choose(principal: Principal) -> None:
    key = _pick_source(principal)
    if not key:
        return
    f = RP.filters(_state.setdefault("filters", {}), dates=False)
    code = prompts.ask("Subject code (blank = all)", f.get("subject") or None)
    if code is not None:
        f["subject"] = code
    sid = None
    if f.get("subject"):
        from education_system.systems.secondary.modules.curriculum.domain import subjects as S
        s = S.get_by_code(f["subject"])
        if s is None:
            raise RA.ValidationError([f"No subject {f['subject']}"])
        sid = s.subject_id
    _state["source"] = key
    _state["analysis"] = a = RA.analyse(principal, key, year_group=f.get("year") or None,
                                        subject_id=sid, form=f.get("form") or None)
    print(f"\n  {a.source.label}: {len(a.results)} result(s)")


def _section(section: str):
    def show(principal: Principal) -> None:
        a = _analysis(principal)
        print(f"\n  {RA.SECTIONS[section]} - {a.source.label}")
        RP.table(*RA.table(a, section))
    return show


def _pupil(principal: Principal) -> None:
    a = _analysis(principal)
    pid = RP.pupil_id()
    if pid is not None:
        print()
        print(RA.pupil_text(a, pid))


def _compare(principal: Principal) -> None:
    first = _state.get("source") or _pick_source(principal, "First (e.g. the mock)")
    if not first:
        return
    second = _pick_source(principal, "Compare with (e.g. the real results)")
    if not second:
        return
    f = _state.get("filters", {})
    c = RA.compare(principal, first, second, year_group=f.get("year") or None)
    _state["compare"] = c
    print(f"\n  {len(c['pairs'])} matched grade(s); average change "
          f"{RA.RC.show(c['avg_diff'])}")
    RP.table(*RA.compare_table(c))
    if prompts.yes("  Show pupil by pupil?"):
        RP.table(*RA.compare_table(c, True))


def _a8(principal: Principal) -> None:
    year = prompts.ask_int("  Year group [11]: ") or 11
    school_year = _prompt("  School year (blank = this year): ") or None
    src = prompts.pick("A8 source", list(HM.SOURCES), "Actual") or "Actual"
    a8 = RA.a8p8(principal, year_group=year, academic_year=school_year, record_source=src)
    _state["a8"] = a8
    s, p = a8["a8"], a8["p8"]
    print(f"\n  A8 records {s['records']}, average A8 {RA.RC.show(s['average_a8'])}; "
          f"P8 records {p['records']}, average P8 {RA.RC.show(p['average_p8'])}")
    RP.table(*RA.table(None, "a8p8", a8=a8))


def _export(principal: Principal) -> None:
    section = prompts.pick("Section", [*RA.SECTIONS, "compare"], "subjects") or "subjects"
    path = RP.csv_path(f"results_{section}.csv")
    if not path:
        return
    if section == "compare":
        if "compare" not in _state:
            raise RA.ValidationError(["Run a comparison first (option 9)"])
        n = RA.export_compare_csv(path, _state["compare"], actor=principal)
    elif section == "a8p8":
        if "a8" not in _state:
            raise RA.ValidationError(["Run Attainment 8 / P8 first (option 10)"])
        n = RA.export_csv(path, None, section, actor=principal, a8=_state["a8"])
    else:
        n = RA.export_csv(path, _analysis(principal), section, actor=principal)
    print(f"  Exported {n} row(s).")


_OPTIONS = {"1": _choose, "2": _section("headline"), "3": _section("subjects"),
            "4": _section("distribution"), "5": _section("targets"), "6": _section("groups"),
            "7": _section("pupils"), "8": _pupil, "9": _compare, "10": _a8, "11": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("results_analysis.view")
        print("\n  ── Results Analysis ──")
        print("    1) Choose what to analyse\n    2) Headline\n    3) Subjects"
              "\n    4) Grade distribution\n    5) Against target\n    6) Groups\n    7) Pupils"
              "\n    8) One pupil\n    9) Compare (e.g. mock vs actual)"
              "\n   10) Attainment 8 / Progress 8\n   11) Export CSV")
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
