"""Compliance options of the Staff HR reports menu: equality monitoring (and
the person's own declaration), gender pay gap, HESA staff return, HR
retention. The domain modules check access themselves; these menus only
print what they are refused.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.university.domains.staff.domain.staff_hr import (
    access,
    equality,
    hesa_staff,
    pay_gap,
    retention,
)


def actor_for(user_id: Any = None, auth: Any = None) -> Any:
    """The session to act as: ``auth`` when given, else a user dict built
    from ``user_id`` (a username or users.id) and the person's role."""
    if auth is not None and access.user_of(auth):
        return auth
    from education_system.systems.university.infrastructure.database.db import get_connection
    with get_connection() as conn:
        key = access.staff_key(user_id, conn)
        row = conn.execute("SELECT role FROM users WHERE username = ?", (key,)).fetchone() \
            if key else None
    return {'username': key, 'role': row[0] if row else 'staff'} if key else {}


def _pause() -> None:
    input("\nPress Enter to continue...")


def _attempt(fn):
    try:
        return fn()
    except PermissionError as e:
        print(f"\nNot permitted: {e}")
    except (ValueError, LookupError) as e:
        print(f"\nCannot do that: {e}")
    except Exception as e:  # noqa: BLE001 - report, keep the menu running
        print(f"\nError: {type(e).__name__}: {e}")
    return None


def _choose(question: str, answers: tuple, current: Any) -> Any:
    print(f"\n{question}" + (f"  [now: {current}]" if current else ""))
    for i, a in enumerate(answers, 1):
        print(f"  {i}. {a}")
    raw = input("Choice (Enter to keep, '-' to clear): ").strip()
    if not raw:
        return current
    if raw == '-':
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(answers):
        return answers[int(raw) - 1]
    print("Not a choice; kept as it was.")
    return current


def my_equality(actor: Any) -> None:
    print("\n--- My Equality Information ---")
    print("Answering is voluntary. Your answers are kept apart from your personnel record;")
    print("HR only sees counts, with small groups hidden.")
    current = _attempt(lambda: equality.get_own(actor))
    if current is None and not access.username_of(actor):
        return _pause()
    current = current or {}
    for field in equality.FIELDS:
        print(f"  {equality.CATEGORIES[field][0]}: {current.get(field) or '(not answered)'}")
    action = input("\n1. Change my answers  2. Withdraw all my answers  0. Back: ").strip()
    if action == '1':
        answers = {f: _choose(q, a, current.get(f)) for f, (q, a) in equality.CATEGORIES.items()}
        if _attempt(lambda: equality.declare(actor, **answers)) is not None:
            print("\nThank you — your answers are saved.")
    elif action == '2' and input("Delete all your answers? (y/N): ").strip().lower() == 'y':
        if _attempt(lambda: equality.withdraw(actor)):
            print("Withdrawn.")
    _pause()


def equality_report(actor: Any) -> None:
    print("\n--- Equality Monitoring ---")
    print("Break down by: 0. nothing  " + "  ".join(f"{i}. {g}" for i, g in
                                                     enumerate(equality.GROUP_BY, 1)))
    raw = input("Choice: ").strip()
    group = equality.GROUP_BY[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(
        equality.GROUP_BY) else None
    report = _attempt(lambda: equality.aggregate(actor, group_by=group))
    if report:
        print()
        print("\n".join(equality.report_lines(report)))
        if access.can(actor, 'hr_admin'):
            raw = input(f"Change the smallest reportable group (now {report['min_group']})? "
                        "New value or Enter: ").strip()
            if raw.isdigit():
                _attempt(lambda: equality.set_min_group(actor, int(raw)))
    _pause()


def pay_gap_report(actor: Any) -> None:
    print("\n--- Gender Pay Gap ---")
    default = pay_gap.snapshot_for().isoformat()
    snap = input(f"Snapshot date [{default}]: ").strip() or default
    r = _attempt(lambda: pay_gap.gender_pay_gap(actor, snap))
    if r:
        print()
        print("\n".join(pay_gap.report_lines(r)))
    _pause()


def hesa_return(actor: Any) -> None:
    while True:
        print("\n--- HESA Staff Return ---")
        print("  1. Validate a year")
        print("  2. Set a person's date of birth / nationality")
        print("  3. Generate the return (HR administrators)")
        print("  4. List staff returns")
        print("  5. Export a return's XML to a file (HR administrators)")
        print("  6. Set the UKPRN (HR administrators)")
        print("  0. Back")
        choice = input("Choice: ").strip()
        if choice == '0':
            return
        if choice == '1':
            year = input(f"Academic year [{hesa_staff.year_bounds()[0]}]: ").strip() or None
            v = _attempt(lambda: hesa_staff.validate(actor, year))
            if v:
                print(f"\n{v['academic_year']}: {v['people']} staff, {v['contracts']} contracts; "
                      f"{v['without_declaration']} without an equality declaration")
                for issue in v['issues']:
                    print(f"  {issue['employee_id'] or '-':<10}{issue['username']}")
                    for m in issue['missing']:
                        print(f"      - {m}")
                if v['valid']:
                    print("No missing data.")
        elif choice == '2':
            who = input("Username or employee number: ").strip()
            dob = input("Date of birth (YYYY-MM-DD, Enter to keep): ").strip() or None
            nation = input("Nationality (Enter to keep): ").strip() or None
            if _attempt(lambda: hesa_staff.set_personal_details(actor, who, dob, nation)) is None:
                print("Saved (if anything was entered).")
        elif choice == '3':
            year = input(f"Academic year [{hesa_staff.year_bounds()[0]}]: ").strip() or None
            allow = input("Store as a draft even with missing data? (y/N): ").strip().lower() == 'y'
            r = _attempt(lambda: hesa_staff.create_return(actor, year, allow_errors=allow))
            if r:
                print(f"Return {r['return_id']} ({r['academic_year']}) saved as {r['status']}; "
                      f"{len(r['issues'])} record(s) with missing data."
                      + ("" if r['ukprn_set'] else " UKPRN not set."))
        elif choice == '4':
            for r in _attempt(lambda: hesa_staff.list_returns(actor)) or []:
                print(f"  #{r['id']:<5}{r['academic_year']:<10}{r['status']:<12}"
                      f"{r['created_by'] or '':<16}{r['created_at'] or ''}")
        elif choice == '5':
            rid = input("Return number: ").strip()
            path = input("Save to file: ").strip()
            if rid.isdigit() and path:
                xml = _attempt(lambda: hesa_staff.export_xml(actor, int(rid)))
                if xml is not None:
                    with open(path, 'w', encoding='utf-8') as fh:
                        fh.write(xml)
                    print(f"Written to {path}")
        elif choice == '6':
            value = input("UKPRN (8 digits): ").strip()
            if value.isdigit() and len(value) == 8:
                _attempt(lambda: equality.set_setting(actor, 'ukprn', value))
            else:
                print("A UKPRN is 8 digits.")
        else:
            print("Invalid choice.")


def retention_menu(actor: Any) -> None:
    while True:
        print("\n--- HR Record Retention ---")
        print("  1. Policies")
        print("  2. Preview what is due")
        print("  3. Run now")
        print("  4. Change a policy")
        print("  5. Holds   6. Place a hold   7. Release a hold")
        print("  8. Erase a leaver's HR data")
        print("  9. Recent runs")
        print("  0. Back")
        choice = input("Choice: ").strip()
        if choice == '0':
            return
        if choice == '1':
            for p in retention.policies():
                print(f"  {p['record_type']:<24}{p['keep_months']:>4} months {p['trigger']:<24}"
                      f"then {p['action']:<10}{'' if p['enabled'] else '(off)'}")
        elif choice == '2':
            for p in _attempt(lambda: retention.preview(actor)) or []:
                print(f"  {p['record_type']:<24}{p['table'][:33]:<34}{p['action']:<11}"
                      f"due {p['due']:>4}  people {p['people']}"
                      f"{'' if p.get('enabled', True) else '  (off)'}")
        elif choice == '3':
            if input("Delete or anonymise everything now due? (y/N): ").strip().lower() == 'y':
                for d in _attempt(lambda: retention.run(actor)) or []:
                    print(f"  {d['record_type']:<24}{d['table']:<34}{d['action']:<11}{d['rows']:>5}")
        elif choice == '4':
            rtype = input("Record type: ").strip()
            months = input("Months to keep (Enter to keep): ").strip()
            action = input("anonymise / delete (Enter to keep): ").strip().lower() or None
            enabled = input("Enabled? (y/n, Enter to keep): ").strip().lower()
            _attempt(lambda: retention.update_policy(
                actor, rtype, int(months) if months.isdigit() else None, action,
                None if not enabled else enabled == 'y'))
        elif choice == '5':
            for h in _attempt(lambda: retention.list_holds(actor)) or []:
                print(f"  #{h['hold_id']:<5}{h['username']:<20}{h['placed_at']:<21}{h['reason']}")
        elif choice == '6':
            who = input("Username: ").strip()
            reason = input("Reason: ").strip()
            if _attempt(lambda: retention.place_hold(actor, who, reason)):
                print("Hold placed.")
        elif choice == '7':
            hold = input("Hold number: ").strip()
            if hold.isdigit() and _attempt(lambda: retention.release_hold(actor, int(hold))):
                print("Released.")
        elif choice == '8':
            who = input("Leaver's username: ").strip()
            if who and input(f"Erase {who}'s HR data now? (y/N): ").strip().lower() == 'y':
                r = _attempt(lambda: retention.erase_leaver(actor, who))
                if r:
                    print(f"Erased; now '{r['alias']}' in HR records.")
                    for d in r['done']:
                        print(f"  {d['record_type']}: {d['rows']} {d['table']} row(s) {d['action']}d")
                    for k in r['kept']:
                        print(f"  kept {k['record_type']}: {k['rows']} {k['table']} row(s) "
                              f"until {k['until']}")
        elif choice == '9':
            for r in _attempt(lambda: retention.recent_runs(actor)) or []:
                print(f"  {r['at']:<21}{r['actor'] or '':<18}{r['record_type']:<24}"
                      f"{r['table_name'][:30]:<31}{r['action']:<10}{r['rows_affected']:>5}")
        else:
            print("Invalid choice.")


__all__ = ['actor_for', 'equality_report', 'hesa_return', 'my_equality', 'pay_gap_report',
           'retention_menu']
