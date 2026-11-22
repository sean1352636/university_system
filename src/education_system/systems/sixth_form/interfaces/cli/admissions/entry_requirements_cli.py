"""CLI: entry requirements, applicant GCSEs, structured offer conditions."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
    entry_requirements as er,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _input,
    _pause,
    _pick_applicant,
    _pick_from,
    _run_submenu,
    _yes,
)


def _user() -> str | None:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def list_requirements_flow() -> None:
    print("\n═══ Entry requirements ═══")
    rows = er.list_requirements()
    if not rows:
        print("  (none set)")
    for r in rows:
        print(f"  {r.programme}")
        for line in r.describe() or ["(no rules)"]:
            print(f"      • {line}")
    missing = er.programmes_without_requirements()
    if missing:
        print("\n  Chosen by applicants but without requirements: "
              + ", ".join(missing))
    _pause()


def set_requirement_flow() -> None:
    print("\n═══ Set entry requirement ═══")
    print(f"  Programme = a subject/course name, or '{er.GENERAL_PROGRAMME}'.")
    prog = _input("Programme", default=er.GENERAL_PROGRAMME, allow_empty=False)
    old = er.get_requirement(prog)
    count = _input("Minimum number of GCSEs",
                   default=str(old.min_gcse_count or "") if old else "")
    grade = _input("…at grade (9-1)",
                   default=str(old.min_gcse_grade or "") if old else "")
    avg = _input("Minimum average point score",
                 default=str(old.min_average_points or "") if old else "")
    subs = _input("Subject minimums (Subject=grade; …)", default="; ".join(
        f"{s}={g}" for s, g in old.subject_minimums.items()) if old else "")
    minimums = {}
    for part in subs.split(";"):
        if "=" in part:
            s, g = part.split("=", 1)
            minimums[s.strip()] = g.strip()
    try:
        r = er.set_requirement(prog, min_gcse_count=count, min_gcse_grade=grade,
                               min_average_points=avg,
                               subject_minimums=minimums, updated_by=_user())
        print("  ✓ Saved: " + "; ".join(r.describe()))
    except er.ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


def delete_requirement_flow() -> None:
    rows = er.list_requirements()
    if not rows:
        print("  (none set)")
        return _pause()
    prog = _pick_from("Delete which", [r.programme for r in rows])
    if _yes(f"Delete the requirement for {prog}?"):
        er.delete_requirement(prog)
        print("  ✓ Deleted")
    _pause()


def _show_applicant(aid: str) -> None:
    a = adm.get_applicant(aid)
    print(f"\n  {aid} {a.full_name if a else ''} — offer "
          f"{(a.offer_type if a else None) or 'none'}")
    print("  GCSEs:")
    for g in er.list_gcses(aid):
        print(f"    [{g.result_type:<9}] {g.subject:<24} {g.grade:<3} "
              f"{g.kind} ({g.source})")
    print("  Conditions:")
    for c in er.list_conditions(aid):
        print(f"    #{c.condition_id:<4} {c.description:<50} "
              f"{c.effective_outcome}  {c.outcome_detail or ''}")


def applicant_gcses_flow() -> None:
    print("\n═══ Applicant GCSEs & conditions ═══")
    a = _pick_applicant()
    aid = a.applicant_id
    actions = [
        ("Show", lambda: (_show_applicant(aid), _pause())),
        ("Add / replace GCSE", lambda: _add_gcse(aid)),
        ("Delete GCSE", lambda: _delete_gcse(aid)),
        ("Read predicted GCSEs from application text", lambda: _from_text(aid)),
        ("Generate conditions from entry requirements",
         lambda: _generate(aid)),
        ("Add condition (free text)", lambda: _add_cond(aid)),
        ("Delete condition", lambda: _delete_cond(aid)),
        ("Set staff outcome on a condition", lambda: _manual(aid)),
        ("Evaluate against predicted", lambda: _evaluate(aid, "Predicted")),
        ("Evaluate against actual", lambda: _evaluate(aid, "Actual")),
        ("Make conditional offer from conditions", lambda: _offer(aid)),
    ]
    _run_submenu(f"GCSEs & conditions — {aid}", actions)


def _add_gcse(aid: str) -> None:
    rt = _pick_from("Result type", list(er.RESULT_TYPES), default="Actual")
    subj = _input("Subject", allow_empty=False)
    grade = _input("Grade (9-1 or A*-G)", allow_empty=False)
    kind = _pick_from("Kind", list(er.GCSE_KINDS), default="GCSE")
    year = _input("Year", default="")
    try:
        er.record_gcse(aid, subj, grade, result_type=rt, kind=kind,
                       year=year or None, entered_by=_user())
        print("  ✓ Recorded")
    except er.ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


def _delete_gcse(aid: str) -> None:
    rows = er.list_gcses(aid)
    if not rows:
        print("  (no results)")
        return _pause()
    label = _pick_from("Delete", [f"{g.id}: {g.result_type} {g.subject} "
                                  f"{g.grade}" for g in rows])
    er.delete_gcse(int(label.split(":")[0]))
    print("  ✓ Deleted")
    _pause()


def _from_text(aid: str) -> None:
    n, unread = er.import_predicted_from_text(aid, entered_by=_user())
    print(f"  ✓ {n} predicted result(s) recorded")
    for u in unread:
        print(f"    could not read: {u}")
    _pause()


def _generate(aid: str) -> None:
    rows = er.generate_conditions(aid)
    print(f"  ✓ {len(rows)} condition(s): {er.conditions_text(aid) or '—'}")
    _pause()


def _add_cond(aid: str) -> None:
    kind = _pick_from("Kind", list(er.CONDITION_KINDS), default="other")
    kw = {"kind": kind}
    if kind == "subject_grade":
        kw["subject"] = _input("GCSE subject", allow_empty=False)
        kw["min_grade"] = _input("Grade (9-1)", allow_empty=False)
    elif kind == "gcse_count":
        kw["min_count"] = _input("Number of GCSEs", allow_empty=False)
        kw["min_grade"] = _input("At grade (9-1)", default="4")
    elif kind == "average_points":
        kw["min_points"] = _input("Average point score", allow_empty=False)
    kw["description"] = _input("Wording (blank = automatic)", default="") or None
    try:
        c = er.add_condition(aid, **kw)
        print(f"  ✓ Added: {c.description}")
    except er.ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


def _pick_condition(aid: str) -> int | None:
    rows = er.list_conditions(aid)
    if not rows:
        print("  (no conditions)")
        return None
    label = _pick_from("Condition", [f"{c.condition_id}: {c.description}"
                                     for c in rows])
    return int(label.split(":")[0])


def _delete_cond(aid: str) -> None:
    cid = _pick_condition(aid)
    if cid:
        er.delete_condition(cid)
        print("  ✓ Deleted")
    _pause()


def _manual(aid: str) -> None:
    cid = _pick_condition(aid)
    if cid:
        o = _pick_from("Outcome", ["(automatic)"] + list(er.MANUAL_OUTCOMES))
        er.set_manual_outcome(cid, None if o == "(automatic)" else o,
                              by=_user())
        print("  ✓ Saved")
    _pause()


def _evaluate(aid: str, rt: str) -> None:
    ev = er.evaluate(aid, result_type=rt)
    for c in ev.conditions:
        print(f"    {c.description:<50} {c.effective_outcome:<9} "
              f"{c.outcome_detail or ''}")
    print(f"\n  Overall ({rt}, {ev.results_used} results): {ev.overall}")
    _pause()


def _offer(aid: str) -> None:
    try:
        a = er.make_structured_offer(aid, decided_by=_user(),
                                     regenerate=not er.list_conditions(aid))
        print(f"  ✓ Offer made: {a.offer_conditions or '(no conditions)'}")
    except er.ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


def import_results_flow() -> None:
    print("\n═══ Import GCSE results CSV ═══")
    print("  Columns: applicant_id (or uln/upn), subject, grade "
          "[, kind, year, exam_board]")
    path = _input("CSV path", allow_empty=False)
    rt = _pick_from("Result type", list(er.RESULT_TYPES), default="Actual")
    try:
        n, errors = er.import_results_csv(path, result_type=rt,
                                          entered_by=_user())
    except OSError as e:
        print(f"  ✗ {e}")
        return _pause()
    print(f"  ✓ {n} row(s) recorded")
    for e in errors[:40]:
        print(f"    {e}")
    _pause()


MENU = [
    ("List entry requirements", list_requirements_flow),
    ("Set / edit a requirement", set_requirement_flow),
    ("Delete a requirement", delete_requirement_flow),
    ("─" * 6, lambda: None),
    ("Applicant GCSEs & conditions…", applicant_gcses_flow),
    ("Import GCSE results CSV", import_results_flow),
]


def run() -> None:
    _run_submenu("Entry Requirements & GCSEs", MENU)
