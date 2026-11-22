"""CLI: module registration - the same rules as the Module Registration
portal (``application/modules/registration`` and
``module_registration_admin``)."""

from __future__ import annotations

from contextlib import closing

from education_system.systems.university.application.modules import catalogue
from education_system.systems.university.application.modules import registration as reg
from education_system.systems.university.application.modules import registration_messages as msgs
from education_system.systems.university.application.modules import registration_admin as setup
from education_system.systems.university.infrastructure.database.db import get_connection

STAFF = ("admin", "administrator", "superadmin", "staff", "registrar", "lecturer",
         "instructor", "faculty")
ADMINS = ("admin", "administrator", "superadmin", "registrar")


def _run(fn, *args, write=False, **kwargs):
    try:
        with closing(get_connection(row_factory=False)) as conn:
            result = fn(conn, *args, **kwargs)
            if write:
                conn.commit()
            return True if result is None else result
    except ValueError as exc:
        print(f"Refused: {exc}")
        return None


def _who(auth):
    user = getattr(auth, "current_user", None) or {}
    role = str(user.get("role") or "").lower()
    return (user.get("username") or "unknown", role, user.get("student_id")
            or user.get("username"))


def _show(student_id):
    d = _run(reg.overview, student_id)
    if not isinstance(d, dict):
        return None
    s, r = d["student"], d["rules"]
    print(f"\n{s['name']} ({s['student_id']}) {s['course']} year {s['year_of_study']} - "
          f"{s['status']}; registration {d['window']['phase']}; {d['credits']} credits "
          f"(target {r['target_credits']}, max {r['max_credits']})")
    if d["blocked"]:
        print(f"  ! {d['blocked']}")
    for kind in ("compulsory", "optional"):
        print(f"  {kind.title()}:")
        for m in d["structure"][kind]:
            print(f"    {m['code']:<12} {m['name'][:40]:<40} {m['credits'] or '-':>4}  "
                  f"{m['state'] or ''}")
    if d["pending"]:
        print(f"  Awaiting approval: {', '.join(d['pending']['modules'])}")
    return d


def _after(student_id, results):
    for code, result in results.items():
        print(f"  {code}: {result}")
        if result in ("enrolled", "reinstated"):
            failed = reg.side_effects(student_id, code)
            if failed:
                print(f"    follow-up to check: {', '.join(failed)}")


def _student_menu(student_id, actor, staff):
    while _show(student_id):
        choice = input("1 enrol compulsory  2 choose options  3 drop  4 annual registration"
                       + ("  5 enrol other (override)" if staff else "")
                       + "  6 browse catalogue  0 back: ").strip()
        if choice == "1":
            result = _run(reg.enrol_compulsory, student_id, actor, write=True)
            if isinstance(result, dict):
                _after(student_id, result)
        elif choice == "2":
            codes = input("Optional module codes (comma-separated): ").split(",")
            result = _run(reg.submit_choices, student_id, codes, actor, write=True)
            if isinstance(result, dict):
                print("Sent for approval." if result["status"] == "submitted" else "")
                _after(student_id, result["results"])
        elif choice == "3":
            code = input("Module code to drop: ").strip()
            reason = input("Reason: ").strip() if staff else None
            status = _run(reg.drop, student_id, code, actor, staff=staff, reason=reason,
                          write=True)
            if status:
                print(f"{code}: {status}")
                if not msgs.after_drop(student_id, code, status, reason, actor):
                    print("  (the acknowledgement message could not be sent)")
        elif choice == "4":
            _annual(student_id, actor)
        elif choice == "6":
            _browse(student_id)
        elif choice == "5" and staff:
            code = input("Module code: ").strip()
            override = input("Override reason if outside the structure (blank = none): ")
            result = _run(reg.enrol, student_id, code, actor, staff=True,
                          override=override.strip() or None, write=True)
            if isinstance(result, dict):
                _after(student_id, {code: result["result"]})
        else:
            return


def _browse(student_id):
    """The module catalogue, read-only, with any module's details."""
    filters = _run(catalogue.catalogue_filters) or {"departments": [], "levels": []}
    if filters["departments"]:
        print("Departments: " + ", ".join(filters["departments"]))
    department = input("Department (blank = all): ").strip() or None
    level = input("Level (blank = all): ").strip() or None
    search = input("Search code / title (blank = all): ").strip() or None
    rows = _run(catalogue.catalogue, department=department, level=level, search=search,
                student_id=student_id) or []
    for m in rows:
        print(f"  {m['module_code']:<12} {(m['module_name'] or '')[:40]:<40} "
              f"{m['credits'] or '-':>4}  L{m['level'] or '-':<3} {m.get('for_you') or ''}")
    print(f"{len(rows)} module(s). Modules outside your course structure are added by staff "
          "(ask your personal tutor or the Registry).")
    while True:
        code = input("Module code for details (blank = back): ").strip()
        if not code:
            return
        d = _run(catalogue.module_details, code, student_id=student_id)
        if isinstance(d, dict):
            print("\n" + catalogue.details_text(d) + "\n")


def _annual(student_id, actor):
    answers = {}
    for text in reg.DECLARATIONS:
        answers[text] = input(f"{text} (y/N): ").strip().lower() == "y"
    mode = input("Mode of study [full-time]: ").strip() or "full-time"
    try:
        result = reg.annual_register(student_id, actor, declarations=answers,
                                     mode_of_study=mode, returning=True)
    except ValueError as exc:
        print(f"Refused: {exc}")
        return
    print(f"Registered for {result['academic_year']}.")
    _after(student_id, result["modules"])


def _approvals(actor, admin):
    rows = _run(reg.submissions, actor, admin=admin) or []
    for r in rows:
        print(f"  #{r['id']} {r['student_id']} {r['name']} ({r['course']}): "
              f"{', '.join(r['modules'])}")
    pick = input("Submission number (blank = back): ").strip()
    if not pick.isdigit():
        return
    approve = input("Approve? (y = approve, n = reject): ").strip().lower() == "y"
    note = "" if approve else input("Reason: ").strip()
    result = _run(reg.decide, int(pick), approve, actor, admin=admin, note=note, write=True)
    if isinstance(result, dict):
        sid = next((r["student_id"] for r in rows if r["id"] == int(pick)), None)
        _after(sid, result["results"])


def _setup(actor):
    choice = input("1 add registration period  2 credit rules  3 set module credits  "
                   "4 fix enrolment records  0 back: ").strip()
    if choice == "1":
        fields = {k: input(f"{label}: ").strip() or None for k, label in (
            ("academic_year", "Academic year"), ("opens", "Opens (YYYY-MM-DD)"),
            ("closes", "Closes"), ("add_deadline", "Add deadline"),
            ("drop_deadline", "Drop deadline"), ("withdraw_deadline", "Withdrawal deadline"))}
        _run(setup.add_period, admin=True, write=True, **fields) and print("Added.")
    elif choice == "2":
        course, year = input("Course code: ").strip(), input("Year of study: ").strip()
        _run(setup.set_rules, course, year, target_credits=input("Target credits [120]: ") or 120,
             max_credits=input("Maximum credits [140]: ") or 140,
             min_optional=input("Fewest options [0]: ") or 0,
             max_optional=input("Most options (blank = no limit): ").strip() or None,
             needs_approval=input("Options need approval? (Y/n): ").lower() != "n",
             actor=actor, admin=True, write=True) and print("Saved.")
    elif choice == "3":
        missing = _run(setup.modules_without_credits) or []
        print(f"{len(missing)} module(s) have no credits.")
        codes = [c.strip() for c in input("Module codes (comma-separated): ").split(",") if c]
        if codes:
            n = _run(setup.set_credits, codes, input("Credits: ").strip(), actor, admin=True,
                     write=True)
            print(f"{n} module(s) updated." if n is not None else "")
    elif choice == "4":
        rows = _run(setup.mismatches) or []
        print(f"{len(rows)} enrolment(s) differ between student_modules and module_enrolments.")
        if rows and input("Fix them all? (y/N): ").lower() == "y":
            print(f"{_run(setup.fix_mismatches, actor, admin=True, write=True)} fixed.")


def display_module_registration_menu(auth=None):
    if auth is None:
        from education_system.systems.university.infrastructure.shared_context import get_auth
        auth = get_auth()
    actor, role, student_id = _who(auth)
    if role not in STAFF:
        _student_menu(student_id, actor, staff=False)
        return
    while True:
        choice = input("\nModule registration: 1 a student's registration  2 choices to approve"
                       + ("  3 setup" if role in ADMINS else "") + "  0 back: ").strip()
        if choice == "1":
            sid = input("Student ID: ").strip()
            if sid:
                _student_menu(sid, actor, staff=True)
        elif choice == "2":
            _approvals(actor, role in ADMINS)
        elif choice == "3" and role in ADMINS:
            _setup(actor)
        else:
            return
