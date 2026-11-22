"""Staff Directory in the terminal.

The old Staff Directory menu keeps its options in place: 1 List Active Staff,
2 List All Staff, 3 Filter Staff, 4 Search, 5 View, 6 New, 7 Edit, 8 Mark as
Left, 9 Delete, 10 Summary. New: 11 Leavers, 12 Reinstate a leaver,
13 Qualifications & ECT, 14 Personal & HR (HR only), 15 Link login,
16 Import logins, 17 History, 18 Export CSV. View now shows the profile
(forms tutored, teaching groups, timetable, cover, departments, reports).
Rules live in :mod:`modules.staff.domain.staff_directory`.

:func:`ask_fields` is shared with the Departments and Appraisals menus.
"""

from __future__ import annotations

from typing import Any, Sequence

from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (SD.ValidationError, SD.PermissionDenied, SD.NotFound)
_problem = prompts.problem

#: (key, label, options) - options: None (free text), "bool", or a list.
Field = tuple[str, str, Any]


def ask_fields(fields: Sequence[Field], current: Any = None) -> dict[str, Any]:
    """Ask each field; Enter keeps the current value (or skips), ``-`` clears."""
    out: dict[str, Any] = {}
    for key, label, options in fields:
        cur = getattr(current, key, None) if current is not None else None
        if options == "bool":
            shown = "y" if cur else "n"
            v = prompts.ask(label, shown if current is not None else None, hint="y/n")
            if v:
                out[key] = v.lower().startswith("y")
        elif options:
            v = prompts.pick(label, list(options), str(cur) if cur not in (None, "") else None)
            if v and v != (str(cur) if cur is not None else None):
                out[key] = v
        else:
            v = prompts.ask(label, None if cur is None else str(cur))
            if v is not None:
                out[key] = v
    return out


def _staff(label: str = "Staff (code, username or id)") -> SD.StaffMember | None:
    ref = _prompt(f"  {label}: ")
    if not ref:
        return None
    m = SD.find(ref)
    if m is None:
        print(f"  ✗ No staff {ref}")
    return m


def _table(rows: list[SD.StaffMember]) -> None:
    if not rows:
        print("\n  (no staff)")
        return
    print(f"\n  {'ID':<10}  {'Name':<26}  {'Role':<22}  {'Department':<18}  {'Status':<12}  "
          f"{'Room':<6}  Flags")
    print("  " + "-" * 110)
    for s in rows:
        print(f"  {s.staff_code:<10}  {s.sort_name[:26]:<26}  {s.role[:22]:<22}  "
              f"{(s.department or '')[:18]:<18}  {s.employment_status:<12}  "
              f"{(s.room or ''):<6}  {s.flags}")
    print(f"\n  {len(rows)} staff. (Flags: T=Tutor D=DSL E=Examiner)")


def _list_active(p: Principal) -> None:
    print("\n═══ Active Staff ═══")
    _table([m for m in SD.list_staff(actor=p) if m.is_active])


def _list_all(p: Principal) -> None:
    print("\n═══ Staff Directory ═══")
    _table(SD.list_staff(include_leavers=True, actor=p))


def _filter(p: Principal) -> None:
    print("\n═══ Filter Staff ═══\n  (blank to skip)")
    role = prompts.pick("Role", SD.ROLES)
    rtype = prompts.pick("Role type", SD.ROLE_TYPES)
    dept = _prompt("  Department: ")
    status = prompts.pick("Employment status", SD.EMPLOYMENT_STATUSES)
    _table(SD.list_staff(role=role or None, role_type=rtype or None, department=dept or None,
                         employment_status=status or None, include_leavers=True,
                         tutors=_yes("  Tutors only?"), dsl=_yes("  DSLs only?"), actor=p))


def _search(p: Principal) -> None:
    print("\n═══ Search Staff ═══")
    q = _prompt("  Search: ")
    if q:
        _table(SD.search_staff(q, actor=p))


def _view(p: Principal) -> None:
    print("\n═══ View Staff ═══")
    m = _staff()
    if m:
        print()
        print("\n".join("  " + line for line in SD.profile_text(m.staff_id, actor=p)
                        .splitlines()))


_CORE: list[Field] = [
    ("staff_code", "Staff ID (blank = made up)", None), ("username", "Login (username)", None),
    ("title", "Title", SD.TITLES), ("first_name", "First name", None),
    ("last_name", "Last name", None), ("preferred_name", "Preferred name", None),
    ("job_title", "Job title", None), ("role", "Role", SD.ROLES),
    ("role_type", "Role type", SD.ROLE_TYPES), ("department", "Department", None),
    ("employment_status", "Employment status", SD.EMPLOYMENT_STATUSES),
    ("contract_type", "Contract", SD.CONTRACT_TYPES), ("fte", "FTE (e.g. 0.6)", None),
    ("start_date", "Start date", None), ("leave_date", "End date", None),
    ("room", "Room", None), ("extension", "Extension", None),
    ("work_email", "Work e-mail", None), ("work_phone", "Work phone", None),
    ("line_manager_id", "Line manager (code)", None), ("is_tutor", "Tutor", "bool"),
    ("is_dsl", "DSL", "bool"), ("is_examiner", "Examiner", "bool"), ("notes", "Notes", None)]
_QUALS: list[Field] = [
    ("qts", "QTS", "bool"), ("qts_date", "QTS date", None),
    ("trn", "Teacher reference number", None), ("ect_status", "ECT status", SD.ECT_STATUSES),
    ("ect_start", "Induction start", None), ("ect_mentor_id", "ECT mentor (code)", None),
    ("qualifications", "Qualifications", None)]
_PRIVATE: list[Field] = [(k, SD.LABELS[k], "bool" if k == "pension_enrolled" else (
    SD.SALARY_SCALES if k == "salary_scale" else None)) for k in SD.PRIVATE_FIELDS]


def _new(p: Principal) -> None:
    print("\n═══ New Staff ═══")
    waiting = SD.unlinked_logins()
    if waiting:
        print("  Logins without a record: " + ", ".join(s["username"] for s in waiting[:15]))
    m = SD.create(ask_fields(_CORE), actor=p)
    print(f"\n  ✓ Created {m.staff_code} — {m.full_name} ({m.role})")
    if m.email:
        print(f"    Email: {m.email}")


def _edit_with(p: Principal, fields: list[Field], title: str) -> None:
    print(f"\n═══ {title} ═══")
    m = _staff()
    if m:
        print("  (Enter keeps a value, '-' clears it)")
        SD.update(m.staff_id, ask_fields(fields, m), actor=p)
        print(f"\n  ✓ Updated {m.staff_code}")


def _edit(p: Principal) -> None:
    _edit_with(p, _CORE, "Edit Staff")


def _quals(p: Principal) -> None:
    _edit_with(p, _QUALS, "Qualifications & ECT")


def _personal(p: Principal) -> None:
    if not SD.is_editor(p):
        print("  Only HR sees personal and HR fields.")
        return
    _edit_with(p, _PRIVATE, "Personal & HR")


def _mark_left(p: Principal) -> None:
    print("\n═══ Mark Staff as Left ═══")
    m = _staff()
    if m is None:
        return
    day = _prompt("  End date (YYYY-MM-DD, blank = today): ")
    reason = prompts.pick("Reason", SD.LEAVING_REASONS)
    m = SD.mark_left(m.staff_id, day or None, reason=reason or None, actor=p)
    print(f"\n  ✓ Marked {m.staff_code} as Left ({m.leave_date}) - the record is kept")


def _delete(p: Principal) -> None:
    print("\n═══ Delete Staff ═══")
    m = _staff()
    if m and _yes(f"  Delete {m.full_name} ({m.staff_code})? Only for a record made in error"):
        SD.delete(m.staff_id, actor=p)
        print("  ✓ Deleted.")


def _summary(_p: Principal) -> None:
    s = SD.summary()
    print(f"\n═══ Staff Summary ═══\n  Total: {s['total']}  Current: {s['current']}  Active: "
          f"{s['active']}  Left: {s['left']}  FTE: {s['fte']}")
    print(f"  Tutors: {s['tutors']}  DSLs: {s['dsls']}  Examiners: {s['examiners']}  "
          f"Without login: {s['without_login']}  Logins without a record: "
          f"{s['logins_without_record']}")
    if s["unfilled_critical"]:
        print("  ⚠ No one in: " + ", ".join(s["unfilled_critical"]))
    if s["ects_without_mentor"]:
        print("  ⚠ ECTs without a mentor: " + ", ".join(
            m.full_name for m in s["ects_without_mentor"]))
    for title, key in (("By role type", "by_role_type"), ("By role", "by_role"),
                       ("By department", "by_department"), ("By status", "by_status")):
        print(f"\n  {title}:")
        for k, n in s[key].items():
            print(f"    {k:<28}: {n}")


def _leavers(p: Principal) -> None:
    print("\n═══ Leavers ═══")
    _table(SD.list_staff(leavers_only=True, actor=p))


def _reinstate(p: Principal) -> None:
    m = _staff("Leaver (code)")
    if m:
        st = prompts.pick("Coming back as", [s for s in SD.EMPLOYMENT_STATUSES if s != "Left"],
                          SD.DEFAULT_EMPLOYMENT_STATUS)
        SD.reinstate(m.staff_id, actor=p, status=st or SD.DEFAULT_EMPLOYMENT_STATUS)
        print("  ✓ Reinstated.")


def _link(p: Principal) -> None:
    m = _staff()
    if m:
        waiting = SD.unlinked_logins()
        print("  Logins without a record: " + (", ".join(s["username"] for s in waiting)
                                               or "(none)"))
        u = _prompt(f"  Login [{m.username or 'none'}] ('-' to unlink): ")
        if u:
            SD.link_login(m.staff_id, None if u == "-" else u, actor=p)
            print("  ✓ Saved.")


def _import(p: Principal) -> None:
    waiting = SD.unlinked_logins()
    if not waiting:
        print("  Every staff login already has a record.")
        return
    for s in waiting:
        print(f"    {s['display_name']} ({s['username']})")
    if _yes(f"  Make records for these {len(waiting)} login(s)?"):
        print(f"  ✓ Made {len(SD.import_logins(actor=p))} record(s).")


def _history(_p: Principal) -> None:
    m = _staff()
    if m:
        for h in SD.history(m.staff_id):
            print(f"  {h['at']}  {h['actor']:<12} {h['action']:<10} "
                  + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


def _export(p: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. staff.csv): ")
    if path:
        personal = SD.is_editor(p) and _yes("  Include personal and HR fields?")
        n = SD.export_csv(path, actor=p, include_personal=personal, include_leavers=True)
        print(f"  Exported {n} member(s) of staff.")


_OPTIONS = {"1": _list_active, "2": _list_all, "3": _filter, "4": _search, "5": _view,
            "6": _new, "7": _edit, "8": _mark_left, "9": _delete, "10": _summary,
            "11": _leavers, "12": _reinstate, "13": _quals, "14": _personal, "15": _link,
            "16": _import, "17": _history, "18": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("staff.view")
        print("\n── Staff Directory ──")
        print("   1) List Active Staff\n   2) List All Staff\n   3) Filter Staff\n   4) Search"
              "\n   5) View\n   6) New\n   7) Edit\n   8) Mark as Left\n   9) Delete"
              "\n  10) Summary")
        print("  More")
        print("  11) Leavers\n  12) Reinstate a leaver\n  13) Qualifications & ECT"
              "\n  14) Personal & HR\n  15) Link login\n  16) Import logins\n  17) History"
              "\n  18) Export CSV")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        except OSError as e:
            print(f"\n  ✗ {e}")
        _pause()
