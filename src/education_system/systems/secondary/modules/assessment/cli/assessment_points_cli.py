"""Assessment points (termly data drops) in the terminal. There was no old
version. Rules live in :mod:`modules.assessment.domain.assessment_points`."""

from __future__ import annotations

from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (AP.ValidationError, AP.PermissionDenied, AP.NotFound)


_problem = prompts.problem


def _print_points(rows: list[AP.Point]) -> None:
    if not rows:
        print("  (no assessment points)")
        return
    print(f"  {'ID':<4} {'Year':<8} {'Name':<24} {'Years':<12} {'Deadline':<11} "
          f"{'Done':<6} Status")
    for p in rows:
        s = AP.summary(p.point_id) if p.status != "Draft" else {"pct": None}
        print(f"  {p.point_id:<4} {p.academic_year:<8} {p.name[:24]:<24} "
              f"{p.years_label[:12]:<12} {(p.deadline or '-'):<11} "
              f"{'' if s['pct'] is None else str(s['pct']) + '%':<6} {p.status}"
              + (" (overdue)" if p.overdue else ""))


def _choose(statuses=None) -> AP.Point | None:
    rows = [p for p in AP.list_points() if statuses is None or p.status in statuses]
    if not rows:
        print("  No assessment points" + (" open" if statuses == ("Open",) else "") + ".")
        return None
    _print_points(rows)
    raw = _prompt("  Point ID (blank = first): ")
    if not raw:
        return rows[0]
    if not raw.isdigit():
        print("  Enter a number.")
        return None
    return AP.get_point(int(raw))


def _choose_group(principal: Principal, pt: AP.Point) -> TG.TeachingGroup | None:
    mine = AP.groups_for(pt, teacher=principal.username)
    groups = mine if mine and not (AP.is_editor(principal) and not _yes(
        "  Only your groups?")) else AP.groups_for(pt)
    if not groups:
        print("  No teaching groups for this point.")
        return None
    done = {r["group"].group_id: r for r in AP.completion(pt.point_id)}
    for i, g in enumerate(groups, 1):
        r = done.get(g.group_id)
        print(f"  {i:>3}) {g.code:<10} Y{g.year_group} {g.teacher_name or '':<20} "
              + (f"{r['done']}/{r['pupils']}" if r else ""))
    raw = _prompt("  Group number or code: ")
    if raw.isdigit() and 1 <= int(raw) <= len(groups):
        return groups[int(raw) - 1]
    g = next((g for g in groups if g.code.lower() == raw.lower()), None)
    if g is None and raw:
        print("  No such group.")
    return g


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("points.view")
        open_ = AP.list_points(status="Open")
        print("\n── Assessment Points ──")
        print(f"  Open now: {', '.join(p.name for p in open_) or 'none'}")
        print("   1) List points\n   2) New point\n   3) Edit a point"
              "\n   4) Open / close / publish / unpublish\n   5) Delete a point"
              "\n   6) Enter grades for a class\n   7) View a class's grades"
              "\n   8) Completion\n   9) Chase teachers by e-mail\n  10) Grade spread"
              "\n  11) Progress against an earlier point\n  12) Attitude concerns"
              "\n  13) One pupil's grades\n  14) Export / import (CSV)\n  15) History"
              "\n   0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        try:
            {"1": _list, "2": lambda: _edit(principal, None),
             "3": lambda: _edit(principal, _choose()), "4": lambda: _status(principal),
             "5": lambda: _delete(principal), "6": lambda: _enter(principal),
             "7": lambda: _view(principal), "8": _completion,
             "9": lambda: _chase(principal), "10": _spread, "11": _progress,
             "12": _concerns, "13": _pupil, "14": lambda: _csv(principal), "15": _history,
             }.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


def _list() -> None:
    year = _prompt(f"  School year (blank = all, e.g. {TG.current_year()}): ") or None
    _print_points(AP.list_points(academic_year=year))
    _pause()


def _edit(principal: Principal, p: AP.Point | None) -> None:
    cur = p
    data: dict = {}
    for key, label, hint in (("name", "Name", "e.g. Autumn data drop"),
                             ("year_groups", "Year groups", "e.g. 7,8,9"),
                             ("ks3_scale", "KS3 scale", " / ".join(AP.SCALES)),
                             ("ks4_scale", "KS4 scale", " / ".join(AP.SCALES)),
                             ("opens_on", "Opens on", "YYYY-MM-DD"),
                             ("deadline", "Deadline", "YYYY-MM-DD"),
                             ("notes", "Notes", "")):
        current = getattr(cur, key) if cur else None
        v = _ask(label, current, required=key in ("name", "year_groups") and cur is None,
                 hint=hint)
        if v is not None:
            data[key] = v
    for key, label in (("collect_predicted", "Collect predicted grades"),
                       ("collect_attitude", "Collect attitude to learning"),
                       ("collect_homework", "Collect homework"),
                       ("collect_comment", "Collect a comment")):
        on = getattr(cur, key) if cur else key in ("collect_predicted", "collect_attitude")
        raw = _prompt(f"  {label}? (y/n) [{'y' if on else 'n'}]: ").lower()
        data[key] = (raw in {"y", "yes"}) if raw else on
    if cur:
        p = AP.update_point(cur.point_id, data, actor=principal)
    else:
        p = AP.create_point(data, actor=principal)
    print(f"  ✓ {p.name} ({p.academic_year}, Y{p.years_label}) - {p.status}")


def _status(principal: Principal) -> None:
    p = _choose()
    if not p:
        return
    to = _prompt(f"  {p.name} is {p.status}. Move to (Draft/Open/Closed/Published): ")
    if not to:
        return
    p = AP.set_status(p.point_id, to, actor=principal)
    print(f"  ✓ {p.name} is now {p.status}")


def _delete(principal: Principal) -> None:
    p = _choose()
    if not p:
        return
    n = len(AP.grades(p.point_id))
    if _yes(f"  Delete '{p.name}'" + (f" and its {n} grade(s)" if n else "") + "?"):
        AP.delete_point(p.point_id, actor=principal)
        print("  ✓ Deleted")


def _enter(principal: Principal) -> None:
    pt = _choose(("Open", "Closed"))
    g = pt and _choose_group(principal, pt)
    if not pt or not g:
        return
    scale = pt.scale_for(g.year_group)
    print(f"\n  {g.code} - scale: {', '.join(scale)}. Enter keeps a value, '-' clears it.")
    if pt.collect_attitude or pt.collect_homework:
        print("  Attitude / homework: " + ", ".join(f"{k} {v}" for k, v in AP.ATTITUDE.items()))
    suggested = AP.from_gradebook(pt.point_id, g.group_id)
    changes = {}
    fields = [("working_at", "Working at")] + [c for on, c in (
        (pt.collect_predicted, ("predicted", "Predicted")),
        (pt.collect_attitude, ("attitude", "Attitude")),
        (pt.collect_homework, ("homework", "Homework")),
        (pt.collect_comment, ("comment", "Comment"))) if on]
    for p, x in AP.sheet(pt.point_id, g.group_id):
        print(f"\n  {p.display_name} ({p.admission_no})")
        row = {k: (getattr(x, k) if x else None) for k, _l in fields}
        if not row["working_at"] and p.pupil_id in suggested:
            print(f"    gradebook says {suggested[p.pupil_id]}")
        changed = False
        for k, label in fields:
            cur = row[k]
            v = _ask(f"  {label}", None if cur is None else str(cur))
            if v is not None:
                row[k] = v or None
                changed = True
        if changed:
            changes[p.pupil_id] = row
    if not changes:
        print("  Nothing changed.")
        return
    n = AP.save_sheet(pt.point_id, g.group_id, changes, actor=principal)
    print(f"  ✓ Saved {n} pupil(s)")


def _view(principal: Principal) -> None:
    pt = _choose()
    g = pt and _choose_group(principal, pt)
    if not pt or not g:
        return
    print(f"\n  {pt.name} - {g.code}")
    print(f"  {'Pupil':<24} {'Working at':<11} {'Predicted':<11} {'Att':<4} {'Hw':<4} Comment")
    for p, x in AP.sheet(pt.point_id, g.group_id):
        print(f"  {p.display_name[:24]:<24} {(x and x.working_at) or '-':<11} "
              f"{(x and x.predicted) or '-':<11} {(x and x.attitude) or '-':<4} "
              f"{(x and x.homework) or '-':<4} {(x and x.comment) or ''}")
    _pause()


def _completion() -> None:
    pt = _choose(("Open", "Closed", "Published"))
    if not pt:
        return
    print(f"\n  {'Group':<10} {'Subj':<6} {'Yr':<3} {'Teacher':<22} Entered")
    for r in AP.completion(pt.point_id):
        g = r["group"]
        print(f"  {g.code:<10} {r['subject_code'][:6]:<6} {g.year_group:<3} "
              f"{(g.teacher_name or '-')[:22]:<22} {r['done']}/{r['pupils']} ({r['pct']}%)")
    s = AP.summary(pt.point_id)
    print(f"\n  {s['complete']} of {s['groups']} groups complete · {s['done']} of "
          f"{s['pupils']} grades in")
    _pause()


def _chase(principal: Principal) -> None:
    pt = _choose(("Open",))
    if not pt or not _yes("  E-mail every teacher with unfinished groups?"):
        return
    r = AP.chase(pt.point_id, actor=principal)
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    for mid in r["sent"]:
        report = E.deliver(mid, principal=principal)
    print(f"  ✓ E-mailed {len(r['sent'])} teacher(s)"
          + (f" ({report.mode})" if r["sent"] else ""))
    if r["no_email"]:
        print("  No e-mail address: " + ", ".join(r["no_email"]))


def _year() -> int | None:
    y = _prompt("  Year group (7-11, blank = all): ")
    return int(y) if y.isdigit() else None


def _spread() -> None:
    pt = _choose()
    if not pt:
        return
    d = AP.distribution(pt.point_id, year_group=_year())
    for s, c in d["subjects"].items():
        print(f"  {s:<8} " + "  ".join(f"{g}: {n}" for g, n in c.items()))
    if not d["subjects"]:
        print("  No grades yet.")
    if d["attitude"]:
        print("  Attitude: " + "  ".join(f"{k}: {v}" for k, v in d["attitude"].items()))
    _pause()


def _progress() -> None:
    print("  This point:")
    pt = _choose()
    if not pt:
        return
    print("  Compare with:")
    before = _choose()
    if not before:
        return
    r = AP.progress(pt.point_id, before.point_id, year_group=_year())
    print(f"\n  Up {r['up']} · same {r['same']} · down {r['down']}"
          + (f" · different scale {r['different_scale']}" if r["different_scale"] else ""))
    for d in r["declines"]:
        print(f"   ↓ {d['pupil_name'][:24]:<24} Y{d['year']} {d['subject_code']:<6} "
              f"{d['before']} → {d['now']}")
    _pause()


def _concerns() -> None:
    pt = _choose()
    if not pt:
        return
    raw = _prompt("  In at least how many subjects? [2]: ")
    rows = AP.attitude_concerns(pt.point_id, min_subjects=int(raw) if raw.isdigit() else 2)
    if not rows:
        print("  None.")
    for c in rows:
        print(f"  {c['pupil_name'][:24]:<24} {c['admission_no']:<10} Y{c['year']} "
              f"{c['form'] or '':<5} {c['subjects']}")
    _pause()


def _pupil() -> None:
    ref = _prompt("  Admission number or UPN: ")
    p = P.find_by_reference(ref) if ref else None
    if p is None:
        print("  No such pupil." if ref else "")
        return
    pt = _choose()
    if not pt:
        return
    rows = AP.pupil_report(pt.point_id, p.pupil_id)
    print(f"\n  {p.display_name} · {pt.name}")
    for x in rows:
        print(f"  {x.subject_code:<8} working at {x.working_at or '-':<11} predicted "
              f"{x.predicted or '-':<11} attitude {x.attitude or '-'}"
              + (f"  homework {x.homework}" if x.homework else "")
              + (f"\n           {x.comment}" if x.comment else ""))
    if not rows:
        print("  No grades at this point.")
    _pause()


def _csv(principal: Principal) -> None:
    what = _prompt("  1) Export a point  2) Import a class's grades: ")
    if what == "1":
        pt = _choose()
        path = pt and _prompt("  Save to (path.csv): ")
        if pt and path:
            print(f"  ✓ Exported {AP.export_point(pt.point_id, path, actor=principal)} row(s)")
    elif what == "2":
        pt = _choose(("Open", "Closed"))
        g = pt and _choose_group(principal, pt)
        if not pt or not g:
            return
        print("  Columns: Admission no, Working at, and optionally Predicted, Attitude, "
              "Homework, Comment.")
        path = _prompt("  File: ")
        if path:
            try:
                n = AP.import_grades(pt.point_id, g.group_id, path, actor=principal)
            except (OSError, UnicodeDecodeError) as e:
                print(f"  Couldn't read the file: {e}")
                return
            print(f"  ✓ Imported {n} pupil(s)")


def _history() -> None:
    pt = _choose()
    if not pt:
        return
    for h in AP.history(pt.point_id):
        print(f"  {h['at']}  {h['actor']:<14} {h['action']:<8} "
              + ", ".join(f"{k}: {v}" for k, v in h["detail"].items()))
    _pause()

