"""The HESA Data Futures builder for the terminal, through ``application/statutory``."""

from __future__ import annotations

from datetime import date

from education_system.systems.university.application.statutory import access as sa
from education_system.systems.university.application.statutory import hesa_codes, hesa_return


def _current_year() -> str:
    today = date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return f"{start}/{(start + 1) % 100:02d}"


def _ask_year() -> str:
    default = _current_year()
    return input(f"Academic year [{default}]: ").strip() or default


def _build(user) -> None:
    year = _ask_year()
    periods = hesa_return.reference_periods(year)
    for number, period in enumerate(periods, start=1):
        print(f"  {number}. {period['label']}")
    picked = input("Reference period [1]: ").strip() or "1"
    if not picked.isdigit() or not 1 <= int(picked) <= len(periods):
        print("\n✗ Not one of the listed periods.")
        return
    period = periods[int(picked) - 1]
    built = hesa_return.build(user, year, period_start=period["start"], period_end=period["end"],
                              reference_period=period["label"])
    print(f"\nReturn #{built['return_id']} ({built['status']}): {built['errors']} error(s), "
          f"{built['warnings']} warning(s).")
    for entity, count in built["counts"].items():
        print(f"  {entity}: {count}")
    print(f"Upload file: {built['output_path'] or 'none - fix the errors and build again'}")
    for issue in built["issues"][:20]:
        print(f"  [{issue['level']}] {issue['student_id']} {issue['entity']}.{issue['field']}: "
              f"{issue['message']}")
    if len(built["issues"]) > 20:
        print(f"  ... and {len(built['issues']) - 20} more (option 2 saves them all)")


def _save_report(user) -> None:
    return_id = input("Return ID: ").strip()
    if not return_id.isdigit():
        print("\n✗ A return ID is a number.")
        return
    text = hesa_return.report_csv(user, int(return_id))
    path = input("Save the issues CSV to: ").strip()
    if not path:
        print(text)
        return
    with open(path, "w", encoding="utf-8", newline="") as out:
        out.write(text)
    print(f"Saved to {path}")


def _missing(user) -> None:
    rows = hesa_return.missing_sids(user, _ask_year())
    if not rows:
        print("\nEvery student in this year's return has a SID.")
    for row in rows:
        print(f"  {row['student_id']:<14} {row['name']}")


def _import_sids(user) -> None:
    path = input("CSV file (columns student_id, sid): ").strip()
    with open(path, encoding="utf-8-sig", newline="") as src:
        result = hesa_return.import_sids(user, src.read())
    print(f"\n{result['recorded']} recorded, {len(result['refused'])} refused.")
    for refused in result["refused"]:
        print(f"  Line {refused['line']}: {refused['error']}")


def _codes(user) -> None:
    sa.officer(user)
    for number, field in enumerate(hesa_codes.FIELDS, start=1):
        print(f"  {number}. {field}")
    picked = input("Field: ").strip()
    if not picked.isdigit() or not 1 <= int(picked) <= len(hesa_codes.FIELDS):
        print("\n✗ Not one of the listed fields.")
        return
    field = hesa_codes.FIELDS[int(picked) - 1]
    with sa.session() as conn:
        rows = hesa_codes.frame(conn, field)
    for row in rows:
        state = "" if row.get("active", 1) else " (inactive)"
        print(f"  {row['code']:<10} {row['label']}{state}")
    code = input("\nCode to add or edit (blank to leave): ").strip()
    if code:
        label = input("Label: ").strip()
        active = input("Active? (y/n) [y]: ").strip().lower() != "n"
        hesa_codes.save_code(user, field, code, label, active)
        print("Saved.")


def hesa_menu(auth) -> None:
    """Reference periods, the validation report, SIDs and coding frames."""
    user = getattr(auth, "current_user", None)
    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("HESA DATA FUTURES".center(70))
        print("=" * 70)
        print("\n  1. Build and validate a return")
        print("  2. Save a return's validation issues as CSV")
        print("  3. Students with no SID")
        print("  4. Record a SID")
        print("  5. Import SIDs from CSV")
        print("  6. Coding frames")
        print("\n  0. Back")
        print("=" * 70)
        choice = input("\nSelect: ").strip()
        if choice == "0":
            return
        try:
            if choice == "1":
                _build(user)
            elif choice == "2":
                _save_report(user)
            elif choice == "3":
                _missing(user)
            elif choice == "4":
                hesa_return.set_sid(user, input("Student: ").strip(),
                                    input("SID (13 digits): ").strip())
                print("Saved.")
            elif choice == "5":
                _import_sids(user)
            elif choice == "6":
                _codes(user)
            else:
                print("\nChoose one of the listed options.")
        except (PermissionError, ValueError, OSError) as exc:
            print(f"\n✗ {exc}")
        input("\nPress Enter to continue...")


# ── Student Loans Company ───────────────────────────────────────────────


def _pick_census(user) -> str | None:
    from education_system.systems.university.application.statutory import slc

    points = slc.census_points(user)
    if not points:
        print("\nNo SLC census dates yet: add a 'census_slc' key date in the Academic Calendar.")
        return None
    for number, p in enumerate(points, start=1):
        print(f"  {number}. {str(p['start_date'])[:10]}  {p.get('title') or ''} "
              f"({p.get('year_code') or '?'})")
    picked = input(f"Census point [{len(points)}]: ").strip() or str(len(points))
    if not picked.isdigit() or not 1 <= int(picked) <= len(points):
        print("\n✗ Not one of the listed census points.")
        return None
    return str(points[int(picked) - 1]["start_date"])[:10]


def _slc_worklist(user) -> None:
    from education_system.systems.university.application.statutory import slc

    day = _pick_census(user)
    if not day:
        return
    work = slc.worklist(user, day)
    print(f"\n{'Student':<12} {'Name':<26} {'Att%':>5}  {'Suggested':<14} {'Decision':<14} Why")
    print("-" * 100)
    for r in work["rows"]:
        pct = "" if r["attendance_pct"] is None else f"{r['attendance_pct']:.0f}"
        print(f"{r['student_id']:<12} {r['name'][:26]:<26} {pct:>5}  {r['suggested']:<14} "
              f"{(r['decision'] or '-'):<14} {r['why'] or ''}")
    undecided = [r for r in work["rows"] if not r["decision"]]
    print(f"\n{len(work['rows'])} registered, {len(undecided)} undecided.")
    if undecided and input("Accept the suggested decision for every undecided student? "
                           "(y/n): ").strip().lower() == "y":
        slc.decide(user, day, {r["student_id"]: (r["suggested"], r["why"] or None)
                               for r in undecided})
        print(f"Recorded {len(undecided)} decision(s).")


def _slc_decide(user) -> None:
    from education_system.systems.university.application.statutory import slc

    day = _pick_census(user)
    if not day:
        return
    sid = input("Student: ").strip()
    status = input(f"Decision ({'/'.join(slc.STATUSES)}): ").strip().lower()
    reason = input("Reason (required for held): ").strip() or None
    slc.decide(user, day, {sid: (status, reason)})
    print("Saved.")


def _slc_changes(user) -> None:
    from education_system.systems.university.application.statutory import slc

    added = slc.sync_changes(user)
    if added:
        print(f"\n{added} new change notice(s) raised.")
    rows = slc.changes(user, "pending")
    if not rows:
        print("\nNo pending change-of-circumstance notices.")
        return
    for r in rows:
        name = " ".join(p for p in (r.get("first_name"), r.get("last_name")) if p)
        print(f"  #{r['notification_id']:<5} {r['student_id']:<12} {name[:24]:<24} "
              f"{r['effective_date'] or '':<11} {r['change_type']}  {r.get('details') or ''}")


def _slc_mark(user) -> None:
    from education_system.systems.university.application.statutory import slc

    nid = input("Notice #: ").strip()
    if not nid.isdigit():
        print("\n✗ A notice number is a number.")
        return
    status = input("Status (acknowledged/not_required/pending): ").strip().lower()
    ref = input("SLC reference: ").strip() or None if status == "acknowledged" else None
    slc.set_change_status(user, int(nid), status, ref)
    print("Saved.")


def _slc_export(user) -> None:
    from education_system.systems.university.application.statutory import slc

    day = _pick_census(user) if input("Include a census point's confirmations? (y/n) [y]: "
                                      ).strip().lower() != "n" else None
    include = input("Include pending change notices? (y/n) [y]: ").strip().lower() != "n"
    result = slc.export(user, day, include_changes=include)
    if not result["path"]:
        print("\nNothing new to send (holds stay back).")
        return
    print(f"\nBatch {result['batch_id']}: {result['confirmations']} confirmation(s), "
          f"{result['changes']} change notice(s).")
    print(f"Upload through the SLC provider portal: {result['path']}")


def slc_menu(auth) -> None:
    """SLC attendance confirmation and change-of-circumstance notices."""
    user = getattr(auth, "current_user", None)
    actions = {"1": _slc_worklist, "2": _slc_decide, "3": _slc_changes, "4": _slc_mark,
               "5": _slc_export}
    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("STUDENT LOANS COMPANY".center(70))
        print("=" * 70)
        print("\n  1. Census worklist (and accept suggestions)")
        print("  2. Record one student's decision")
        print("  3. Changes of circumstance (find new, list pending)")
        print("  4. Mark a change notice acknowledged / not required")
        print("  5. Write the SLC upload file")
        print("\n  0. Back")
        print("=" * 70)
        choice = input("\nSelect: ").strip()
        if choice == "0":
            return
        try:
            if choice in actions:
                actions[choice](user)
            else:
                print("\nChoose one of the listed options.")
        except (PermissionError, ValueError, OSError) as exc:
            print(f"\n✗ {exc}")
        input("\nPress Enter to continue...")
