"""CLI flows for Sixth Form Enrolment CRUD.

Mirrors `enrolment_views`: list/filter, create, view, edit, delete.
Wired in from `cli_main.py` via `dispatch("Enrolment")`, which opens a
small submenu since enrolment is itself a CRUD area.
"""

from __future__ import annotations

import logging
from typing import Callable
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    STATUSES,
    ValidationError,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments._common import (
    _ROW_SHORTCUTS,
    _UserAbort,
    _collect_form,
    _input,
    _menu_label,
    _pause,
    _pick_from,
    _print_table,
    _prompt_withdrawal,
    _record_undo,
    _print_leaver_effects,
    _resolve_enrolment,
    _row_action_loop,
    _show_checks,
    _writes_ok,
    requires_write,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments.enrolment_lifecycle_cli import (
    bulk_return_intention,
    enrolment_audit_history,
    record_return_intention,
    reinstate_withdrawn,
    reopen_completed,
    return_intention_summary,
    rollover_history,
    undo_rollover_flow,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments.enrolment_reports_cli import (
    academic_year_manager,
    capacity_utilisation,
    cohort_report,
    copy_enrolment_details,
    enrolment_dashboard,
    export_directory_csv,
    export_enrolment_pdf,
    export_progression_list,
    export_tutor_group_pdf,
    import_enrolments_csv,
    retention_report,
    tutor_group_roster,
    withdrawal_analysis,
    year_on_year_comparison,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments.enrolment_search_cli import (
    advanced_query,
    duplicate_conflicts,
    filter_by_date_range,
    filter_by_tutor_group,
    quick_filter_current_year,
    saved_filter_manager,
    search_enrolments,
    show_current_year_group,
    sort_enrolments,
    status_badges,
    student_enrolment_history,
    students_without_enrolment,
    sync_status_to_student_record,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments.enrolment_workflows_cli import (
    bulk_delete,
    bulk_enrol,
    bulk_status_change,
    bulk_tutor_reassign,
    duplicate_enrolment,
    end_of_year_rollover,
    enrol_from_student_profile,
    progression_wizard,
    reenrol_student,
    soft_delete_toggle,
    transfer_enrolment,
    undo_last_action,
    withdraw_enrolment,
    withdraw_with,
)

logger = logging.getLogger(__name__)


def list_all() -> None:
    print("\n═══ Enrolment Directory ═══")
    try:
        rows = data.list_enrolments()
    except Exception as e:
        logger.exception("CLI list_enrolments failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def filter_enrolments() -> None:
    print("\n═══ Filter Enrolments ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        year = _input("Academic year") or None
        yg_raw = _input("Year group (12 or 13)")
        status_raw = _input("Status (Enrolled / Pending / Withdrawn / Completed)")
        if status_raw:
            status_raw = next((s for s in STATUSES
                               if s.lower() == status_raw.lower()), status_raw)
    except _UserAbort:
        print("\n  Cancelled.")
        return

    yg: int | None = None
    if yg_raw:
        try:
            yg = int(yg_raw)
        except ValueError:
            print("  ✗ Year group must be a number.")
            _pause()
            return
    status = status_raw or None
    if status and status not in STATUSES:
        print(f"  ✗ Status must be one of: {', '.join(STATUSES)}")
        _pause()
        return

    try:
        rows = data.list_enrolments(
            academic_year=year, year_group=yg, status=status)
    except Exception as e:
        logger.exception("CLI filter_enrolments failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def new_enrolment() -> None:
    print("\n═══ New Enrolment ═══")
    if not _writes_ok():
        return
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        created = data.create_enrolment(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI new_enrolment failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return

    student = student_data.get_student(created.student_id)
    print()
    print(f"  ✓ Created enrolment #{created.enrolment_id}")
    print(f"      Student      : {created.student_id} "
          f"({student.full_name if student else '?'})")
    print(f"      Academic year: {created.academic_year}")
    print(f"      Year group   : {created.year_group}")
    print(f"      Tutor group  : {created.tutor_group or '—'}")
    print(f"      Status       : {created.status}")
    _show_checks(created.student_id, created.academic_year)
    _pause()


def view_enrolment(enrolment_id: int | None = None) -> None:
    print("\n═══ View Enrolment ═══")
    try:
        eid = enrolment_id if enrolment_id is not None else int(
            _input("Enrolment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Enrolment ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        e = data.get_enrolment(eid)
    except Exception as exc:
        logger.exception("CLI get_enrolment(%d) failed", eid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if e is None:
        print(f"  ✗ No enrolment #{eid}")
        _pause()
        return

    student = student_data.get_student(e.student_id)
    print()
    print(f"    Enrolment ID  : #{e.enrolment_id}")
    print(f"    Student       : {e.student_id} "
          f"({student.full_name if student else '(deleted)'})")
    print(f"    Academic year : {e.academic_year}")
    print(f"    Year group    : Year {e.year_group}")
    print(f"    Tutor group   : {e.tutor_group or '—'}")
    print(f"    Start date    : {e.start_date or '—'}")
    print(f"    Status        : {e.status}"
          + ("  (archived)" if e.is_archived else ""))
    if e.status == "Withdrawn":
        print(f"    Withdrawn     : {e.withdrawal_date or '—'} — "
              f"{e.withdrawal_reason_label or 'no reason'}"
              + (f" (by {e.withdrawn_by})" if e.withdrawn_by else ""))
        if e.withdrawal_detail:
            print(f"    Detail        : {e.withdrawal_detail}")
    if e.completed_at:
        print(f"    Completed     : {e.completed_at}")
    if e.year_group == 12 and (e.return_intention or e.status == "Enrolled"):
        print(f"    Year 13 return: {e.return_intention or 'not asked yet'}"
              + (f" ({e.return_intention_note})" if e.return_intention_note else ""))
    print(f"    Created       : {e.created_at}"
          + (f" by {e.recorded_by}" if e.recorded_by else ""))
    if e.is_archived:
        print(f"    Archived      : {(e.archived_at or '')[:16]} by "
              f"{e.archived_by or '—'}"
              + (f" — {e.archived_reason}" if e.archived_reason else ""))
    if e.notes:
        print(f"    Notes         : {e.notes}")
    print()
    _show_checks(e.student_id, e.academic_year)
    _print_leaver_effects(e.student_id)
    _pause()


def edit_enrolment(enrolment_id: int | None = None) -> None:
    print("\n═══ Edit Enrolment ═══")
    if not _writes_ok():
        return
    try:
        eid = enrolment_id if enrolment_id is not None else int(
            _input("Enrolment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Enrolment ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        existing = data.get_enrolment(eid)
    except Exception as exc:
        logger.exception("CLI get_enrolment(%d) failed", eid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if existing is None:
        print(f"  ✗ No enrolment #{eid}")
        _pause()
        return

    if existing.is_archived:
        print(f"  ✗ Enrolment #{eid} is archived — restore it first.")
        _pause()
        return
    try:
        payload = _collect_form(existing)
        then = payload.pop("_then", None)
        withdrawal = _prompt_withdrawal() if then == "withdraw" else None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        updated = data.update_enrolment(eid, payload)
    except (ValidationError, PermissionError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_enrolment(%d) failed", eid)
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated enrolment #{updated.enrolment_id}")
    _show_checks(updated.student_id, updated.academic_year)
    if withdrawal is not None:
        code, wd, detail, approved = withdrawal
        withdraw_with(eid, code=code, withdrawal_date=wd, detail=detail,
                      approved_by=approved)
    elif then == "complete":
        try:
            done, problems = data.complete_enrolment(eid)
            print(f"  ✓ #{eid} completed ({done.completed_at})")
            for p in problems:
                print(f"    ✗ aim: {p}")
        except (ValidationError, PermissionError) as e:
            print(f"  ✗ {e}")
    _pause()


def delete_enrolment_flow(enrolment_id: int | None = None) -> None:
    print("\n═══ Delete Enrolment (archive) ═══")
    if not _writes_ok():
        return
    try:
        eid = enrolment_id if enrolment_id is not None else int(
            _input("Enrolment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Enrolment ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        existing = data.get_enrolment(eid)
    except Exception as exc:
        logger.exception("CLI get_enrolment(%d) failed", eid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if existing is None:
        print(f"  ✗ No enrolment #{eid}")
        _pause()
        return

    if existing.is_archived:
        print(f"  Enrolment #{eid} is already archived — restore it from "
              "'Restore Archived Enrolment'.")
        _pause()
        return
    print("  Deleting archives the enrolment: it leaves every list but is "
          "kept, and can be restored with the same id.")
    confirm = _input(
        f"Delete enrolment #{existing.enrolment_id} "
        f"({existing.student_id}, {existing.academic_year})? "
        f"Type 'yes' to confirm",
        default="no",
    )
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    reason = _input("Reason", default="Deleted")
    try:
        if data.delete_enrolment(eid, reason=reason):
            # Feature #42 — undo restores the same row (same id).
            _record_undo(f"delete of #{eid} ({existing.student_id})",
                         lambda: data.restore_enrolment(eid))
            print(f"\n  ✓ Archived enrolment #{eid}")
        else:
            print(f"\n  ✗ Could not delete enrolment #{eid}")
    except Exception as e:
        logger.exception("CLI delete_enrolment(%d) failed", eid)
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


def list_archived_enrolments() -> None:
    print("\n═══ Archived Enrolments ═══")
    rows = data.list_enrolments(archived_only=True)
    for e in rows:
        print(f"  #{e.enrolment_id:<5} {e.student_id:<12} {e.academic_year} "
              f"Y{e.year_group} [{e.status}]  archived "
              f"{(e.archived_at or '')[:16]} by {e.archived_by or '—'}"
              + (f" — {e.archived_reason}" if e.archived_reason else ""))
    if not rows:
        print("  (none)")
    _pause()


def restore_enrolment_flow() -> None:
    print("\n═══ Restore Archived Enrolment ═══")
    if not _writes_ok():
        return
    rows = data.list_enrolments(archived_only=True)
    if not rows:
        print("  (nothing archived)")
        _pause()
        return
    labels = [f"#{e.enrolment_id} {e.student_id} {e.academic_year} "
              f"Y{e.year_group} [{e.status}]" for e in rows]
    eid = int(_pick_from("Enrolment", labels).split()[0].lstrip("#"))
    try:
        e = data.restore_enrolment(eid)
        print(f"  ✓ Restored #{e.enrolment_id} (same id)")
    except (ValueError, PermissionError) as exc:
        print(f"  ✗ {exc}")
    _pause()


def _init_row_shortcuts() -> None:
    """Populated lazily once the target functions are defined at module load."""
    _ROW_SHORTCUTS.update({
        "v": ("View", view_enrolment),
        "e": ("Edit", edit_enrolment),
        "d": ("Delete", delete_enrolment_flow),
        "w": ("Withdraw", withdraw_enrolment),
        "x": ("Archive / Restore (not a withdrawal)", soft_delete_toggle),
        "u": ("Duplicate", duplicate_enrolment),
        "t": ("Transfer", transfer_enrolment),
        "c": ("Copy details", copy_enrolment_details),
        "p": ("Print PDF", export_enrolment_pdf),
        "r": ("Reinstate (undo withdrawal)", reinstate_withdrawn),
        "o": ("Reopen completed", reopen_completed),
        "m": ("Context menu", context_menu),
    })


def keyboard_shortcuts_help() -> None:
    """Feature #43 — list the single-key row/record shortcuts."""
    if not _ROW_SHORTCUTS:
        _init_row_shortcuts()
    print("\n═══ Keyboard / Row Shortcuts ═══\n")
    for key, (label, _fn) in _ROW_SHORTCUTS.items():
        print(f"    {key.upper()}) {label}")
    print("\n  These work at the 'Action:' prompt after any listing,")
    print("  and inside the per-record context menu (M).")
    _pause()


def context_menu(enrolment_id: int | None = None) -> None:
    """Feature #44 — per-record action menu for one enrolment."""
    if not _ROW_SHORTCUTS:
        _init_row_shortcuts()
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    eid = e.enrolment_id
    # Exclude the context-menu entry itself to avoid recursion.
    items = [(label, fn) for key, (label, fn) in _ROW_SHORTCUTS.items() if key != "m"]
    while True:
        fresh = data.get_enrolment(eid)
        if fresh is None:
            print(f"  (enrolment #{eid} no longer exists)")
            return
        print(f"\n── Enrolment #{eid} · {fresh.student_id} "
              f"({fresh.academic_year}, {fresh.status}) ──")
        for i, (label, _fn) in enumerate(items, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("  Invalid selection.")
            continue
        items[int(choice) - 1][1](eid)


# ── Submenu dispatcher ──────────────────────────────────────────────

# Grouped menus keep 50+ actions navigable. Each tuple is (label, handler).
_w = requires_write   # write handlers: refused up front, flagged in menus

_CRUD_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All Enrolments", list_all),
    ("Filter Enrolments",   filter_enrolments),
    ("New Enrolment",       _w(new_enrolment)),
    ("View Enrolment",      view_enrolment),
    ("Edit Enrolment",      _w(edit_enrolment)),
    ("Delete Enrolment",    _w(delete_enrolment_flow)),
    ("Enrol a Student",     _w(enrol_from_student_profile)),
    ("Archived Enrolments", list_archived_enrolments),
    ("Restore Archived Enrolment", _w(restore_enrolment_flow)),
    ("Enrolment Change History", enrolment_audit_history),
]

_WORKFLOW_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bulk Enrol",              _w(bulk_enrol)),
    ("Progression Wizard",      _w(progression_wizard)),
    ("End-of-Year Rollover",    _w(end_of_year_rollover)),
    ("Re-enrol Student",        _w(reenrol_student)),
    ("Duplicate Enrolment",     _w(duplicate_enrolment)),
    ("Withdraw Enrolment",      _w(withdraw_enrolment)),
    ("Archive / Restore (soft-delete, not a withdrawal)", _w(soft_delete_toggle)),
    ("Transfer Enrolment (move to another learner)", _w(transfer_enrolment)),
    ("Undo Last Action",        _w(undo_last_action)),
    ("Reinstate a Withdrawn Enrolment", _w(reinstate_withdrawn)),
    ("Reopen a Completed Enrolment", _w(reopen_completed)),
    ("Rollover History",        rollover_history),
    ("Undo Rollover",           _w(undo_rollover_flow)),
    ("Record Year 12 Return Intention", _w(record_return_intention)),
    ("Year 12 Return Intentions Summary", return_intention_summary),
]

_BULK_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bulk Status Change",   _w(bulk_status_change)),
    ("Bulk Tutor Reassign",  _w(bulk_tutor_reassign)),
    ("Bulk Delete",          _w(bulk_delete)),
    ("Bulk Year 12 Return Intention", _w(bulk_return_intention)),
]

_SEARCH_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Search (ID / name)",       search_enrolments),
    ("Filter by Tutor Group",    filter_by_tutor_group),
    ("Filter by Date Range",     filter_by_date_range),
    ("Current Year",             quick_filter_current_year),
    ("Sort Enrolments",          sort_enrolments),
    ("Advanced Query",           advanced_query),
    ("Saved Filter Presets",     saved_filter_manager),
    ("Status Summary",           status_badges),
]

_REPORT_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Dashboard",                 enrolment_dashboard),
    ("Cohort Report",             cohort_report),
    ("Retention",                 retention_report),
    ("Tutor Group Roster",        tutor_group_roster),
    ("Withdrawal Analysis",       withdrawal_analysis),
    ("Year-on-Year Comparison",   year_on_year_comparison),
    ("Capacity Utilisation",      capacity_utilisation),
    ("Student Enrolment History", student_enrolment_history),
    ("Students Without Enrolment", students_without_enrolment),
    ("Duplicate Conflicts",       duplicate_conflicts),
    ("Enrolment Change History",  enrolment_audit_history),
]

_DATA_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Export CSV",           export_directory_csv),
    ("Export Progression",   export_progression_list),
    ("Export Enrolment PDF", export_enrolment_pdf),
    ("Export Roster PDF",    export_tutor_group_pdf),
    ("Import CSV",           _w(import_enrolments_csv)),
    ("Copy Enrolment",       copy_enrolment_details),
]

_ADMIN_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Academic Year Manager",     academic_year_manager),
    ("Current Year Group",        show_current_year_group),
    ("Reconcile Year Group",      sync_status_to_student_record),
    ("Per-record Context Menu",   context_menu),
    ("Keyboard Shortcuts",        keyboard_shortcuts_help),
]

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Records (CRUD)",     lambda: _submenu("Records", _CRUD_MENU)),
    ("Workflows",          lambda: _submenu("Workflows", _WORKFLOW_MENU)),
    ("Bulk Operations",    lambda: _submenu("Bulk Operations", _BULK_MENU)),
    ("Search & Filter",    lambda: _submenu("Search & Filter", _SEARCH_MENU)),
    ("Reports & Analytics", lambda: _submenu("Reports & Analytics", _REPORT_MENU)),
    ("Import / Export",    lambda: _submenu("Import / Export", _DATA_MENU)),
    ("Admin & Tools",      lambda: _submenu("Admin & Tools", _ADMIN_MENU)),
    ("Photo & ID Checks",  lambda: _submenu("Photo & ID Checks", __import__(
        "education_system.systems.sixth_form.interfaces.cli.admissions."
        "enrolments.identity_checks_cli", fromlist=["MENU"]).MENU)),
    ("ILR, Funding & Fees", lambda: _submenu("ILR, Funding & Fees", _marked(
        _lazy("enrolment_ilr_cli", "MENU")))),
    ("Enrolment Day & Agreements", lambda: _submenu(
        "Enrolment Day & Agreements", _marked(_lazy("enrolment_day_cli", "MENU")))),
    ("Course Changes, Capacity & Data Check", lambda: _submenu(
        "Course Changes, Capacity & Data Check",
        _marked(_lazy("enrolment_insights_cli", "COURSE_MENU")))),
    ("Targets & Reports", lambda: _submenu(
        "Targets & Reports", _marked(_lazy("enrolment_insights_cli", "REPORT_MENU")))),
]

#: Handlers in the lazily loaded menus that change enrolment records
#: (flagged for a read-only user, and refused up front). Fee rates and
#: charges are gated by finance / funding inside the domain instead.
_WRITE_HANDLERS = {
    "set_ilr_fields", "set_aim_outcome", "clear_aim_outcome", "cof_apply",
    "record_agreement", "withdraw_agreement", "correct_agreement",
    "change_course",
}


def _lazy(module: str, attr: str) -> list[tuple[str, Callable[[], None]]]:
    return getattr(__import__(
        "education_system.systems.sixth_form.interfaces.cli.admissions."
        f"enrolments.{module}", fromlist=[attr]), attr)


def _marked(entries: list[tuple[str, Callable[[], None]]]
            ) -> list[tuple[str, Callable[[], None]]]:
    return [(label, _w(fn) if fn.__name__ in _WRITE_HANDLERS else fn)
            for label, fn in entries]


def _submenu(title: str, entries: list[tuple[str, Callable[[], None]]]) -> None:
    """Render a categorised submenu and dispatch its handlers safely."""
    while True:
        print(f"\n── {title} ──")
        for i, (label, fn) in enumerate(entries, 1):
            print(f"  {i}) {_menu_label(label, fn)}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(entries)):
            print("  Invalid selection.")
            continue
        _, handler = entries[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except (PermissionError, ValueError) as e:
            # Refusals (no permission, a rule broken) are shown as they are.
            print(f"\n  ✗ {e}")
            _pause()
        except Exception as e:
            logger.exception("Enrolment CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def run() -> None:
    """Show the Enrolment submenu until the user picks Back."""
    while True:
        print("\n── Enrolment ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except (PermissionError, ValueError) as e:
            # Refusals (no permission, a rule broken) are shown as they are.
            print(f"\n  ✗ {e}")
            _pause()
        except Exception as e:
            logger.exception("Enrolment CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    """Run the enrolment submenu when the parent CLI hits "Enrolment".

    Returns True so the caller skips its stub message.
    """
    if label != "Enrolment":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Enrolment CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
