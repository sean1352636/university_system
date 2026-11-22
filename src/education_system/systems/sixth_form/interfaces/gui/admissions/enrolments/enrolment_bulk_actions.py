"""Bulk changes on the selected enrolments: status, tutor group and the
Year 12 return intention — each undoable from the directory's Undo.

A status change goes through the same lifecycle routes as a single one:
withdrawing through ``withdraw_enrolment`` (ILR reason, aims ended),
coming back from a withdrawal through ``reinstate_enrolment`` (aims
reopened), reopening a completed year through ``reopen_enrolment`` and
completing through ``complete_enrolment``. Undo reverses each row the same
way, so a re-withdrawal keeps the original withdrawal date and reason."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    messagebox,
    simpledialog,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    Enrolment,
    STATUSES,
)
from education_system.systems.sixth_form.domain.admissions.enrolments.leaving import (
    UNKNOWN_REASON,
)

from .enrolment_common import (
    _choose_from,
    _enrolment_to_payload,
    _record_undo,
    _report_bulk,
    describe_error,
)
from .enrolment_pickers import tutor_group_names
from .enrolment_withdraw_dialog import WithdrawalChoice, WithdrawalDialog

logger = logging.getLogger(__name__)


@dataclass
class BulkOutcome:
    ok: list[str] = field(default_factory=list)
    fail: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    #: (description, reverse(reason) -> note) per changed row.
    undo: list[tuple[str, Callable[[str | None], str | None]]] = field(
        default_factory=list)
    undo_needs_reason: bool = False


# ── Status ──────────────────────────────────────────────────────────

def _rewithdraw(prior: Enrolment) -> Callable[[str | None], str | None]:
    def rev(_reason: str | None) -> str | None:
        detail = None if prior.withdrawal_detail == data.RESTRICTED \
            else prior.withdrawal_detail
        res = data.withdraw_enrolment(
            prior.enrolment_id, withdrawal_date=prior.withdrawal_date,
            reason=prior.withdrawal_reason or UNKNOWN_REASON, detail=detail)
        return "; ".join(res.aim_problems) or None
    return rev


def _recomplete(prior: Enrolment) -> Callable[[str | None], str | None]:
    def rev(_reason: str | None) -> str | None:
        _out, problems = data.complete_enrolment(
            prior.enrolment_id, completed_on=(prior.completed_at or "")[:10] or None,
            complete_aims=False)
        return "; ".join(problems) or None
    return rev


def _reinstate(eid: int) -> Callable[[str | None], str | None]:
    def rev(reason: str | None) -> str | None:
        res = data.reinstate_enrolment(eid, reason=reason or "Bulk change undone")
        return "; ".join(res.aim_problems) or None
    return rev


def _reopen(eid: int) -> Callable[[str | None], str | None]:
    def rev(reason: str | None) -> str | None:
        data.reopen_enrolment(eid, reason=reason or "Bulk change undone")
        return None
    return rev


def _reupdate(prior: Enrolment) -> Callable[[str | None], str | None]:
    def rev(_reason: str | None) -> str | None:
        data.update_enrolment(prior.enrolment_id, _enrolment_to_payload(prior))
        return None
    return rev


def apply_bulk_status(enrolment_ids: list[int], target: str, *,
                      withdrawal: WithdrawalChoice | None = None,
                      reason: str | None = None) -> BulkOutcome:
    """Move each enrolment to ``target`` by the route its current status
    needs. ``withdrawal`` is required for Withdrawn; ``reason`` for any
    reinstatement or reopening (Enrolled from Withdrawn / Completed)."""
    out = BulkOutcome()
    for eid in enrolment_ids:
        try:
            e = data.get_enrolment(eid)
            if e is None:
                out.fail.append(f"#{eid}: not found")
                continue
            tag = f"#{eid} {e.student_id}"
            if e.is_archived:
                out.fail.append(f"{tag}: archived — restore it first")
                continue
            if e.status == target:
                out.notes.append(f"{tag}: already {target}")
                continue
            if target == "Withdrawn":
                if not e.is_live:
                    out.fail.append(f"{tag}: {e.status} — only an Enrolled or "
                                    "Pending enrolment can be withdrawn")
                    continue
                assert withdrawal is not None
                res = data.withdraw_enrolment(
                    eid, withdrawal_date=withdrawal.withdrawal_date,
                    reason=withdrawal.reason, detail=withdrawal.detail,
                    approved_by=withdrawal.approved_by)
                out.notes.append(f"{tag}: {len(res.aims_ended)} aim(s) ended"
                                 + ("; student marked Left" if res.student_left else ""))
                out.notes += [f"{tag} aim: {p}" for p in res.aim_problems]
                out.undo.append((f"reinstate {tag}", _reinstate(eid)))
                out.undo_needs_reason = True
            elif e.status == "Withdrawn":
                if target != "Enrolled":
                    out.fail.append(f"{tag}: withdrawn — reinstate it (status "
                                    "Enrolled) first")
                    continue
                res = data.reinstate_enrolment(eid, reason=reason or "")
                out.notes.append(f"{tag}: reinstated, {len(res.aims_reopened)} "
                                 "aim(s) reopened"
                                 + ("; student back on roll"
                                    if res.student_reinstated else ""))
                out.notes += [f"{tag} aim: {p}" for p in res.aim_problems]
                out.undo.append((f"withdraw {tag} again", _rewithdraw(e)))
            elif e.status == "Completed":
                if target != "Enrolled":
                    out.fail.append(f"{tag}: completed — reopen it (status "
                                    "Enrolled) first")
                    continue
                data.reopen_enrolment(eid, reason=reason or "")
                out.undo.append((f"complete {tag} again", _recomplete(e)))
            elif target == "Completed":
                if e.status != "Enrolled":
                    out.fail.append(f"{tag}: {e.status} — only an Enrolled "
                                    "enrolment can be completed")
                    continue
                _done, problems = data.complete_enrolment(eid)
                out.notes += [f"{tag} aim: {p}" for p in problems]
                out.undo.append((f"reopen {tag}", _reopen(eid)))
                out.undo_needs_reason = True
            else:
                data.update_enrolment(eid, _enrolment_to_payload(e, status=target))
                out.undo.append((f"put {tag} back to {e.status}", _reupdate(e)))
            out.ok.append(tag)
        except Exception as exc:  # noqa: BLE001 — reported per row
            out.fail.append(f"#{eid}: {describe_error(exc)}")
    return out


def _record_bulk_undo(label: str, outcome: BulkOutcome) -> None:
    if not outcome.undo:
        return
    steps = list(reversed(outcome.undo))

    def restore(reason: str | None = None) -> str:
        problems: list[str] = []
        done = 0
        for what, rev in steps:
            try:
                note = rev(reason)
                done += 1
                if note:
                    problems.append(f"{what}: {note}")
            except Exception as exc:  # noqa: BLE001 — reported per row
                problems.append(f"{what}: {describe_error(exc)}")
        lines = [f"{done} of {len(steps)} change(s) undone."]
        if problems:
            lines += ["", *problems[:20]]
        return "\n".join(lines)

    _record_undo(f"{label} of {len(steps)} enrolment(s)", restore,
                 needs_reason=outcome.undo_needs_reason)


def finish_bulk_status(gui, enrolment_ids: list[int], target: str, *,
                       withdrawal: WithdrawalChoice | None = None,
                       reason: str | None = None) -> BulkOutcome:
    outcome = apply_bulk_status(enrolment_ids, target, withdrawal=withdrawal,
                                reason=reason)
    _record_bulk_undo("status change", outcome)
    _report_bulk(gui, "Bulk status change", outcome.ok, outcome.fail,
                 outcome.notes)
    return outcome


def open_bulk_status_change(gui, enrolment_ids: list[int]) -> None:
    """Feature #3 — set one status on many selected enrolments."""
    if not enrolment_ids:
        return
    new_status = _choose_from(
        gui, "Set Status",
        f"New status for {len(enrolment_ids)} enrolment(s):\n"
        "(Withdrawn asks for the ILR reason; Enrolled reinstates withdrawn "
        "rows and reopens completed ones, with a reason.)",
        list(STATUSES), "Enrolled")
    if new_status is None:
        return
    if new_status == "Withdrawn":
        WithdrawalDialog(
            gui.root, title="Withdraw selected enrolments",
            heading=f"Withdraw {len(enrolment_ids)} enrolment(s)",
            on_submit=lambda c: (finish_bulk_status(
                gui, enrolment_ids, "Withdrawn", withdrawal=c), True)[1])
        return
    reason = None
    if new_status == "Enrolled":
        rows = [data.get_enrolment(i) for i in enrolment_ids]
        if any(r is not None and r.status in ("Withdrawn", "Completed")
               for r in rows):
            reason = simpledialog.askstring(
                "Reason", "Some selected enrolments are withdrawn or completed "
                "and will be reinstated / reopened.\n\nReason:", parent=gui.root)
            if reason is None:
                return
    finish_bulk_status(gui, enrolment_ids, new_status, reason=reason)


# ── Tutor group ─────────────────────────────────────────────────────

def apply_bulk_tutor(enrolment_ids: list[int], tutor: str | None) -> BulkOutcome:
    out = BulkOutcome()
    for eid in enrolment_ids:
        try:
            e = data.get_enrolment(eid)
            if e is None:
                out.fail.append(f"#{eid}: not found")
                continue
            if (e.tutor_group or None) == tutor:
                out.notes.append(f"#{eid}: already {tutor or 'no group'}")
                continue
            data.update_enrolment(eid, _enrolment_to_payload(e, tutor_group=tutor))
            out.ok.append(f"#{eid}")

            def rev(_r, eid=eid, prior=e.tutor_group) -> str | None:
                cur = data.get_enrolment(eid)
                if cur is None:
                    return "no longer exists"
                data.update_enrolment(eid, _enrolment_to_payload(cur, tutor_group=prior))
                return None
            out.undo.append((f"#{eid} back to {e.tutor_group or 'no group'}", rev))
        except Exception as exc:  # noqa: BLE001 — reported per row
            out.fail.append(f"#{eid}: {describe_error(exc)}")
    return out


def open_bulk_tutor_reassign(gui, enrolment_ids: list[int]) -> None:
    """Feature #4 — move many selected enrolments to a new tutor group
    (a real group of their year once tutor groups are set up)."""
    if not enrolment_ids:
        return
    rows = [r for r in (data.get_enrolment(i) for i in enrolment_ids) if r]
    years = {r.year_group for r in rows}
    exist, names = tutor_group_names(years.pop() if len(years) == 1 else None)
    if exist:
        picked = _choose_from(
            gui, "Reassign Tutor Group",
            f"New tutor group for {len(enrolment_ids)} enrolment(s):",
            ["(none)", *names], names[0] if names else "(none)")
        if picked is None:
            return
        tutor = None if picked == "(none)" else picked
    else:
        new_tg = simpledialog.askstring(
            "Reassign Tutor Group",
            f"New tutor group for {len(enrolment_ids)} enrolment(s):\n"
            "(No tutor groups are set up yet, so any name is kept.)",
            parent=gui.root)
        if new_tg is None:
            return
        tutor = new_tg.strip() or None
    outcome = apply_bulk_tutor(enrolment_ids, tutor)
    _record_bulk_undo("tutor reassignment", outcome)
    _report_bulk(gui, "Bulk tutor reassign", outcome.ok, outcome.fail, outcome.notes)


# ── Year 12 return intention ────────────────────────────────────────

def apply_bulk_intention(enrolment_ids: list[int], intention: str | None,
                         note: str | None = None) -> BulkOutcome:
    out = BulkOutcome()
    for eid in enrolment_ids:
        try:
            e = data.get_enrolment(eid)
            if e is None:
                out.fail.append(f"#{eid}: not found")
                continue
            data.set_return_intention(eid, intention, note=note)
            out.ok.append(f"#{eid}")
            if e.year_group != 12:
                out.notes.append(f"#{eid}: recorded, but this is a Year "
                                 f"{e.year_group} enrolment")

            def rev(_r, eid=eid, was=e.return_intention,
                    was_note=e.return_intention_note) -> str | None:
                data.set_return_intention(eid, was, note=was_note)
                return None
            out.undo.append((f"#{eid} back to {e.return_intention or 'unanswered'}",
                             rev))
        except Exception as exc:  # noqa: BLE001 — reported per row
            out.fail.append(f"#{eid}: {describe_error(exc)}")
    return out


def open_bulk_return_intention(gui, enrolment_ids: list[int],
                               after: Callable[[], None] | None = None) -> None:
    """Record "coming back for Year 13?" for the selected enrolments."""
    if not enrolment_ids:
        return
    picked = _choose_from(
        gui, "Return intention",
        f"Year 12 → 13 return intention for {len(enrolment_ids)} enrolment(s):",
        [*data.RETURN_INTENTIONS, "(clear)"], data.RETURN_INTENTIONS[0])
    if picked is None:
        return
    note = simpledialog.askstring("Return intention", "Note (optional):",
                                  parent=gui.root)
    if note is None:
        return
    outcome = apply_bulk_intention(
        enrolment_ids, None if picked == "(clear)" else picked, note)
    _record_bulk_undo("return intention change", outcome)
    if after is None:
        _report_bulk(gui, "Return intention", outcome.ok, outcome.fail,
                     outcome.notes)
        return
    msg = f"{len(outcome.ok)} recorded, {len(outcome.fail)} failed."
    if outcome.fail or outcome.notes:
        msg += "\n\n" + "\n".join((outcome.fail + outcome.notes)[:20])
    (messagebox.showwarning if outcome.fail else messagebox.showinfo)(
        "Return intention", msg, parent=gui.root)
    after()
