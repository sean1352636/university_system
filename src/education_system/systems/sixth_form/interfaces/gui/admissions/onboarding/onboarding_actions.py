"""Onboarding task status changes, second checks and the history viewer.

Every status change goes through ``onboarding.set_item_status``; this
module only asks for what the domain needs first:

* **Done** asks for written evidence only when ``evidence_problem`` says
  the record is not on file. Notes are never evidence.
* **N/A** asks why the task does not apply (refused by the domain for ID
  and right-to-study tasks — the refusal is shown as it comes).
* **Blocked** asks what is blocking it.
* Re-opening a done task warns that its completion and evidence are
  cleared (the history keeps them).
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
    simpledialog,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding.onboarding import (
    Item,
)
from education_system.systems.sixth_form.interfaces.gui._ui import (
    grab_when_viewable,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)

logger = logging.getLogger(__name__)

MIN_CHARS = 5


def can_write() -> bool:
    """Whether the signed-in user may change onboarding (never raises)."""
    try:
        return bool(data.can_write())
    except Exception:  # noqa: BLE001 — unknown user = read-only screen
        logger.debug("onboarding can_write check failed", exc_info=True)
        return False


def set_write_state(buttons: list[tk.Misc], allowed: bool) -> None:
    for b in buttons:
        try:
            b.configure(state="normal" if allowed else "disabled")
        except tk.TclError:
            pass


# ── Text prompt (evidence / reasons) ─────────────────────────────────

class TextPrompt:
    """A modal prompt with a message and a text box.

    ``on_submit`` is called with the text when OK is pressed; an exception
    keeps the prompt open and shows the message, so it can be fixed in
    place. Text shorter than ``min_chars`` (ignoring spaces) is refused
    before ``on_submit`` is called."""

    def __init__(self, parent: tk.Misc, title: str, message: str, *,
                 label: str = "", initial: str = "",
                 min_chars: int = MIN_CHARS,
                 on_submit: Callable[[str], Any] | None = None) -> None:
        self.title = title
        self.min_chars = min_chars
        self.on_submit = on_submit
        self.result: str | None = None
        self.win = make_toplevel(parent)
        self.win.title(title)
        try:
            self.win.transient(parent)
        except tk.TclError:
            pass
        body = ttk.Frame(self.win, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=message, wraplength=520, justify="left",
                  anchor="w").pack(fill="x", pady=(0, 8))
        if label:
            ttk.Label(body, text=label, anchor="w").pack(fill="x")
        bar = ttk.Frame(body)
        bar.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(bar, text="OK", command=self._ok).pack(side="left")
        ttk.Button(bar, text="Cancel",
                   command=self.win.destroy).pack(side="left", padx=8)
        if min_chars:
            ttk.Label(bar, foreground="#777",
                      text=f"At least {min_chars} characters."
                      ).pack(side="right")
        self.text = tk.Text(body, width=64, height=5, wrap="word")
        self.text.pack(fill="both", expand=True)
        if initial:
            self.text.insert("1.0", initial)
        self.text.focus_set()
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def value(self) -> str:
        return self.text.get("1.0", "end").strip()

    def _ok(self) -> None:
        text = self.value()
        if len(text.replace(" ", "")) < self.min_chars:
            messagebox.showwarning(
                self.title, f"Please write at least {self.min_chars} "
                "characters.", parent=self.win)
            return
        if self.on_submit is not None:
            try:
                self.on_submit(text)
            except Exception as e:  # noqa: BLE001 — shown, prompt stays open
                messagebox.showerror(self.title, str(e), parent=self.win)
                return
        self.result = text
        self.win.destroy()

    def show(self) -> str | None:
        grab_when_viewable(self.win)
        self.win.wait_window()
        return self.result


def prompt_text(parent: tk.Misc, title: str, message: str, **kw) -> str | None:
    return TextPrompt(parent, title, message, **kw).show()


# ── Status changes ───────────────────────────────────────────────────

def _apply(parent: tk.Misc, title: str, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 — ValidationError / AccessDenied shown
        messagebox.showerror(title, str(e), parent=parent)
        return None


def change_status(parent: tk.Misc, item: Item, status: str, *,
                  completed_by: str | None = None) -> Item | None:
    """Move *item* to *status*, asking for evidence or a reason when the
    rules need one. Returns the updated item, or None if nothing changed."""
    if status == item.status:
        return None
    iid = item.item_id
    title = f"{status} — {item.task_name}"
    holder: dict[str, Item] = {}

    def run(**kw) -> None:
        holder["item"] = data.set_item_status(
            iid, status, completed_by=completed_by, **kw)

    if status == "Done":
        problem = _apply(parent, title, lambda: data.evidence_problem(item))
        if not problem:
            return _apply(parent, title, lambda: data.set_item_status(
                iid, "Done", completed_by=completed_by))
        if prompt_text(
                parent, "Evidence needed",
                f"{problem}\n\nSay where the evidence is (for example "
                "'Signed form scanned to the student file 12/09'). Notes on "
                "the task never count as evidence.",
                label="Evidence:", initial=item.evidence or "",
                on_submit=lambda t: run(evidence=t)) is None:
            return None
        out = holder.get("item")
        if out is not None and out.awaiting_second_check:
            messagebox.showinfo(
                "Second check needed",
                f"Evidence recorded. '{out.task_name}' stays In Progress "
                "until someone else confirms it with "
                "\"Confirm evidence (second check)\".", parent=parent)
        return out
    if status == "N/A":
        if item.key in data.ID_ITEMS:
            # The domain refuses this; show its reason as it gives it.
            return _apply(parent, title, lambda: data.set_item_status(
                iid, "N/A", completed_by=completed_by))
        if prompt_text(
                parent, "Not applicable",
                f"Why does '{item.task_name}' not apply to this learner?",
                label="Reason:", initial=item.na_reason or "",
                on_submit=lambda t: run(reason=t)) is None:
            return None
        return holder.get("item")
    if status == "Blocked":
        if prompt_text(
                parent, "Blocked",
                f"What is blocking '{item.task_name}'?",
                label="Reason:", initial=item.blocked_reason or "",
                on_submit=lambda t: run(reason=t)) is None:
            return None
        return holder.get("item")
    # Pending / In Progress: re-opening clears completion and evidence.
    if (item.is_done or item.evidence or item.evidence_ref) and not \
            messagebox.askyesno(
                "Re-open task",
                f"Re-open '{item.task_name}'?\n\nIts completion, evidence "
                "and N/A reason are cleared (the history keeps them).",
                parent=parent):
        return None
    return _apply(parent, title, lambda: data.set_item_status(
        iid, status, completed_by=completed_by))


def confirm_second_check(parent: tk.Misc, item: Item) -> Item | None:
    """Second person's confirmation of written evidence (right to study)."""
    if not item.awaiting_second_check:
        messagebox.showinfo(
            "Confirm evidence",
            f"'{item.task_name}' is not waiting for a second check.",
            parent=parent)
        return None
    note = simpledialog.askstring(
        "Confirm evidence (second check)",
        f"{item.task_name}\n\nEvidence recorded by "
        f"{item.verified_by or '—'} on {item.verified_on or '—'}:\n"
        f"{item.evidence}\n\nYou are confirming it as the second check — "
        "it must be someone other than the person who recorded it.\n"
        "Note (optional):", parent=parent)
    if note is None:
        return None
    return _apply(parent, "Confirm evidence", lambda: data.confirm_evidence(
        item.item_id, note=note.strip() or None))


def describe_item(item: Item) -> str:
    """The detail panel text for one task."""
    lines = [f"#{item.item_id}  {item.task_name}"
             + ("  (required)" if item.required else "")]
    if item.item_key and item.item_key != item.task_name \
            and item.task_name != data.RESTRICTED:
        lines.append(f"Rule key: {item.item_key}")
    lines.append(f"Status: {item.status}"
                 + (f"   Completed {item.completed_on} by "
                    f"{item.completed_by or '—'}" if item.completed_on else ""))
    if item.evidence_ref:
        lines.append(f"Record on file: {item.evidence_ref}")
    if item.evidence:
        lines.append(f"Evidence: {item.evidence}")
    if item.verified_by or item.verified_on:
        lines.append(f"Verified by {item.verified_by or '—'} on "
                     f"{item.verified_on or '—'}")
    if item.second_check_by:
        lines.append(f"Second check: {item.second_check_by} on "
                     f"{item.second_check_on or '—'}")
    elif item.awaiting_second_check:
        lines.append("Awaiting a second check by someone else.")
    if item.na_reason:
        lines.append(f"N/A reason: {item.na_reason}")
    if item.blocked_reason:
        lines.append(f"Blocked: {item.blocked_reason}")
    owner = " / ".join(x for x in (item.owner_role, item.assigned_to) if x)
    if owner:
        lines.append(f"Owner: {owner}")
    if item.source:
        lines.append(f"Source: {item.source}")
    if item.notes:
        lines.append(f"Notes (not evidence): {item.notes}")
    return "\n".join(lines)


# ── History viewer ───────────────────────────────────────────────────

class HistoryWindow:
    """The onboarding audit trail for one checklist or one learner."""

    def __init__(self, parent: tk.Misc, *, checklist_id: int | None = None,
                 student_id: str | None = None) -> None:
        if checklist_id is None and not student_id:
            raise ValueError("HistoryWindow needs a checklist or a student")
        self.checklist_id = checklist_id
        self.student_id = student_id
        what = (f"checklist #{checklist_id}" if checklist_id is not None
                else f"student {student_id}")
        self.win = ui.new_window(parent, f"Onboarding history — {what}")
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Close",
                   command=self.win.destroy).pack(side="left", padx=6)
        self.count_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.count_var,
                  foreground="#555").pack(side="right")
        self.detail = tk.Text(self.win, height=6, wrap="word")
        self.detail.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        self.detail.configure(state="disabled")
        holder = ttk.Frame(self.win)
        holder.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree = ui.make_tree(holder, [
            ("when", "When", 150), ("chk", "Checklist", 80),
            ("task", "Task", 260), ("action", "Action", 120),
            ("detail", "Detail", 520), ("by", "By", 130)], height=24)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show())
        self._rows: dict[str, dict[str, Any]] = {}
        self.refresh()

    def _task_names(self) -> dict[int, str]:
        if self.checklist_id is not None:
            cids = [self.checklist_id]
        else:
            cids = [c.checklist_id for c in data.list_checklists(
                student_id=self.student_id, include_archived=True)]
        names: dict[int, str] = {}
        for cid in cids:
            for it in data.list_items(checklist_id=cid):
                names[it.item_id] = it.task_name
        return names

    def refresh(self) -> None:
        ui.clear(self.tree)
        self._rows.clear()
        try:
            rows = data.history(checklist_id=self.checklist_id,
                                student_id=self.student_id)
            names = self._task_names()
        except Exception as e:  # noqa: BLE001 — shown in the window
            logger.exception("Onboarding history failed to load")
            messagebox.showerror("History", str(e), parent=self.win)
            return
        for r in rows:
            item_id = r.get("item_id")
            task = ""
            restricted = False
            if item_id is not None:
                task = names.get(item_id, f"task #{item_id} (removed)")
                restricted = task == data.RESTRICTED
            detail = "(restricted)" if restricted else (r.get("detail") or "")
            iid = str(r["history_id"])
            self._rows[iid] = {**r, "task": task, "detail": detail}
            self.tree.insert("", "end", iid=iid, values=(
                r.get("changed_at") or "", f"#{r.get('checklist_id')}", task,
                r.get("action") or "", detail.replace("\n", " "),
                r.get("changed_by") or "—"))
        self.count_var.set(f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'}"
                           " (newest first)")
        self._show()

    def _show(self) -> None:
        sel = self.tree.selection()
        r = self._rows.get(sel[0]) if sel else None
        text = ""
        if r:
            text = (f"{r.get('changed_at')}  ·  checklist #{r.get('checklist_id')}"
                    f"  ·  {r.get('action')}  ·  by {r.get('changed_by') or '—'}\n"
                    + (f"Task: {r['task']}\n" if r["task"] else "")
                    + r["detail"])
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")
