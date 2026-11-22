"""School Census in the terminal (data manager only).

The old Census menu keeps its numbers: 1 List all returns, 2 Overdue
returns, 3 Open windows, 4 Drafts, 5 Submitted, 6 Accepted, 7 Filter
returns, 8 View return, 10 New return, 11 Edit return, 12 Mark validated,
13 Submit, 14 Accept, 15 Reject, 16 Resubmit, 17 Archive, 18 Record
validation counts, 19 Change return status, 20 Delete return, 22 List all
aims, 23 Active aims, 24 Aims for return, 25 Aims for learner, 26 New aim,
27 Edit aim, 28 Delete aim (:mod:`census_aims_cli`), 30 Summary.

New, after "More": 31 Census dates, 32 Build a return, 33 Validation report,
34 Return pupils, 35 Attendance, 36 Exclusions, 37 Save the built return,
38 Export CSV, 39 Export XML. Rules: :mod:`modules.reporting.domain.census`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.reporting.cli import census_aims_cli as AC
from education_system.systems.secondary.modules.reporting.cli import report_prompts as RP
from education_system.systems.secondary.modules.reporting.domain import census as CE
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import current_year
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt

_state: dict[str, Any] = {}


def _runs(rows: list[dict[str, Any]]) -> None:
    RP.table(["Id", "Ov", "Type", "Year", "Census day", "Deadline", "Submitted", "Learners",
              "Errors", "Warnings", "Status"],
             [[r["return_id"], "!" if r["is_overdue"] else "", r["return_type"],
               r["academic_year"], r["census_date"], r["deadline"], r["submitted_on"],
               r["pupils"], r["errors"], r["queries"], r["status"]] for r in rows],
             limit=None, width=24)


def _lister(**kw: Any):
    def show(principal: Principal) -> None:
        _runs(CE.list_runs(principal, **kw))
    return show


def _filter(principal: Principal) -> None:
    rt = prompts.pick("Type (blank = any)", CE.RETURN_TYPES)
    st = prompts.pick("Status (blank = any)", CE.RETURN_STATUSES)
    yr = _prompt("  Academic year (blank = any): ") or None
    _runs(CE.list_runs(principal, return_type=rt or None, status=st or None, academic_year=yr))


def _id() -> int | None:
    return prompts.ask_int("  Return id: ")


def _view(principal: Principal) -> None:
    rid = _id()
    if rid is None:
        return
    r = CE.get_run(principal, rid)
    for k in ("return_id", "return_type", "academic_year", "census_date", "status",
              "window_opens", "window_closes", "deadline", "submitted_on", "submitted_by",
              "accepted_on", "pupils", "sen_k", "sen_e", "fsm", "exclusions", "errors",
              "queries", "file_ref", "exported_as", "notes", "created_by", "created_at"):
        print(f"  {k:<16} {RP.RC.show(r.get(k))}")
    for k, n in r["error_kinds"].items():
        print(f"    {k}: {n}")


def _fields(current: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rt = prompts.pick("Return type", CE.RETURN_TYPES,
                      (current or {}).get("return_type", CE.RETURN_TYPES[0]))
    if rt:
        out["return_type"] = rt
    for key, label in (("academic_year", "Academic year"), ("census_date", "Reference date"),
                       ("window_opens", "Window opens"), ("window_closes", "Window closes"),
                       ("deadline", "Submission deadline"), ("submitted_on", "Submitted on"),
                       ("submitted_by", "Submitted by"), ("accepted_on", "Accepted on"),
                       ("pupils", "Learner count"), ("errors", "Error count"),
                       ("queries", "Warning count"), ("file_ref", "File ref"),
                       ("notes", "Notes")):
        cur = (current or {}).get(key, current_year() if key == "academic_year" else None)
        v = prompts.ask(label, RP.RC.show(cur) if cur not in (None, "") else None)
        if v is not None:
            out[key] = v
        elif current is None and key == "academic_year":
            out[key] = cur
    st = prompts.pick("Status", CE.RETURN_STATUSES, (current or {}).get("status", "Planned"))
    if st:
        out["status"] = st
    return out


def _new(principal: Principal) -> None:
    r = CE.create_return(_fields(None), actor=principal)
    print(f"  Created return #{r['return_id']}.")


def _edit(principal: Principal) -> None:
    rid = _id()
    if rid is not None:
        CE.update_return(rid, _fields(CE.get_run(principal, rid)), actor=principal)
        print("  Saved.")


def _move(action: str):
    def go(principal: Principal) -> None:
        rid = _id()
        if rid is None:
            return
        ref = _prompt("  File reference (optional): ") if action in ("submit",
                                                                     "resubmit") else None
        r = CE.move(rid, action, actor=principal, file_ref=ref or None)
        print(f"  Return #{rid} is now {r['status']}.")
    return go


def _counts(principal: Principal) -> None:
    rid = _id()
    if rid is not None:
        CE.record_counts(rid, actor=principal, errors=_prompt("  Errors: "),
                         queries=_prompt("  Warnings: "))
        print("  Saved.")


def _status(principal: Principal) -> None:
    rid = _id()
    st = prompts.pick("Status", CE.RETURN_STATUSES) if rid is not None else None
    if st:
        CE.set_status(rid, st, actor=principal)  # type: ignore[arg-type]
        print("  Saved.")


def _delete(principal: Principal) -> None:
    rid = _id()
    if rid is not None and prompts.yes(f"  Delete return #{rid}?"):
        CE.delete_return(rid, actor=principal)
        print("  Deleted.")


def _summary(principal: Principal) -> None:
    s = CE.runs_summary(principal)
    for k in ("total", "planned", "in_progress", "submitted", "accepted", "rejected",
              "overdue", "open_windows"):
        print(f"  {k.replace('_', ' ').capitalize():<16} {s[k]}")
    print("  By type:", ", ".join(f"{k} {v}" for k, v in s["by_type"].items()) or "-")
    print("  By status:", ", ".join(f"{k} {v}" for k, v in s["by_status"].items()) or "-")
    AC.summary(principal)


def _dates(_principal: Principal) -> None:
    year = _prompt(f"  School year [{current_year()}]: ") or current_year()
    for t in CE.TERMS:
        pr = CE.periods(t, year)
        print(f"  {t:<7} census day {CE.census_date(t, year)}; attendance "
              f"{pr['attendance_term']} ({pr['attendance_from']}..{pr['attendance_to']}); "
              f"exclusions {pr['exclusions_term']}")


def _build(principal: Principal) -> None:
    term0, year0 = CE.next_census()
    term = prompts.pick("Census", CE.TERMS, term0) or term0
    year = _prompt(f"  School year [{year0}]: ") or year0
    day = _prompt("  Census day (blank = the DfE day): ") or None
    _state["ret"] = ret = CE.build(term, year, actor=principal, on=day)
    print()
    print("\n".join("  " + x for x in ret.summary_lines()))


def _ret() -> CE.CensusReturn:
    if "ret" not in _state:
        raise CE.ValidationError(["Build a return first (option 32)"])
    return _state["ret"]


def _part(part: str):
    def show(_principal: Principal) -> None:
        RP.table(*CE.table(_ret(), part), limit=200)
    return show


def _save(principal: Principal) -> None:
    rid = CE.save_run(_ret(), actor=principal, notes=_prompt("  Notes (optional): ") or None)
    print(f"  Saved as return #{rid}.")


def _export_csv(principal: Principal) -> None:
    ret = _ret()
    part = prompts.pick("Part", list(CE.PARTS), "pupils") or "pupils"
    path = RP.csv_path(f"census_{ret.term.lower()}_{part}.csv")
    if path:
        print(f"  Exported {CE.export_csv(ret, path, part, actor=principal)} row(s).")


def _export_xml(principal: Principal) -> None:
    ret = _ret()
    path = _prompt(f"  Save XML to [census_{ret.term.lower()}.xml]: ") or \
        f"census_{ret.term.lower()}.xml"
    default = CE.school_identity()[1]
    laestab = _prompt(f"  LA/Estab number [{default or 'not set in Settings'}]: ") or default
    print(f"  Wrote {CE.export_xml(ret, path, actor=principal, laestab=laestab)} pupil(s).")


_OPTIONS = {"1": _lister(), "2": _lister(overdue_only=True), "3": _lister(open_only=True),
            "4": _lister(status="Draft"), "5": _lister(status="Submitted"),
            "6": _lister(status="Accepted"), "7": _filter, "8": _view, "10": _new,
            "11": _edit, "12": _move("validate"), "13": _move("submit"),
            "14": _move("accept"), "15": _move("reject"), "16": _move("resubmit"),
            "17": _move("archive"), "18": _counts, "19": _status, "20": _delete,
            "22": AC.list_all, "23": AC.list_active, "24": AC.for_return,
            "25": AC.for_learner, "26": AC.new, "27": AC.edit, "28": AC.delete,
            "30": _summary, "31": _dates, "32": _build, "33": _part("problems"),
            "34": _part("pupils"), "35": _part("attendance"), "36": _part("exclusions"),
            "37": _save, "38": _export_csv, "39": _export_xml}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("census.view")
        print("\n  ── School Census ──")
        print("    1) List all returns\n    2) Overdue returns\n    3) Open windows"
              "\n    4) Drafts\n    5) Submitted\n    6) Accepted\n    7) Filter returns"
              "\n    8) View return")
        print("   10) New return\n   11) Edit return\n   12) Mark validated\n   13) Submit"
              "\n   14) Accept\n   15) Reject\n   16) Resubmit\n   17) Archive"
              "\n   18) Record validation counts\n   19) Change return status"
              "\n   20) Delete return")
        print("   22) List all aims\n   23) Active aims\n   24) Aims for return"
              "\n   25) Aims for learner\n   26) New aim\n   27) Edit aim\n   28) Delete aim")
        print("   30) Summary")
        print("  More")
        print("   31) Census dates\n   32) Build a return\n   33) Validation report"
              "\n   34) Return pupils\n   35) Attendance\n   36) Exclusions"
              "\n   37) Save the built return\n   38) Export CSV\n   39) Export XML")
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
        except (*RP.ERRORS, OSError) as e:
            prompts.problem(e)
        _pause()
