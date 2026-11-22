"""CLI: onboarding archive, history, outstanding tasks and the learner's
photo / ID check."""

from __future__ import annotations

import datetime as _dt

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    identity_checks as idc,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.onboarding.onboarding_cli import (
    _REFUSED,
    _input,
    _pause,
    _pick_checklist,
    _pick_from,
    _pick_student,
    _print_checklists,
    _refused,
    _signed_in,
    _UserAbort,
    _writer,
    _yes_no,
)


def _names() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


# ── Archive ───────────────────────────────────────────────────────

def list_archived() -> None:
    print("\n═══ Archived Checklists ═══")
    rows = data.list_checklists(archived_only=True)
    _print_checklists(rows)
    for c in rows:
        print(f"    #{c.checklist_id}: archived {c.archived_at} by "
              f"{c.archived_by or '?'} — {c.archived_reason or ''}")
    _pause()


def restore_flow() -> None:
    print("\n═══ Restore Checklist ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist(archived=True)
        print(f"\n    Archived {c.archived_at} by {c.archived_by or '?'}: "
              f"{c.archived_reason or ''}")
        if not _yes_no(f"Restore checklist #{c.checklist_id}?",
                       default=False):
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = data.restore_checklist(c.checklist_id)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ Restored #{out.checklist_id} ({out.status})")
    _pause()


# ── History ───────────────────────────────────────────────────────

def history_flow() -> None:
    print("\n═══ Onboarding History ═══")
    try:
        scope = _pick_from("History for", ["A checklist", "A student"],
                           default="A checklist")
        if scope == "A checklist":
            c = _pick_checklist()
            rows = data.history(checklist_id=c.checklist_id)
            title = f"checklist #{c.checklist_id}"
        else:
            sid = _pick_student()
            rows = data.history(student_id=sid)
            title = sid
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  History for {title} (newest first):")
    if not rows:
        print("    (nothing recorded)")
    for r in rows:
        item = f" item #{r['item_id']}" if r.get("item_id") else ""
        print(f"    {r['changed_at']}  {r.get('changed_by') or '?':<14} "
              f"#{r['checklist_id']}{item}  {r['action']}: "
              f"{r.get('detail') or ''}")
    _pause()


# ── Outstanding tasks ─────────────────────────────────────────────

def _current_year() -> str:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enrolments,
    )
    return _enrolments.current_academic_year()


def outstanding_flow() -> None:
    print("\n═══ Outstanding Required Tasks ═══")
    try:
        year = _input("Academic year ('all' for every year)",
                      default=_current_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    year_filter = None if year.lower() == "all" else year
    today = _dt.date.today().isoformat()
    names = _names()
    rows = []
    for c in data.list_checklists(open_only=True, academic_year=year_filter):
        for it in data.list_items(checklist_id=c.checklist_id,
                                  required_only=True):
            if it.is_done:
                continue
            due = it.due_date or c.due_date
            rows.append((due, c, it))
    # Overdue first, then by due date (undated last).
    rows.sort(key=lambda r: (not (r[0] and r[0] < today),
                             r[0] is None, r[0] or "",
                             r[1].student_id, r[2].sort_order))
    print(f"\n  {'Due':<10}  {'Student':<10}  {'Name':<20}  "
          f"{'Chk':>4}  {'Status':<11}  Task")
    print("  " + "-" * 96)
    overdue = 0
    for due, c, it in rows:
        late = bool(due and due < today)
        overdue += late
        flag = "LATE " if late else ""
        extra = ""
        if it.awaiting_second_check:
            extra = "  [awaiting second check]"
        elif it.status == "Blocked" and it.blocked_reason:
            extra = f"  [blocked: {it.blocked_reason}]"
        print(f"  {due or '—':<10}  {c.student_id:<10}  "
              f"{names.get(c.student_id, '?')[:20]:<20}  "
              f"{c.checklist_id:>4}  {it.status:<11}  "
              f"{flag}{it.task_name}{extra}")
    print(f"\n  {len(rows)} open required task(s), {overdue} overdue"
          f" — {year_filter or 'all years'}.")
    _pause()


# ── Photo & ID check ──────────────────────────────────────────────

def _show_identity(sid: str) -> None:
    status = idc.check_status(sid)
    check = idc.get_check(sid)
    print(f"\n  Photo & ID — {sid}  {_names().get(sid, '')}")
    print(f"    Photo          : "
          + (f"on file (added {check.photo_added_at} by "
             f"{check.photo_added_by or '?'})"
             if check and check.has_photo else "none"))
    if check and check.id_checked:
        print(f"    ID document    : {check.id_document_type} "
              f"(…{check.id_number_last4 or '????'})")
        print(f"    Checked        : {check.id_checked_on} by "
              f"{check.id_checked_by or '?'}"
              + (f"  [{check.source}]" if check.source else ""))
        print(f"    Right to study : {check.right_to_study or '—'}")
        if check.visa_type or check.visa_expiry:
            print(f"    Visa           : {check.visa_type or '—'}, "
                  f"expires {check.visa_expiry or '—'}")
        if check.notes:
            print(f"    Notes          : {check.notes}")
    else:
        print("    ID document    : no ID check recorded")
    print("    Status         : "
          + ("complete" if status.is_complete
             else "outstanding — " + ", ".join(status.problems)))


def _record_id_check(sid: str) -> None:
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_details as _details,
    )
    doc = _pick_from("Document type", list(idc.ID_DOCUMENT_TYPES))
    number = _input("Document number (only the last 4 are kept)",
                    allow_empty=False)
    who = _input("Checked by", default=_signed_in() or "")
    on = _input("Checked on (YYYY-MM-DD)",
                default=_dt.date.today().isoformat())
    rts = _pick_from("Right to study", list(_details.RIGHT_TO_STUDY),
                     default=_details.RIGHT_TO_STUDY[0])
    visa_type = visa_expiry = ""
    if rts.startswith("Yes - visa"):
        visa_type = _input("Visa type")
        visa_expiry = _input("Visa expiry (YYYY-MM-DD)", allow_empty=False)
    notes = _input("Notes")
    try:
        idc.record_id_check(
            sid, document_type=doc, document_number=number,
            checked_by=who or None, checked_on=on or None,
            notes=notes or None, right_to_study=rts,
            visa_type=visa_type or None, visa_expiry=visa_expiry or None,
            source="onboarding CLI")
    except _REFUSED as e:
        print(f"\n  ✗ {e}")
        return
    print("\n  ✓ ID check recorded (the onboarding ID task is ticked "
          "where it applies)")


def _set_photo(sid: str) -> None:
    path = _input("Path to the photo file", allow_empty=False)
    try:
        idc.set_photo(sid, path, by=_signed_in())
    except _REFUSED as e:
        print(f"\n  ✗ {e}")
        return
    print("\n  ✓ Photo recorded")


def _show_id_history(sid: str) -> None:
    try:
        rows = idc.id_history(sid)
    except _REFUSED as e:
        print(f"\n  ✗ {e}")
        return
    if not rows:
        print("\n    No ID checks recorded.")
    for r in rows:
        print(f"    {r.get('id_checked_on') or '?'}  "
              f"{r.get('id_document_type') or '?'} "
              f"(…{r.get('id_number_last4') or '????'})  by "
              f"{r.get('id_checked_by') or '?'}  right to study: "
              f"{r.get('right_to_study') or '—'}")


def identity_flow() -> None:
    print("\n═══ Photo & ID Check ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _show_identity(sid)
    actions = ["Done"]
    if idc.can_see_immigration():
        actions.insert(0, "ID check history")
    if data.can_write():
        actions[:0] = ["Record an ID check", "Add / replace photo"]
    else:
        print("\n  You have read-only access: recording an ID check or a "
              "photo needs the admissions or student-management "
              "permission.")
    if actions == ["Done"]:
        return _pause()
    try:
        action = _pick_from("Action", actions, default="Done")
        if action == "Record an ID check":
            _record_id_check(sid)
            _show_identity(sid)
        elif action == "Add / replace photo":
            _set_photo(sid)
        elif action == "ID check history":
            _show_id_history(sid)
        else:
            return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _pause()


# ── Consent sync ──────────────────────────────────────────────────

def sync_consents_flow() -> None:
    print("\n═══ Sync Consent Tasks with GDPR Records ═══")
    if not _writer():
        return
    try:
        c = _pick_checklist()
        links = data.consent_links(c.checklist_id)
        if not links:
            print("    This checklist has no consent items.")
            return _pause()
        for link in links:
            print(f"    {link.item.task_name:<34} GDPR: {link.state:<9} "
                  f"task: {link.item.status}")
        if not _yes_no("Tick / re-open the consent tasks to match the GDPR "
                       "register?", default=True):
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        n = data.sync_consent_items(c.checklist_id)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  ✓ {n} consent task(s) updated")
    _pause()
