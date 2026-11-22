"""Checklist actions added in the second onboarding wave.

* "Re-check from records" — :func:`evidence_sources.resync` on one
  checklist, or :func:`evidence_sources.resync_all` on every open one.
* "Link bursary application…" — :func:`bursary_link.link_application`.
* The learner's sixth form login state for the checklist header
  (:func:`evidence_sources.login_state`, read-only, cached per learner).
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)

logger = logging.getLogger(__name__)

#: Lines shown in a message box before the rest go to a text window.
_MAX_LINES = 15


def _evidence_sources():
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        evidence_sources,
    )
    return evidence_sources


def show_lines(parent: tk.Misc, title: str, summary: str,
               lines: list[str]) -> None:
    """A short result in a message box; a long one in a text window."""
    if len(lines) <= _MAX_LINES:
        messagebox.showinfo(title, "\n".join([summary, *lines]),
                            parent=parent)
    else:
        ui.show_text(parent, title, "\n".join([summary, "", *lines]))


def _resync_lines(res: Any) -> list[str]:
    return ([f"Ticked: {t}" for t in res.ticked]
            + [f"Re-opened: {t}" for t in res.reopened]
            + [f"Error: {t}" for t in res.errors])


def resync_one(parent: tk.Misc, checklist_id: int) -> bool:
    try:
        res = _evidence_sources().resync(checklist_id)
    except Exception as e:  # noqa: BLE001 — ValidationError / AccessDenied
        messagebox.showerror("Re-check from records", str(e), parent=parent)
        return False
    show_lines(parent, "Re-check from records", res.summary,
               _resync_lines(res))
    return True


def resync_everything(parent: tk.Misc,
                      academic_year: str | None = None) -> bool:
    what = f"open checklists for {academic_year}" if academic_year \
        else "every open checklist"
    if not messagebox.askyesno(
            "Re-check all from records",
            f"Check {what} against the learners' records?\n\nTasks whose "
            "record now exists are ticked; tasks ticked from a record that "
            "has gone are re-opened. Hand-evidenced tasks are left alone.",
            parent=parent):
        return False
    try:
        res = _evidence_sources().resync_all(academic_year=academic_year)
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Re-check all from records", str(e),
                             parent=parent)
        return False
    show_lines(parent, "Re-check all from records", res.summary,
               _resync_lines(res))
    return True


class LoginStates:
    """Cached :func:`evidence_sources.login_state` per learner."""

    LABELS = {"Active": "active", "Disabled": "disabled",
              "No sixth form access": "no sixth form access",
              "None": "no login yet"}

    def __init__(self) -> None:
        self._cache: dict[str, str | None] = {}

    def label(self, student_id: str) -> str:
        if student_id not in self._cache:
            try:
                self._cache[student_id] = _evidence_sources().login_state(
                    student_id)
            except Exception:  # noqa: BLE001 — header only
                logger.debug("login state failed", exc_info=True)
                self._cache[student_id] = None
        state = self._cache[student_id]
        return self.LABELS.get(state or "", "can't tell") if state \
            else "can't tell"

    def clear(self) -> None:
        self._cache.clear()


# ── Bursary ─────────────────────────────────────────────────────────

def link_bursary(parent: tk.Misc, checklist_id: int) -> bool:
    """Pick one of the learner's bursary applications and point the
    checklist's bursary task at it (the task is added when missing)."""
    from education_system.systems.sixth_form.domain.admissions.onboarding import (
        bursary_link,
    )
    chk = data.get_checklist(checklist_id)
    if chk is None:
        return False
    has_task = any(i.key == bursary_link.BURSARY_KEY
                   for i in data.list_items(checklist_id=checklist_id))
    try:
        from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
            bursaries,
        )
        apps = bursaries.list_applications(student_id=chk.student_id)
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Link bursary application", str(e),
                             parent=parent)
        return False
    if not apps:
        messagebox.showinfo(
            "Link bursary application",
            f"{chk.student_id} has no bursary application. Open one in "
            "Finance → Bursaries first.", parent=parent)
        return False
    if not has_task and not messagebox.askyesno(
            "Link bursary application",
            f"This checklist has no '{bursary_link.BURSARY_KEY}' task. Add "
            "it (required) and link the application?", parent=parent):
        return False
    labels = {f"#{a.application_id} — {a.bursary_type}, "
              f"{a.academic_year or 'no year'}, {a.status}": a.application_id
              for a in apps}
    holder: dict[str, Any] = {}

    def run(v: dict[str, Any]) -> None:
        if v["app"] not in labels:
            raise data.ValidationError("Pick an application")
        holder["item"] = bursary_link.link_application(
            checklist_id, labels[v["app"]], required=True)

    if ui.ask_form(parent, "Link bursary application", [
            ("app", "Application", "readonly", list(labels))],
            {"app": next(iter(labels))}, on_submit=run) is None:
        return False
    item = holder.get("item")
    if item is not None:
        messagebox.showinfo(
            "Link bursary application",
            f"'{item.task_name}' is linked ({item.evidence_ref or 'done'}). "
            + ("It ticks once the application is submitted — use "
               "\"Re-check from records\"." if not item.is_done else ""),
            parent=parent)
    return True
