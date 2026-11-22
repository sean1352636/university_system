"""Record actions on enrolments: archive (the screens' "Delete"), restore,
withdraw with an ILR reason, the Withdrawn/Enrolled toggle and the
session undo stack.

Nothing here hard-deletes: "Delete" archives the row through
``enrolments.archive_enrolment`` and undo brings the same row back with
``restore_enrolment``.
"""

from __future__ import annotations

import logging
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    messagebox,
    simpledialog,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    Enrolment,
)
from education_system.systems.sixth_form.domain.admissions.enrolments.leaving import (
    UNKNOWN_REASON,
)

from .enrolment_common import (
    _UNDO_STACK,
    _record_undo,
    _report_bulk,
    back_to_directory,
    describe_error,
    show_error,
)
from .enrolment_withdraw_dialog import (
    WithdrawalChoice,
    WithdrawalDialog,
    reinstate_lines,
    withdrawal_lines,
)

logger = logging.getLogger(__name__)


_describe = describe_error


def _load(gui, enrolment_id: int) -> Enrolment | None:
    try:
        e = data.get_enrolment(enrolment_id)
    except Exception as exc:
        logger.exception("Failed to load enrolment %d", enrolment_id)
        messagebox.showerror("Error", f"Could not load enrolment: {exc}",
                             parent=gui.root)
        return None
    if e is None:
        messagebox.showerror("Not found",
                             f"No enrolment #{enrolment_id}", parent=gui.root)
    return e


def _restore_ids(ids: list[int]) -> None:
    problems: list[str] = []
    for eid in ids:
        try:
            data.restore_enrolment(eid)
        except Exception as exc:  # noqa: BLE001 — collected and raised once
            problems.append(f"#{eid}: {exc}")
    if problems:
        raise RuntimeError("; ".join(problems))


def _delete_with_confirm(gui, enrolment_id: int) -> None:
    """"Delete" archives the enrolment with a reason; Undo restores it."""
    e = _load(gui, enrolment_id)
    if e is None:
        return
    if e.is_archived:
        messagebox.showinfo(
            "Already archived",
            f"Enrolment #{enrolment_id} was archived {e.archived_at}"
            + (f" ({e.archived_reason})" if e.archived_reason else "")
            + ". Use Restore to bring it back.", parent=gui.root)
        return
    reason = simpledialog.askstring(
        "Delete (archive) enrolment",
        f"Enrolment #{e.enrolment_id} for {e.student_id} "
        f"({e.academic_year}, Year {e.year_group}) will be archived: it "
        "leaves every list but is kept, and can be restored.\n\n"
        "Reason:", parent=gui.root)
    if reason is None:
        logger.debug("GUI archive cancelled for enrolment #%d", enrolment_id)
        return
    try:
        archived = data.archive_enrolment(enrolment_id,
                                          reason=reason.strip() or "Deleted")
    except Exception as exc:
        logger.exception("GUI archive failed for enrolment %d", enrolment_id)
        messagebox.showerror("Error", f"Could not archive: {_describe(exc)}",
                             parent=gui.root)
        return
    if not archived:
        messagebox.showerror("Error", "The enrolment was not archived (it may "
                             "already be archived).", parent=gui.root)
        return
    _record_undo(f"archive of #{enrolment_id} ({e.student_id})",
                 lambda: _restore_ids([enrolment_id]))
    gui.status_var.set(f"Archived enrolment #{enrolment_id}")
    back_to_directory(gui)


def restore_enrolments(gui, enrolment_ids: list[int]) -> None:
    """Bring archived enrolments back (same rows, same ids)."""
    if not enrolment_ids:
        return
    ok: list[str] = []
    fail: list[str] = []
    for eid in enrolment_ids:
        try:
            e = data.get_enrolment(eid)
            if e is None:
                fail.append(f"#{eid}: not found")
                continue
            if not e.is_archived:
                fail.append(f"#{eid}: not archived")
                continue
            data.restore_enrolment(eid)
            ok.append(f"#{eid}")
        except Exception as exc:  # noqa: BLE001 — reported per row
            fail.append(f"#{eid}: {_describe(exc)}")
    _report_bulk(gui, "Restore", ok, fail)


# ── Withdrawal (ILR reason + date; ends learning aims) ──────────────

def _after(gui, after: Callable[[], None] | None) -> Callable[[], None]:
    return after or (lambda: back_to_directory(gui))


def _show_lines(gui, title: str, lines: list[str], *, warn: bool = False) -> None:
    (messagebox.showwarning if warn else messagebox.showinfo)(
        title, "\n".join(lines), parent=gui.root)


def _rewithdraw(prior: Enrolment) -> str:
    """Undo of a reinstatement: withdraw again with the original date,
    reason and detail."""
    detail = prior.withdrawal_detail
    if detail == data.RESTRICTED:
        detail = None
    res = data.withdraw_enrolment(
        prior.enrolment_id, withdrawal_date=prior.withdrawal_date,
        reason=prior.withdrawal_reason or UNKNOWN_REASON, detail=detail)
    return "\n".join(withdrawal_lines(res))


def _reinstate_undo(enrolment_id: int) -> Callable[[str], str]:
    def restore(reason: str) -> str:
        res = data.reinstate_enrolment(enrolment_id, reason=reason)
        return "\n".join(reinstate_lines(res))
    return restore


def do_withdraw(gui, enrolment_id: int, choice: WithdrawalChoice, *,
                parent=None, after: Callable[[], None] | None = None) -> bool:
    """Withdraw one enrolment with the dialog's answers; shows the result
    (or the error) and records the undo. True when it was withdrawn."""
    try:
        result = data.withdraw_enrolment(
            enrolment_id, withdrawal_date=choice.withdrawal_date,
            reason=choice.reason, detail=choice.detail,
            approved_by=choice.approved_by)
    except Exception as exc:  # ValidationError / AccessDenied / DB
        logger.warning("Withdraw failed for enrolment %d: %s", enrolment_id, exc)
        show_error(parent or gui.root, "Could not withdraw", exc)
        return False
    _show_lines(gui, "Withdrawn", withdrawal_lines(result),
                warn=bool(result.aim_problems))
    _record_undo(f"withdrawal of #{enrolment_id} (reinstates it and reopens "
                 "its aims)", _reinstate_undo(enrolment_id), needs_reason=True)
    gui.status_var.set(f"Withdrew enrolment #{enrolment_id}")
    _after(gui, after)()
    return True


def _confirm_and_withdraw(gui, enrolment_id: int,
                          after: Callable[[], None] | None = None
                          ) -> WithdrawalDialog | None:
    """Withdraw with an ILR reason code and the last day in learning
    (``enrolments.withdraw_enrolment``: the year's aims end, and the
    student record is marked Left when nothing live remains)."""
    e = _load(gui, enrolment_id)
    if e is None:
        return None
    if e.is_archived:
        messagebox.showinfo("Archived", f"Enrolment #{enrolment_id} is "
                            "archived; restore it first.", parent=gui.root)
        return None
    if e.status == "Withdrawn":
        messagebox.showinfo(
            "Already withdrawn",
            f"Enrolment #{enrolment_id} is already withdrawn"
            + (f" ({e.withdrawal_date}, {e.withdrawal_reason_label})"
               if e.withdrawal_date else "") + ". Use Reinstate to undo it.",
            parent=gui.root)
        return None
    if e.status == "Completed":
        messagebox.showinfo(
            "Completed", f"Enrolment #{enrolment_id} is Completed. Reopen it "
            "first if the learner is still in learning.", parent=gui.root)
        return None
    holder: dict[str, WithdrawalDialog] = {}
    dlg = WithdrawalDialog(
        gui.root, title=f"Withdraw enrolment #{enrolment_id}",
        heading=(f"{e.student_id} — {e.academic_year}, Year {e.year_group}"
                 + (f", started {e.start_date}" if e.start_date else "")),
        on_submit=lambda c: do_withdraw(gui, enrolment_id, c,
                                        parent=holder["d"].win, after=after))
    holder["d"] = dlg
    return dlg


def reinstate_with_reason(gui, enrolment_id: int,
                          after: Callable[[], None] | None = None,
                          reason: str | None = None) -> bool:
    """Undo a withdrawal (``reinstate_enrolment``): back to Enrolled, the
    aims it ended reopened, a learner marked Left put back on roll."""
    e = _load(gui, enrolment_id)
    if e is None:
        return False
    if e.status != "Withdrawn":
        messagebox.showinfo("Not withdrawn", f"Enrolment #{enrolment_id} is "
                            f"{e.status}; only a withdrawn enrolment can be "
                            "reinstated.", parent=gui.root)
        return False
    if reason is None:
        reason = simpledialog.askstring(
            "Reinstate enrolment",
            f"Reinstate #{enrolment_id} ({e.student_id}, {e.academic_year}, "
            f"Year {e.year_group}), withdrawn {e.withdrawal_date or '?'} "
            f"({e.withdrawal_reason_label or 'no reason'})?\n\nThe aims its "
            "withdrawal ended are reopened, and a student record marked Left "
            "is put back on roll.\n\nReason:", parent=gui.root)
        if reason is None:
            return False
    try:
        result = data.reinstate_enrolment(enrolment_id, reason=reason)
    except Exception as exc:
        show_error(gui.root, "Could not reinstate", exc)
        return False
    _show_lines(gui, "Reinstated", reinstate_lines(result),
                warn=bool(result.aim_problems))
    _record_undo(f"reinstatement of #{enrolment_id} (withdraws it again on "
                 f"{e.withdrawal_date or 'the same date'})",
                 lambda prior=e: _rewithdraw(prior))
    gui.status_var.set(f"Reinstated enrolment #{enrolment_id}")
    _after(gui, after)()
    return True


def reopen_with_reason(gui, enrolment_id: int,
                       after: Callable[[], None] | None = None,
                       reason: str | None = None) -> bool:
    """Completed → Enrolled (``reopen_enrolment``), e.g. completed by a
    rollover by mistake."""
    e = _load(gui, enrolment_id)
    if e is None:
        return False
    if e.status != "Completed":
        messagebox.showinfo("Not completed", f"Enrolment #{enrolment_id} is "
                            f"{e.status}; only a completed enrolment can be "
                            "reopened.", parent=gui.root)
        return False
    if reason is None:
        reason = simpledialog.askstring(
            "Reopen enrolment",
            f"Reopen #{enrolment_id} ({e.student_id}, {e.academic_year}, Year "
            f"{e.year_group}) as Enrolled? Learning aims are left as they "
            "are — reopen them in Learning Aims if they were completed too."
            "\n\nReason:", parent=gui.root)
        if reason is None:
            return False
    try:
        out = data.reopen_enrolment(enrolment_id, reason=reason)
    except Exception as exc:
        show_error(gui.root, "Could not reopen", exc)
        return False
    messagebox.showinfo("Reopened", f"Enrolment #{enrolment_id} is now "
                        f"{out.status}.", parent=gui.root)

    def _recomplete(prior: Enrolment = e) -> str:
        day = (prior.completed_at or "")[:10] or None
        _out, problems = data.complete_enrolment(prior.enrolment_id,
                                                 completed_on=day,
                                                 complete_aims=False)
        return "\n".join([f"#{prior.enrolment_id} completed again."]
                         + [f"  • {p}" for p in problems])
    _record_undo(f"reopening of #{enrolment_id}", _recomplete)
    gui.status_var.set(f"Reopened enrolment #{enrolment_id}")
    _after(gui, after)()
    return True


def _confirm_bulk_delete(gui, enrolment_ids: list[int]) -> None:
    """Guarded multi-archive: typed confirmation plus a reason; Undo
    restores the same rows."""
    if not enrolment_ids:
        return
    n = len(enrolment_ids)
    typed = simpledialog.askstring(
        "Delete (archive) selected enrolments",
        f"This will archive {n} enrolment(s): they leave every list but are "
        "kept and can be restored.\nType DELETE to confirm:",
        parent=gui.root)
    if (typed or "").strip().upper() != "DELETE":
        gui.status_var.set("Bulk delete cancelled")
        return
    reason = simpledialog.askstring("Reason", "Reason for archiving:",
                                    parent=gui.root)
    if reason is None:
        gui.status_var.set("Bulk delete cancelled")
        return
    ok: list[str] = []
    done: list[int] = []
    fail: list[str] = []
    for eid in enrolment_ids:
        try:
            if data.archive_enrolment(eid, reason=reason.strip() or "Deleted"):
                ok.append(f"#{eid}")
                done.append(eid)
            else:
                fail.append(f"#{eid}: not found or already archived")
        except Exception as exc:  # noqa: BLE001 — reported per row
            fail.append(f"#{eid}: {_describe(exc)}")
    if done:
        _record_undo(f"archive of {len(done)} enrolment(s)",
                     lambda ids=list(done): _restore_ids(ids))
    _report_bulk(gui, "Bulk archive", ok, fail)


def _soft_delete_toggle(gui, enrolment_id: int,
                       after: Callable[[], None] | None = None) -> None:
    """"Withdraw / Reinstate (toggle)": a withdrawn enrolment is
    reinstated (aims reopened); anything live opens the withdrawal form
    (ILR reason and date required). Archiving is the separate
    :func:`archive_toggle`, as in the CLI."""
    e = _load(gui, enrolment_id)
    if e is None:
        return
    if e.status == "Withdrawn":
        reinstate_with_reason(gui, enrolment_id, after)
    else:
        _confirm_and_withdraw(gui, enrolment_id, after)


def archive_toggle(gui, enrolment_id: int) -> None:
    """"Archive / Restore (toggle)" — the CLI's soft-delete toggle: archive
    a row (it leaves every list but is kept), or restore an archived one."""
    e = _load(gui, enrolment_id)
    if e is None:
        return
    if e.is_archived:
        restore_enrolments(gui, [enrolment_id])
    else:
        _delete_with_confirm(gui, enrolment_id)


def open_undo_last_action(gui) -> None:
    """Undo the most recent archive / withdrawal / status change this session."""
    if not _UNDO_STACK:
        messagebox.showinfo("Nothing to undo",
                            "No recent action to undo.", parent=gui.root)
        return
    entry = _UNDO_STACK[-1]
    if entry.needs_reason:
        reason = simpledialog.askstring(
            "Undo", f"Undo {entry.label}?\n\nReason (recorded in the "
            "enrolment history):", initialvalue="Undo: done in error",
            parent=gui.root)
        if reason is None:
            return
    elif not messagebox.askyesno("Undo", f"Undo {entry.label}?", parent=gui.root):
        return
    try:
        message = entry.restore(reason) if entry.needs_reason else entry.restore()
    except Exception as exc:
        logger.warning("Undo failed for %s: %s", entry.label, exc)
        show_error(gui.root, "Undo failed", exc)
        return
    _UNDO_STACK.pop()
    if message:
        messagebox.showinfo("Undone", message, parent=gui.root)
    gui.status_var.set(f"Undid {entry.label}")
    back_to_directory(gui)
