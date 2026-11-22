"""Safe applicant record actions shared by the admissions screens.

Every button that changes an applicant goes through here so the domain
rules are respected the same way everywhere: permissions are checked up
front (buttons disabled when the signed-in person cannot use them), and
every refusal — ``AccessDenied``, ``ValidationError`` or anything else —
is shown, never swallowed.

Covers delete → archive, archive / restore, merge, reopen, withdraw /
decline with a reason, defer, offers that hit a full programme, and the
two-person GDPR erasure.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Iterable

from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
    simpledialog,
)
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)

logger = logging.getLogger(__name__)


# ── Permissions ────────────────────────────────────────────────────

def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def can(capability: str) -> bool:
    """Whether the signed-in person holds *capability* (never raises)."""
    try:
        return bool(_access().current().can(capability))
    except Exception:  # noqa: BLE001 — no principal = no permission
        return False


def can_admissions() -> bool:
    return can(_access().ADMISSIONS)


def can_convert() -> bool:
    a = _access()
    return can(a.ADMISSIONS) and can(a.STUDENTS_MANAGE)


def can_govern() -> bool:
    return can(_access().GOVERNANCE)


def can_area(area: str) -> bool:
    """``send`` / ``medical`` / ``safeguarding`` capability."""
    a = _access()
    cap = {"send": a.SEND, "medical": a.MEDICAL,
           "safeguarding": a.SAFEGUARDING}.get(area)
    return bool(cap) and can(cap)


def username() -> str | None:
    try:
        return _access().current().username or None
    except Exception:  # noqa: BLE001
        return None


def gate(widget: Any, allowed: bool) -> Any:
    """Disable *widget* (kept visible, in place) when not *allowed*."""
    try:
        widget.state(["!disabled"] if allowed else ["disabled"])
    except (AttributeError, tk.TclError):
        try:
            widget.configure(state="normal" if allowed else "disabled")
        except tk.TclError:
            pass
    return widget


def gate_menu(menu: tk.Menu, label: str, allowed: bool) -> None:
    try:
        menu.entryconfigure(label, state="normal" if allowed else "disabled")
    except tk.TclError:
        pass


# ── Errors ─────────────────────────────────────────────────────────

def describe(exc: BaseException) -> str:
    if isinstance(exc, _access().AccessDenied):
        return f"You do not have permission for this.\n\n{exc}"
    return str(exc) or exc.__class__.__name__


def show_error(parent: tk.Misc | None, title: str, exc: BaseException) -> None:
    if not isinstance(exc, (ValueError, PermissionError)):
        logger.exception("%s failed", title, exc_info=exc)
    messagebox.showerror(title, describe(exc), parent=_top(parent))


def attempt(parent: tk.Misc | None, title: str, fn: Callable[..., Any],
            *args: Any, **kwargs: Any) -> tuple[bool, Any]:
    """Run *fn*; on any failure show it and return ``(False, None)``."""
    try:
        return True, fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 — every failure is shown
        show_error(parent, title, e)
        return False, None


def run_each(ids: Iterable[str], fn: Callable[[str], Any]
             ) -> tuple[list[str], list[str]]:
    """Apply *fn* to each id; returns (done, failures) with reasons."""
    done, failed = [], []
    for aid in ids:
        try:
            fn(aid)
            done.append(aid)
        except Exception as e:  # noqa: BLE001 — collected and reported
            failed.append(f"{aid}: {describe(e).splitlines()[-1]}")
    return done, failed


def report(parent: tk.Misc | None, title: str, done: list[str],
           failed: list[str], verb: str = "Updated") -> None:
    msg = f"{verb} {len(done)} applicant(s)."
    if failed:
        msg += f"\n\n{len(failed)} could not be changed:\n" + "\n".join(
            failed[:20])
        if len(failed) > 20:
            msg += f"\n…and {len(failed) - 20} more."
        messagebox.showwarning(title, msg, parent=_top(parent))
    else:
        messagebox.showinfo(title, msg, parent=_top(parent))


def _top(parent: tk.Misc | None) -> tk.Misc | None:
    try:
        return parent.winfo_toplevel() if parent is not None else None
    except tk.TclError:
        return None


# ── Small modals ───────────────────────────────────────────────────

def ask_text(parent: tk.Misc, title: str, prompt: str, *,
             initial: str = "", required: bool = True) -> str | None:
    """A line of text; None on cancel. *required* re-asks on blank."""
    while True:
        v = simpledialog.askstring(title, prompt, initialvalue=initial,
                                   parent=_top(parent))
        if v is None:
            return None
        v = v.strip()
        if v or not required:
            return v
        messagebox.showinfo(title, "This needs an answer (or Cancel).",
                            parent=_top(parent))


def ask_reason(parent: tk.Misc, title: str,
               prompt: str = "Reason (recorded on the timeline):"
               ) -> str | None:
    return ask_text(parent, title, prompt, required=True)


def pick(parent: tk.Misc, title: str, label: str, choices: list[str], *,
         initial: str | None = None, width: int = 44,
         notes_label: str | None = None) -> tuple[str, str] | None:
    """Choose one of *choices* (plus optional notes). Returns
    ``(choice, notes)`` or None when cancelled / nothing to choose."""
    if not choices:
        messagebox.showinfo(title, "There is nothing to choose from.",
                            parent=_top(parent))
        return None
    win = make_toplevel(_top(parent))
    win.title(title)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=label).grid(row=0, column=0, sticky="e", padx=4)
    cb = ttk.Combobox(frm, values=choices, state="readonly", width=width)
    cb.set(initial if initial in choices else choices[0])
    cb.grid(row=0, column=1, sticky="w", padx=4, pady=4)
    notes = None
    if notes_label:
        ttk.Label(frm, text=notes_label).grid(row=1, column=0, sticky="ne",
                                              padx=4)
        notes = tk.Text(frm, width=width, height=3, wrap="word")
        notes.grid(row=1, column=1, sticky="w", padx=4, pady=4)
    out: dict[str, tuple[str, str]] = {}

    def ok() -> None:
        out["v"] = (cb.get(), notes.get("1.0", "end").strip() if notes
                    else "")
        win.destroy()

    bar = ttk.Frame(frm)
    bar.grid(row=2, column=0, columnspan=2, pady=(10, 0))
    ttk.Button(bar, text="OK", command=ok).pack(side="left")
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left",
                                                            padx=8)
    win.bind("<Escape>", lambda _e: win.destroy())
    win.wait_window()
    return out.get("v")


def choose_action(parent: tk.Misc, title: str, message: str,
                  buttons: list[str]) -> str | None:
    """Message with one button per choice (plus Cancel); returns the
    chosen button text or None."""
    win = make_toplevel(_top(parent))
    win.title(title)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=14)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=message, wraplength=520, justify="left").pack(
        anchor="w", pady=(0, 12))
    bar = ttk.Frame(frm)
    bar.pack(fill="x")
    out: dict[str, str] = {}

    def choose(b: str) -> None:
        out["v"] = b
        win.destroy()

    for b in buttons:
        ttk.Button(bar, text=b, command=lambda b=b: choose(b)).pack(
            side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    win.bind("<Escape>", lambda _e: win.destroy())
    win.wait_window()
    return out.get("v")


# ── Delete / archive / restore ─────────────────────────────────────

def delete_or_archive(parent: tk.Misc, ids: list[str],
                      on_done: Callable[[], None]) -> None:
    """Delete applicants entered by mistake; anything with history
    (HasHistory) is offered for archiving instead, with a reason."""
    if not ids:
        messagebox.showinfo("Delete", "Select one or more applicants first.",
                            parent=_top(parent))
        return
    noun = (f"{len(ids)} applicants" if len(ids) > 1
            else f"applicant {ids[0]}")
    if not messagebox.askyesno(
            "Delete",
            f"Delete {noun}?\n\nOnly an application that has not progressed "
            "can be deleted. Anything further along will be offered for "
            "archiving instead, which keeps its history.",
            parent=_top(parent)):
        return
    deleted, history, failed = [], [], []
    for aid in ids:
        try:
            data.delete_applicant(aid)
            deleted.append(aid)
        except data.HasHistory as e:
            history.append((aid, str(e)))
        except Exception as e:  # noqa: BLE001 — reported below
            failed.append(f"{aid}: {describe(e).splitlines()[-1]}")
    archived: list[str] = []
    if history:
        lines = "\n".join(f"  {aid}: {why}" for aid, why in history[:12])
        if messagebox.askyesno(
                "Archive instead?",
                f"{len(history)} applicant(s) cannot be deleted because "
                f"they have history:\n\n{lines}\n\nArchive them instead? "
                "Archived records are hidden from the lists and can be "
                "restored.", parent=_top(parent)):
            reason = ask_reason(parent, "Archive",
                                "Reason for archiving:")
            if reason:
                done, bad = run_each(
                    [aid for aid, _w in history],
                    lambda aid: _safety().archive_applicant(aid,
                                                            reason=reason))
                archived += done
                failed += bad
    on_done()
    msg = []
    if deleted:
        msg.append(f"Deleted {len(deleted)}: {', '.join(deleted)}")
    if archived:
        msg.append(f"Archived {len(archived)}: {', '.join(archived)}")
    if failed:
        msg.append("Failed:\n" + "\n".join(failed))
    if msg:
        (messagebox.showwarning if failed else messagebox.showinfo)(
            "Delete", "\n\n".join(msg), parent=_top(parent))


def _safety():
    from education_system.systems.sixth_form.domain.admissions import (
        record_safety,
    )
    return record_safety


def archive(parent: tk.Misc, ids: list[str],
            on_done: Callable[[], None]) -> None:
    if not ids:
        messagebox.showinfo("Archive", "Select one or more applicants first.",
                            parent=_top(parent))
        return
    reason = ask_reason(parent, "Archive",
                        f"Reason for archiving {len(ids)} applicant(s):")
    if not reason:
        return
    done, failed = run_each(
        ids, lambda aid: _safety().archive_applicant(aid, reason=reason))
    on_done()
    report(parent, "Archive", done, failed, verb="Archived")


def restore(parent: tk.Misc, ids: list[str],
            on_done: Callable[[], None]) -> None:
    if not ids:
        messagebox.showinfo("Restore", "Select one or more archived "
                            "applicants first (tick 'Show archived').",
                            parent=_top(parent))
        return
    done, failed = run_each(ids, _safety().restore_applicant)
    on_done()
    report(parent, "Restore", done, failed, verb="Restored")


# ── Merge ──────────────────────────────────────────────────────────

def merge(parent: tk.Misc, keep_id: str, dup_id: str,
          on_done: Callable[[], None]) -> bool:
    keep, dup = data.get_applicant(keep_id), data.get_applicant(dup_id)
    if keep is None or dup is None:
        messagebox.showerror("Merge", "Both applicants must exist.",
                             parent=_top(parent))
        return False
    if not messagebox.askyesno(
            "Merge duplicates",
            f"Keep {keep.applicant_id} ({keep.full_name}) and merge "
            f"{dup.applicant_id} ({dup.full_name}) into it?\n\n"
            "Blank fields on the kept record are filled from the duplicate "
            "and its notes, events, documents, choices and other records "
            "move across. Nothing is deleted: the duplicate is archived as "
            "'merged into' the kept record.", parent=_top(parent)):
        return False
    reason = ask_text(parent, "Merge", "Reason (optional):", required=False)
    if reason is None:
        return False
    ok, res = attempt(parent, "Merge", _safety().merge_applicants,
                      keep.applicant_id, dup.applicant_id,
                      reason=reason or None)
    on_done()
    if not ok:
        return False
    lines = [f"Merged {res.duplicate} into {res.kept}.", ""]
    lines.append("Fields filled: " + (", ".join(res.filled) or "none"))
    if res.moved:
        lines.append("Moved: " + ", ".join(
            f"{_table_label(t)} {n}" for t, n in res.moved.items()))
    if res.left_on_duplicate:
        lines.append("Left on the duplicate (the kept record already had "
                     "the same): " + ", ".join(
                         f"{_table_label(t)} {n}"
                         for t, n in res.left_on_duplicate.items()))
    messagebox.showinfo("Merge", "\n".join(lines), parent=_top(parent))
    return True


def _table_label(table: str) -> str:
    return table.replace("admissions_", "").replace("_", " ")


def merge_dialog(parent: tk.Misc, selected: list[data.Applicant],
                 on_done: Callable[[], None]) -> None:
    """One selected: search its duplicates; two: merge the second into
    the first."""
    if len(selected) == 1:
        a = selected[0]
        dupes = [d for d in data.find_duplicates(
            email=a.email, first_name=a.first_name, last_name=a.last_name,
            dob=a.dob, exclude_id=a.applicant_id) if not d.is_archived]
        if not dupes:
            messagebox.showinfo(
                "Merge duplicates",
                f"No potential duplicates found for {a.applicant_id}.",
                parent=_top(parent))
            return
        labels = [f"{d.applicant_id} — {d.full_name} — "
                  f"{d.email or 'no email'} ({d.status})" for d in dupes]
        got = pick(parent, "Merge duplicates",
                   f"Merge which record into {a.applicant_id}?", labels,
                   width=60)
        if got:
            merge(parent, a.applicant_id,
                  dupes[labels.index(got[0])].applicant_id, on_done)
        return
    if len(selected) == 2:
        merge(parent, selected[0].applicant_id, selected[1].applicant_id,
              on_done)
        return
    messagebox.showinfo(
        "Merge duplicates",
        "Select one applicant to search for its duplicates, or exactly two "
        "applicants to merge the second into the first.",
        parent=_top(parent))


# ── Status workflow ────────────────────────────────────────────────

def reopen(parent: tk.Misc, aid: str, on_done: Callable[[], None]) -> bool:
    reason = ask_reason(parent, "Reopen application",
                        "Why is this application being reopened?")
    if not reason:
        return False
    ok, _ = attempt(parent, "Reopen", data.reopen_application, aid,
                    reason=reason)
    on_done()
    return ok


def withdraw_or_decline(parent: tk.Misc, ids: list[str], *, decline: bool,
                        on_done: Callable[[], None]) -> None:
    title = "Decline offer" if decline else "Withdraw"
    if not ids:
        messagebox.showinfo(title, "Select one or more applicants first.",
                            parent=_top(parent))
        return
    got = pick(parent, title, "Reason:", list(data.WITHDRAWAL_REASONS),
               width=52,
               notes_label=None if decline else "Notes (optional):")
    if got is None:
        return
    reason, notes = got
    if decline:
        fn = lambda aid: data.decline_offer(aid, reason=reason)  # noqa: E731
    else:
        fn = lambda aid: data.withdraw(aid, reason=reason,  # noqa: E731
                                       notes=notes or None)
    done, failed = run_each(ids, fn)
    on_done()
    report(parent, title, done, failed)


def defer(parent: tk.Misc, aid: str, on_done: Callable[[], None]) -> bool:
    a = data.get_applicant(aid)
    if a is None:
        return False
    suggest = ""
    try:
        from education_system.systems.sixth_form.domain.admissions import (
            cycles,
        )
        suggest = cycles.next_cycle_name(a.intake_year
                                         or data.default_intake_year())
    except Exception:  # noqa: BLE001 — just no suggestion
        pass
    to = ask_text(parent, "Defer",
                  f"Defer {a.full_name}'s offer from "
                  f"{a.intake_year or '—'} to which intake year (YYYY/YY)?",
                  initial=suggest)
    if not to:
        return False
    reason = ask_text(parent, "Defer", "Reason (optional):", required=False)
    if reason is None:
        return False
    ok, _ = attempt(parent, "Defer", data.defer, aid, to_intake=to,
                    reason=reason or None)
    on_done()
    return ok


# ── Offers and capacity ────────────────────────────────────────────

def places_summary(aid: str) -> str:
    """'A Level Biology: 3 left · A Level Maths: full' for the
    applicant's choices in their intake (blank when no limits set)."""
    try:
        from education_system.systems.sixth_form.domain.admissions import (
            capacity,
        )
        a = data.get_applicant(aid)
        if a is None or not a.intake_year:
            return ""
        parts = []
        for c in data.list_programme_choices(aid):
            p = capacity.get_programme_places(a.intake_year, c)
            if p.places is None:
                continue
            left = p.places_left
            parts.append(f"{p.label}: "
                         + ("full" if not left else f"{left} left")
                         + f" of {p.places}")
        return " · ".join(parts)
    except Exception:  # noqa: BLE001 — display only
        logger.debug("places summary failed for %s", aid, exc_info=True)
        return ""


def make_offer(parent: tk.Misc, aid: str, **kwargs: Any) -> Any:
    """``admissions.make_offer`` that handles a full programme: waitlist
    the applicant, or override capacity with a reason. Returns the
    updated applicant, or None when nothing was offered."""
    from education_system.systems.sixth_form.domain.admissions import (
        capacity,
    )
    try:
        return data.make_offer(aid, **kwargs)
    except capacity.CapacityFull as full:
        choice = choose_action(
            parent, "Programme full",
            f"{full}\n\nFull: {', '.join(full.programmes)}",
            ["Waitlist", "Override capacity"])
        if choice == "Waitlist":
            ok, _ = attempt(parent, "Waitlist", capacity.waitlist_if_full,
                            aid, notes="Programme full at offer")
            if ok:
                messagebox.showinfo("Waitlist", f"{aid} has been put on the "
                                    "waitlist.", parent=_top(parent))
            return None
        if choice == "Override capacity":
            reason = ask_reason(parent, "Override capacity",
                                "Why is this offer going over the places "
                                "set?")
            if not reason:
                return None
            ok, out = attempt(parent, "Make offer", data.make_offer, aid,
                              override_capacity=True, **kwargs)
            if ok:
                attempt(parent, "Make offer", data.add_note, aid,
                        f"Capacity override reason: {reason}",
                        author=username())
                return out
        return None
    except Exception as e:  # noqa: BLE001 — every refusal is shown
        show_error(parent, "Make offer", e)
        return None


# ── E-mail results ─────────────────────────────────────────────────

def show_queued(parent: tk.Misc, title: str, msgs: Any) -> None:
    """Honest delivery result for a send (one message or a list)."""
    if msgs is None:
        return
    if not isinstance(msgs, (list, tuple)):
        msgs = [msgs]
    if not msgs:
        messagebox.showinfo(title, "No message was queued.",
                            parent=_top(parent))
        return
    lines = [f"{m.recipient_role}: {m.to_name or ''} <{m.to_address}> — "
             f"{m.label}" for m in msgs]
    messagebox.showinfo(title, "\n".join(lines), parent=_top(parent))


# ── GDPR erasure (two people) ──────────────────────────────────────

def erasure(parent: tk.Misc, aid: str, on_done: Callable[[], None],
            on_erased: Callable[[], None]) -> None:
    """Request erasure; a second person with governance approves or
    rejects a pending request."""
    rs = _safety()
    ok, pending = attempt(parent, "Erasure", lambda: [
        r for r in rs.list_erasure_requests(status="Pending")
        if r.applicant_id == aid])
    if not ok:
        return
    if pending:
        req = pending[0]
        mine = (req.requested_by or "") == (username() or "")
        info = (f"Erasure request #{req.request_id} by {req.requested_by} "
                f"on {req.requested_at}:\n{req.reason}\n\n")
        if mine or not rs.can_approve_erasure():
            messagebox.showinfo(
                "Erasure request",
                info + "It is waiting for a second person with governance "
                "access to approve it. The person who asked cannot approve "
                "their own request.", parent=_top(parent))
            return
        choice = choose_action(
            parent, "Erasure request",
            info + "Approving erases this applicant's data now. This cannot "
            "be undone.", ["Approve and erase", "Reject request"])
        if choice is None:
            return
        note = ask_text(parent, "Erasure", "Note (optional):",
                        required=False)
        if note is None:
            return
        if choice == "Approve and erase":
            ok, _ = attempt(parent, "Erasure", rs.approve_erasure,
                            req.request_id, note=note or None)
            if ok:
                messagebox.showinfo("Erasure", f"{aid} has been erased.",
                                    parent=_top(parent))
                on_erased()
                return
        else:
            attempt(parent, "Erasure", rs.reject_erasure, req.request_id,
                    note=note or None)
        on_done()
        return
    reason = ask_reason(
        parent, "Request erasure",
        "Reason for erasure (e.g. the applicant's request and its date).\n"
        "A second person with governance access must approve it:")
    if not reason:
        return
    ok, req = attempt(parent, "Request erasure", rs.request_erasure, aid,
                      reason=reason)
    if ok:
        messagebox.showinfo(
            "Request erasure",
            f"Erasure request #{req.request_id} recorded. A second person "
            "with governance access must approve it before anything is "
            "erased.", parent=_top(parent))
    on_done()
