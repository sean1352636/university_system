"""Enrolment CLI: record workflows (withdraw, re-enrol, transfer, undo) and bulk/cohort operations."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    DEFAULT_STATUS,
    Enrolment,
    STATUSES,
    ValidationError,
    YEAR_GROUPS,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments._common import (
    _UNDO_STACK,
    _UserAbort,
    _collect_form,
    _default_academic_year,
    _enrolment_to_payload,
    _input,
    _next_academic_year,
    _pause,
    _pick_from,
    _pick_student,
    _pick_students_multi,
    _print_withdrawal,
    _prompt_academic_year,
    _prompt_ids,
    _prompt_start_date,
    _prompt_tutor_group,
    _prompt_withdrawal,
    _record_undo,
    _report_bulk,
    _resolve_enrolment,
    _show_checks,
    _undo_withdrawal,
    _writes_ok,
)

logger = logging.getLogger(__name__)



def undo_last_action() -> None:
    """Feature #42 — undo the most recent delete / status change this session."""
    print("\n═══ Undo ═══")
    if not _UNDO_STACK:
        print("  (nothing to undo)")
        _pause()
        return
    label, restore = _UNDO_STACK[-1]
    confirm = _input(f"Undo {label}? Type 'yes' to confirm", default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    _UNDO_STACK.pop()
    try:
        restore()
    except Exception as exc:
        logger.exception("Undo failed for: %s", label)
        print(f"  ✗ Could not undo: {exc}")
        _pause()
        return
    print(f"  ✓ Undid {label}")
    _pause()


# ════════════════════════════════════════════════════════════════════
# Record-level workflow actions (features 5, 6, 7, 41, 48)
# ════════════════════════════════════════════════════════════════════

def withdraw_enrolment(enrolment_id: int | None = None) -> None:
    """Feature #5 — withdraw a learner: last day in learning, ILR
    withdrawal reason and detail; their active learning aims are ended."""
    print("\n═══ Withdraw Enrolment ═══")
    if not _writes_ok():
        return
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    if e.status == "Withdrawn":
        print(f"  Enrolment #{e.enrolment_id} is already withdrawn "
              f"({e.withdrawal_date or '—'}, "
              f"{e.withdrawal_reason_label or 'no reason'}).")
        _pause()
        return
    if not e.is_live:
        print(f"  Enrolment #{e.enrolment_id} is "
              f"{'archived' if e.is_archived else e.status} — only an Enrolled "
              "or Pending enrolment can be withdrawn.")
        _pause()
        return
    print(f"  #{e.enrolment_id} {e.student_id} {e.academic_year} Year "
          f"{e.year_group} [{e.status}]")
    try:
        code, wd, detail, approved = _prompt_withdrawal()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    withdraw_with(e.enrolment_id, code=code, withdrawal_date=wd,
                  detail=detail, approved_by=approved)
    _pause()


def withdraw_with(eid: int, *, code: str, withdrawal_date: str,
                  detail: str | None, approved_by: str | None = None,
                  record_undo: bool = True) -> bool:
    """Withdraw one enrolment, print the result and put a reinstatement on
    the undo stack. Returns True when it was withdrawn."""
    try:
        res = data.withdraw_enrolment(eid, withdrawal_date=withdrawal_date,
                                      reason=code, detail=detail,
                                      approved_by=approved_by)
    except (ValueError, PermissionError) as exc:  # ValidationError, AccessDenied
        print(f"  ✗ #{eid}: {exc}")
        return False
    _print_withdrawal(res)
    if record_undo:
        _record_undo(f"withdrawal of #{eid} ({res.enrolment.student_id})",
                     lambda: _undo_withdrawal(eid, "Undo of a withdrawal"))
    return True

def soft_delete_toggle(enrolment_id: int | None = None) -> None:
    """Feature #41 — archive (soft-delete) an enrolment, or restore an
    archived one; the row and its id are kept either way."""
    print("\n═══ Archive / Restore (soft-delete — not a withdrawal) ═══")
    print("  Archiving hides a record entered by mistake from every list; it "
          "does NOT\n  withdraw the learner, end their aims or record an ILR "
          "reason (use Withdraw).")
    if not _writes_ok():
        return
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    try:
        if e.is_archived:
            if _input(f"Restore archived #{e.enrolment_id} to the lists? (y/n)",
                      default="y").lower().startswith("y"):
                data.restore_enrolment(e.enrolment_id)
                print(f"  ✓ #{e.enrolment_id} restored")
        else:
            if not _input(f"Archive #{e.enrolment_id} ({e.student_id}, "
                          f"{e.academic_year})? (y/n)",
                          default="n").lower().startswith("y"):
                print("  Cancelled.")
                _pause()
                return
            reason = _input("Reason for archiving", default="Entered by mistake")
            data.archive_enrolment(e.enrolment_id, reason=reason)
            _record_undo(f"archive of #{e.enrolment_id}",
                         lambda: data.restore_enrolment(e.enrolment_id))
            print(f"  ✓ #{e.enrolment_id} archived (hidden from lists)")
    except (ValueError, PermissionError) as exc:
        print(f"  ✗ {exc}")
    _pause()

def duplicate_enrolment(enrolment_id: int | None = None) -> None:
    """Feature #7 — create a new enrolment pre-filled from an existing one,
    rolled forward one academic year (and Year 12 → 13)."""
    print("\n═══ Duplicate Enrolment ═══")
    if not _writes_ok():
        return
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    yg = 13 if e.year_group == 12 else e.year_group
    try:
        payload = _collect_form(None, preselect_student=e.student_id,
                                preset_year=_next_academic_year(e.academic_year),
                                preset_year_group=yg)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _create_and_report(payload)


def reenrol_student() -> None:
    """Feature #6 — quick re-enrol: pick a student, defaulting to their next
    academic year and year group."""
    print("\n═══ Re-enrol Student ═══")
    if not _writes_ok():
        return
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    latest = data.current_enrolment(sid)
    if latest is not None:
        year = _next_academic_year(latest.academic_year)
        yg = 13 if latest.year_group == 12 else latest.year_group
    else:
        year, yg = _default_academic_year(), YEAR_GROUPS[0]
    try:
        payload = _collect_form(None, preselect_student=sid,
                                preset_year=year, preset_year_group=yg)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _create_and_report(payload)


def enrol_from_student_profile(student_id: str | None = None) -> None:
    """Feature #46 — deep-link equivalent: enrol a chosen student directly."""
    print("\n═══ Enrol Student ═══")
    if not _writes_ok():
        return
    try:
        sid = student_id or _pick_student()
        payload = _collect_form(None, preselect_student=sid)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _create_and_report(payload)


def _create_and_report(payload: dict[str, Any]) -> None:
    try:
        created = data.create_enrolment(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI create failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Created enrolment #{created.enrolment_id} for "
          f"{created.student_id} ({created.academic_year}, Year {created.year_group})")
    _show_checks(created.student_id, created.academic_year)
    _pause()


def transfer_enrolment(enrolment_id: int | None = None) -> None:
    """Feature #48 — move an enrolment entered against the wrong learner to
    the right one: the same row (id, history, withdrawal details) changes
    owner in one transaction, and that year's learning aims go with it."""
    print("\n═══ Transfer Enrolment (move to another learner) ═══")
    if not _writes_ok():
        return
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    from education_system.systems.sixth_form.domain.learners.students import (
        students as student_data,
    )
    src = student_data.get_student(e.student_id)
    print(f"  Moving #{e.enrolment_id} ({e.academic_year}, Year {e.year_group}, "
          f"{e.status}) from {e.student_id} "
          f"({src.full_name if src else 'unknown'}).")
    try:
        target = _pick_student(include_leavers=True)
        if target == e.student_id:
            print("  Same student — nothing to do.")
            _pause()
            return
        dst = student_data.get_student(target)
        print(f"\n  From: {e.student_id}  {src.full_name if src else '—'}"
              + (f"  DOB {src.date_of_birth}" if src and src.date_of_birth else ""))
        print(f"  To  : {target}  {dst.full_name if dst else '—'}"
              + (f"  DOB {dst.date_of_birth}" if dst and dst.date_of_birth else ""))
        print("  The learning aims that started in that year move with it.")
        reason = _input("Reason (required)", allow_empty=False)
        if _input("Move it? Type 'yes' to confirm", default="no").lower() != "yes":
            print("\n  Cancelled.")
            return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        res = data.transfer_enrolment(e.enrolment_id, target, reason=reason)
    except (ValueError, PermissionError) as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ Enrolment #{res.enrolment.enrolment_id} now belongs to {target} "
          f"({res.aims_moved} learning aim(s) moved with it)")
    _pause()


# ════════════════════════════════════════════════════════════════════
# Bulk / cohort operations (features 1, 2, 3, 4, 8, 40)
# ════════════════════════════════════════════════════════════════════

def bulk_enrol() -> None:
    """Feature #1 — enrol several students into one shared year/status."""
    print("\n═══ Bulk Enrol ═══")
    if not _writes_ok():
        return
    try:
        sids = _pick_students_multi()
        if not sids:
            print("  No students selected.")
            _pause()
            return
        print(f"\n  {len(sids)} student(s) selected. Shared details:")
        year = _prompt_academic_year(_default_academic_year())
        yg = _pick_from("Year group", [str(y) for y in YEAR_GROUPS],
                        default=str(YEAR_GROUPS[0]))
        tutor = _prompt_tutor_group(int(yg))
        start = _prompt_start_date(date.today().isoformat())
        status = _pick_from("Status", list(data.CREATE_STATUSES),
                            default=DEFAULT_STATUS)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok: list[str] = []
    fail: list[str] = []
    for sid in sids:
        try:
            data.create_enrolment({
                "student_id": sid, "academic_year": year, "year_group": yg,
                "tutor_group": tutor, "start_date": start, "status": status,
                "notes": None})
            ok.append(sid)
        except Exception as exc:
            fail.append(f"{sid}: {exc}")
    _report_bulk("Bulk enrol", ok, fail)


def progression_wizard() -> None:
    """Feature #2 — roll enrolled Year 12s forward into Year 13 next year
    (the rollover without completing Year 13); dry run first."""
    print("\n═══ Year 12 → 13 Progression Wizard ═══")
    _rollover(complete_year13=False, title="Progression")

def end_of_year_rollover() -> None:
    """Feature #8 — complete Year 13 leavers and progress Year 12 into 13,
    through enrolments.rollover: a dry run first, then the real run."""
    print("\n═══ End-of-Year Rollover ═══")
    _rollover(complete_year13=True, title="Rollover")


def _rollover(*, complete_year13: bool, title: str) -> None:
    if not _writes_ok():
        return
    try:
        src = _prompt_academic_year(_default_academic_year(), label="From year")
        tgt = _prompt_academic_year(data.next_academic_year(src), label="To year")
        try:
            summary = data.reintention_summary(src)
            print("\n  Year 12 return intentions for " + src + ": " + ", ".join(
                f"{k} {v}" for k, v in summary.items()))
        except Exception as exc:  # noqa: BLE001 — shown, not blocking
            print(f"  (return intentions not read: {exc})")
        require = _input("Only move up Year 12s who said they are Returning? "
                         "(y/n)", default="n").lower().startswith("y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    opts = dict(complete_year13=complete_year13, require_intention=require)
    try:
        plan = data.rollover(src, tgt, dry_run=True, **opts)
    except (ValueError, PermissionError) as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    _print_rollover(plan, dry_run=True)
    if not (plan.completed or plan.progressed):
        _pause()
        return
    if _input("Run it? Type 'yes' to confirm", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        res = data.rollover(src, tgt, **opts)
    except (ValueError, PermissionError) as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    _print_rollover(res, dry_run=False)
    if res.run_id is not None:
        print(f"\n  Rollover run #{res.run_id} — undo it from "
              "'Undo Rollover' if it was a mistake.")
    _report_bulk(title, [f"{s} (completed)" for s in res.completed]
                 + [f"{s} (progressed)" for s in res.progressed],
                 [f"{s}: {why}" for s, why in res.failed])


def _print_rollover(r: "data.RolloverResult", *, dry_run: bool) -> None:
    verb = "would be" if dry_run else "were"
    print(f"\n  {r.from_year} → {r.to_year}{' (dry run)' if dry_run else ''}:")
    print(f"    {len(r.completed)} Year 13 leaver(s) {verb} completed")
    print(f"    {len(r.progressed)} Year 12 learner(s) {verb} progressed")
    if r.skipped:
        print(f"    {len(r.skipped)} skipped:")
        for sid, why in r.skipped:
            print(f"      {sid}: {why}")
    for sid, why in r.failed:
        print(f"    ✗ {sid}: {why}")
    for p in r.aim_problems:
        print(f"    ✗ aim: {p}")


_BULK_TARGETS = (
    "Enrolled",
    "Pending",
    "Withdrawn — ILR reason, ends aims",
    "Completed — end of course, completes aims",
)


def bulk_status_change() -> None:
    """Feature #3 — set one status on many enrolments by ID, each through
    the route that status needs: Withdrawn through ``withdraw_enrolment``
    (one ILR reason, date and detail for all), Completed through
    ``complete_enrolment``, a withdrawn row back to Enrolled through
    ``reinstate_enrolment`` and a completed one through ``reopen_enrolment``.
    Undo reverses each the same way."""
    print("\n═══ Bulk Status Change ═══")
    if not _writes_ok():
        return
    try:
        ids = _prompt_ids("Enrolment IDs (comma/space separated)")
        if not ids:
            print("  No IDs given.")
            _pause()
            return
        target = _pick_from("New status", list(_BULK_TARGETS), default="Enrolled")
        new_status = target.split(" — ")[0]
        code = wd = detail = approved = reason = None
        if new_status == "Withdrawn":
            code, wd, detail, approved = _prompt_withdrawal()
        elif new_status == "Enrolled":
            reason = _input("Reason (needed to reinstate a withdrawn or reopen "
                            "a completed enrolment)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok: list[str] = []
    fail: list[str] = []
    done: list[tuple[str, Enrolment]] = []   # (how, prior) for undo
    for eid in ids:
        try:
            e = data.get_enrolment(eid)
            if e is None:
                fail.append(f"#{eid}: not found")
                continue
            if e.status == new_status:
                fail.append(f"#{eid}: already {new_status}")
                continue
            if new_status == "Withdrawn":
                res = data.withdraw_enrolment(eid, withdrawal_date=wd, reason=code,
                                              detail=detail, approved_by=approved)
                how = "withdrawn"
                extra = f", {len(res.aims_ended)} aim(s) ended" + (
                    ", student marked Left" if res.student_left else "")
                fail += [f"#{eid} aim: {p}" for p in res.aim_problems]
            elif new_status == "Completed":
                _out, problems = data.complete_enrolment(eid)
                how, extra = "completed", ""
                fail += [f"#{eid} aim: {p}" for p in problems]
            elif e.status == "Withdrawn":
                if not reason:
                    fail.append(f"#{eid}: withdrawn — a reason is needed to "
                                "reinstate it")
                    continue
                r = data.reinstate_enrolment(eid, reason=reason)
                how = "reinstated"
                extra = f", {len(r.aims_reopened)} aim(s) reopened"
                fail += [f"#{eid} aim: {p}" for p in r.aim_problems]
            elif e.status == "Completed":
                if not reason:
                    fail.append(f"#{eid}: completed — a reason is needed to "
                                "reopen it")
                    continue
                data.reopen_enrolment(eid, reason=reason)
                how, extra = "reopened", ""
            else:
                data.update_enrolment(eid, _enrolment_to_payload(e, status=new_status))
                how, extra = "updated", ""
            done.append((how, e))
            ok.append(f"#{eid} {how}{extra}")
        except Exception as exc:  # ValidationError / AccessDenied shown per row
            fail.append(f"#{eid}: {exc}")
    if done:
        def _restore(snap: list[tuple[str, Enrolment]] = done) -> None:
            for how, e in snap:
                eid = e.enrolment_id
                if how == "withdrawn":
                    _undo_withdrawal(eid, "Undo of a bulk status change")
                elif how == "completed":
                    data.reopen_enrolment(eid, reason="Undo of a bulk status change")
                elif how == "reinstated":
                    # Put the withdrawal back with its original date and reason.
                    data.withdraw_enrolment(
                        eid, withdrawal_date=e.withdrawal_date,
                        reason=e.withdrawal_reason or "98",
                        detail=(None if e.withdrawal_detail == data.RESTRICTED
                                else e.withdrawal_detail))
                elif how == "reopened":
                    data.complete_enrolment(eid, completed_on=e.completed_at,
                                            complete_aims=False)
                else:
                    data.update_enrolment(eid, _enrolment_to_payload(e))
        _record_undo(f"status change of {len(done)} enrolment(s)", _restore)
    for line in ok:
        print(f"    ✓ {line}")
    _report_bulk("Bulk status change", ok, fail)


def bulk_tutor_reassign() -> None:
    """Feature #4 — move many enrolments to a new tutor group."""
    print("\n═══ Bulk Tutor Reassign ═══")
    if not _writes_ok():
        return
    try:
        ids = _prompt_ids("Enrolment IDs (comma/space separated)")
        if not ids:
            print("  No IDs given.")
            _pause()
            return
        found = [e for e in (data.get_enrolment(i) for i in ids) if e is not None]
        years = {e.year_group for e in found}
        tutor = _prompt_tutor_group(years.pop() if len(years) == 1 else None) or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok: list[str] = []
    fail: list[str] = []
    priors: list[Enrolment] = []
    for eid in ids:
        try:
            e = data.get_enrolment(eid)
            if e is None:
                fail.append(f"#{eid}: not found")
                continue
            data.update_enrolment(eid, _enrolment_to_payload(e, tutor_group=tutor))
            priors.append(e)
            ok.append(f"#{eid}")
        except Exception as exc:
            fail.append(f"#{eid}: {exc}")
    if priors:
        def _restore(snap: list[Enrolment] = priors) -> None:
            for e in snap:
                data.update_enrolment(e.enrolment_id, _enrolment_to_payload(e))
        _record_undo(f"tutor reassign of {len(priors)} enrolment(s)", _restore)
    _report_bulk("Bulk tutor reassign", ok, fail)


def bulk_delete() -> None:
    """Feature #40 — guarded multi-delete requiring a typed confirmation."""
    print("\n═══ Bulk Delete (archive) ═══")
    if not _writes_ok():
        return
    try:
        ids = _prompt_ids("Enrolment IDs to delete (comma/space separated)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not ids:
        print("  No IDs given.")
        _pause()
        return
    typed = _input(f"This archives {len(ids)} enrolment(s) (restorable). "
                   "Type DELETE to confirm")
    if typed.strip().upper() != "DELETE":
        print("\n  Cancelled.")
        return
    snapshots = [data.get_enrolment(eid) for eid in ids]
    ok: list[str] = []
    fail: list[str] = []
    for eid in ids:
        try:
            if data.delete_enrolment(eid):
                ok.append(f"#{eid}")
            else:
                fail.append(f"#{eid}: not found")
        except Exception as exc:
            fail.append(f"#{eid}: {exc}")
    restorable = [e for e in snapshots if e is not None
                  and f"#{e.enrolment_id}" in ok]
    if restorable:
        def _restore(snap: list[Enrolment] = restorable) -> None:
            for e in snap:
                data.restore_enrolment(e.enrolment_id)
        _record_undo(f"bulk delete of {len(restorable)} enrolment(s)", _restore)
    _report_bulk("Bulk delete", ok, fail)
