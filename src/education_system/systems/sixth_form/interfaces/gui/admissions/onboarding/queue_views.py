"""Onboarding work queues and cohort actions.

* **My queue** — :func:`workflow.my_queue` for the signed-in member of
  staff ("me"), any member of staff (staff id / login / e-mail) or an
  owner role, optionally overdue only; bulk status changes and bulk
  assignment report per task (:class:`workflow.BulkResult`).
* **Cohort** — :func:`workflow.bulk_open_for_cohort` and
  :func:`workflow.reonboard_cohort`, with one result line per learner.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    templates as tpl,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    workflow,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)
from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding import (
    checklist_extras as extras,
)
from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding import (
    onboarding_actions as actions,
)

logger = logging.getLogger(__name__)

ME = "me"


def _current_year() -> str:
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            enrolments,
        )
        return enrolments.current_academic_year()
    except Exception:  # noqa: BLE001
        return ""


class _WriteTab:
    def __init__(self, nb: ttk.Notebook, title: str) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=title)
        self._writable = actions.can_write()
        self._write_buttons: list[ttk.Button] = []

    def _wbtn(self, parent: tk.Misc, text: str,
              command: Callable[[], None]) -> ttk.Button:
        b = ttk.Button(parent, text=text, command=command)
        self._write_buttons.append(b)
        return b

    def _parent(self) -> tk.Misc:
        return self.frame.winfo_toplevel()


# ══ My queue ══════════════════════════════════════════════════════

class QueueTab(_WriteTab):
    COLS = [("due", "Due", 90), ("student", "Student", 80),
            ("name", "Name", 150), ("year", "Year", 70),
            ("chk", "Checklist", 70), ("task", "Task", 300),
            ("category", "Category", 140), ("status", "Status", 85),
            ("owner", "Owner", 90), ("assigned", "Assigned", 100),
            ("why", "Why it's here", 100)]

    def __init__(self, nb: ttk.Notebook) -> None:
        super().__init__(nb, "My queue")
        self._rows: dict[str, workflow.QueueRow] = {}
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Queue for:").pack(side="left")
        self.who_cb = ttk.Combobox(bar, values=(ME,) + tpl.OWNER_ROLES,
                                   width=22)
        self.who_cb.set(ME)
        self.who_cb.pack(side="left", padx=(2, 4))
        self.who_cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.who_cb.bind("<Return>", lambda _e: self.refresh())
        ttk.Label(bar, foreground="#888", text="(me, an owner role, or a "
                  "staff id / login / e-mail)").pack(side="left")
        ttk.Label(bar, text="Academic year:").pack(side="left", padx=(12, 0))
        self.year_e = ttk.Entry(bar, width=10)
        self.year_e.pack(side="left", padx=(2, 8))
        self.overdue_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Overdue only", variable=self.overdue_var,
                        command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Show", command=self.refresh).pack(side="left",
                                                                 padx=8)
        self.count_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.count_var,
                  foreground="#555").pack(side="right")

        acts = ttk.Frame(self.frame)
        acts.pack(side="bottom", fill="x", padx=8, pady=(4, 8))
        self._wbtn(acts, "Set status of selected…",
                   self._bulk_status).pack(side="left")
        self._wbtn(acts, "Assign selected…",
                   self._bulk_assign).pack(side="left", padx=4)
        ttk.Button(acts, text="Select all",
                   command=self._select_all).pack(side="left", padx=(12, 4))
        ttk.Label(acts, foreground="#777", text="Ctrl/Shift-click selects "
                  "several tasks.").pack(side="left", padx=8)
        if not self._writable:
            ttk.Label(acts, foreground="#a33",
                      text="Read-only").pack(side="right")
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=8)
        self.tree = ui.make_tree(holder, self.COLS, height=24,
                                 selectmode="extended")
        self.tree.tag_configure("overdue", background="#ffd0d0")
        self.tree.tag_configure("Blocked", foreground="#a33")
        actions.set_write_state(self._write_buttons, self._writable)

    def _who(self) -> str:
        who = self.who_cb.get().strip()
        if who.lower() == ME:
            me = ui.current_username()
            if not me:
                raise data.ValidationError("You are not signed in — pick a "
                                           "role or a member of staff")
            return me
        return who

    def refresh(self) -> None:
        ui.clear(self.tree)
        self._rows.clear()
        try:
            rows = workflow.my_queue(
                self._who(), academic_year=self.year_e.get().strip() or None,
                overdue_only=self.overdue_var.get())
        except Exception as e:  # noqa: BLE001 — ValidationError shown in place
            self.count_var.set(str(e))
            return
        for q in rows:
            it = q.item
            iid = str(it.item_id)
            self._rows[iid] = q
            tags = (["overdue"] if q.overdue else []) + (
                ["Blocked"] if it.status == "Blocked" else [])
            self.tree.insert("", "end", iid=iid, tags=tuple(tags), values=(
                it.due_date or "—", q.student_id, q.student_name,
                q.academic_year or "—", f"#{q.checklist_id}", it.task_name,
                it.category, it.status, it.owner_role or "",
                it.assigned_to or "", q.why))
        n_late = sum(1 for q in rows if q.overdue)
        self.count_var.set(f"{len(rows)} task(s), {n_late} overdue")

    def _select_all(self) -> None:
        self.tree.selection_set(self.tree.get_children())

    def _selected_ids(self, title: str) -> list[int]:
        ids = [int(i) for i in self.tree.selection()]
        if not ids:
            messagebox.showinfo(title, "Select one or more tasks first.",
                                parent=self._parent())
        return ids

    def _show_result(self, title: str, res: workflow.BulkResult) -> None:
        lines = res.lines()
        extras.show_lines(self._parent(), title, lines[0], lines[1:])
        self.refresh()

    def _bulk_status(self) -> None:
        ids = self._selected_ids("Set status")
        if not ids:
            return
        v = ui.ask_form(self._parent(), f"Set status of {len(ids)} task(s)", [
            ("status", "New status", "readonly", data.ITEM_STATUSES)],
            {"status": "Done"})
        if v is None or not v["status"]:
            return
        status = v["status"]
        kw: dict[str, Any] = {"completed_by": ui.current_username()}
        if status == "Done":
            problems = []
            for i in ids:
                item = data.get_item(i)
                if item is None:
                    continue
                try:
                    p = data.evidence_problem(item)
                except Exception as e:  # noqa: BLE001
                    p = str(e)
                if p:
                    problems.append(p)
            if problems:
                ev = actions.prompt_text(
                    self._parent(), "Evidence needed",
                    f"{len(problems)} of the {len(ids)} task(s) need "
                    "evidence:\n\n" + "\n".join(f"• {p}" for p in
                                                 problems[:8])
                    + ("\n…" if len(problems) > 8 else "")
                    + "\n\nSay where the evidence is; it is recorded on the "
                    "tasks that need it. Notes never count as evidence.",
                    label="Evidence:")
                if ev is None:
                    return
                kw["evidence"] = ev
        elif status in ("N/A", "Blocked"):
            reason = actions.prompt_text(
                self._parent(), status,
                ("Why do these tasks not apply?" if status == "N/A"
                 else "What is blocking these tasks?"), label="Reason:")
            if reason is None:
                return
            kw["reason"] = reason
        elif not messagebox.askyesno(
                status, f"Set {len(ids)} task(s) to {status}? Any evidence "
                "on them is cleared (the history keeps it).",
                parent=self._parent()):
            return
        try:
            res = workflow.bulk_set_status(ids, status, **kw)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Set status", str(e), parent=self._parent())
            return
        self._show_result(f"Set status — {status}", res)

    def _bulk_assign(self) -> None:
        ids = self._selected_ids("Assign")
        if not ids:
            return
        unchanged = "(leave as it is)"
        v = ui.ask_form(self._parent(), f"Assign {len(ids)} task(s)", [
            ("assignee", "Assign to (staff id, login or e-mail)", "entry",
             None),
            ("clear", "Clear the assignee instead", "check", None),
            ("owner", "Owner role", "readonly", (unchanged,) + tpl.OWNER_ROLES)],
            {"owner": unchanged})
        if v is None:
            return
        kw: dict[str, Any] = {}
        if v["clear"]:
            kw["assignee"] = None
        elif v["assignee"]:
            who = workflow.find_staff(v["assignee"])
            if who is None:
                messagebox.showerror(
                    "Assign", f"{v['assignee']!r} is not an active member "
                    "of staff (staff id, login or e-mail).",
                    parent=self._parent())
                return
            kw["assignee"] = who.staff_id
        if v["owner"] and v["owner"] != unchanged:
            kw["owner_role"] = v["owner"]
        if not kw:
            messagebox.showinfo("Assign", "Nothing to change.",
                                parent=self._parent())
            return
        try:
            res = workflow.bulk_assign(ids, **kw)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Assign", str(e), parent=self._parent())
            return
        self._show_result("Assign", res)


# ══ Cohort actions ════════════════════════════════════════════════

class CohortTab(_WriteTab):
    SUGGEST = "(suggest per learner)"

    def __init__(self, nb: ttk.Notebook) -> None:
        super().__init__(nb, "Cohort")
        self._build()

    def _build(self) -> None:
        year = _current_year()
        box = ttk.LabelFrame(self.frame, text="Open checklists for a cohort",
                             padding=8)
        box.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(box, text="Academic year:").grid(row=0, column=0,
                                                   sticky="e")
        self.year_e = ttk.Entry(box, width=12)
        self.year_e.insert(0, year)
        self.year_e.grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(box, text="Year group:").grid(row=0, column=2, sticky="e")
        self.yg_cb = ttk.Combobox(box, values=("", "12", "13"),
                                  state="readonly", width=5)
        self.yg_cb.grid(row=0, column=3, sticky="w", padx=4)
        ttk.Label(box, text="Tutor group:").grid(row=0, column=4, sticky="e")
        self.tg_e = ttk.Entry(box, width=12)
        self.tg_e.grid(row=0, column=5, sticky="w", padx=4)
        ttk.Label(box, text="Template:").grid(row=1, column=0, sticky="e")
        try:
            names = tpl.template_names()
        except Exception:  # noqa: BLE001
            logger.exception("Template names failed to load")
            names = []
        self.tpl_cb = ttk.Combobox(box, values=[self.SUGGEST, *names],
                                   state="readonly", width=30)
        self.tpl_cb.set(self.SUGGEST)
        self.tpl_cb.grid(row=1, column=1, columnspan=3, sticky="w", padx=4,
                         pady=2)
        self._wbtn(box, "Open checklists…", self._open).grid(
            row=1, column=4, columnspan=2, sticky="w", padx=4)
        ttk.Label(box, foreground="#777", text=(
            "Every live enrolment in the year (and year group / tutor group) "
            "gets a checklist; learners who already have one for the year "
            "are skipped, so running it again is safe.")).grid(
            row=2, column=0, columnspan=6, sticky="w", pady=(4, 0))

        box2 = ttk.LabelFrame(self.frame, text="Year 13 re-onboarding",
                              padding=8)
        box2.pack(fill="x", padx=8, pady=4)
        ttk.Label(box2, text="From (Year 12) year:").pack(side="left")
        self.from_e = ttk.Entry(box2, width=12)
        self.from_e.pack(side="left", padx=(2, 10))
        ttk.Label(box2, text="To (Year 13) year:").pack(side="left")
        self.to_e = ttk.Entry(box2, width=12)
        self.to_e.insert(0, year)
        self.to_e.pack(side="left", padx=(2, 10))
        try:
            start = int(year[:4])        # "2025/26" -> "2024/25"
            self.from_e.insert(0, f"{start - 1}/{str(start)[-2:]}")
        except ValueError:
            pass
        self._wbtn(box2, "Re-onboard Year 13…",
                   self._reonboard).pack(side="left", padx=8)
        ttk.Label(box2, foreground="#777", text="A short 'Year 13 return' "
                  "checklist for learners who were in Year 12 here.").pack(
            side="left", padx=8)

        self.summary_var = tk.StringVar(value="Results appear here.")
        ttk.Label(self.frame, textvariable=self.summary_var,
                  font=("", 10, "bold")).pack(fill="x", padx=8, pady=(8, 2))
        holder = ttk.Frame(self.frame)
        holder.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree = ui.make_tree(holder, [
            ("student", "Student", 100), ("result", "Result", 80),
            ("chk", "Checklist", 80), ("template", "Template", 200),
            ("detail", "Detail", 700)], height=20)
        for tag, colour in (("opened", "#d8f4d8"), ("skipped", "#eeeeee"),
                            ("failed", "#ffd0d0")):
            self.tree.tag_configure(tag, background=colour)
        if not self._writable:
            ttk.Label(self.frame, foreground="#a33", text="Read-only: you "
                      "can't open checklists.").pack(side="bottom", pady=4)
        actions.set_write_state(self._write_buttons, self._writable)

    def _show(self, title: str, lines: list[workflow.CohortLine]) -> None:
        ui.clear(self.tree)
        counts: dict[str, int] = {}
        for n, ln in enumerate(lines):
            counts[ln.result] = counts.get(ln.result, 0) + 1
            self.tree.insert("", "end", iid=str(n), tags=(ln.result,), values=(
                ln.student_id, ln.result,
                f"#{ln.checklist_id}" if ln.checklist_id else "",
                ln.template or "", ln.detail))
        self.summary_var.set(f"{title}: " + (", ".join(
            f"{v} {k}" for k, v in sorted(counts.items()))
            or "no learners matched"))

    def _open(self) -> None:
        year = self.year_e.get().strip()
        if not year:
            messagebox.showinfo("Open checklists", "Give an academic year.",
                                parent=self._parent())
            return
        yg = int(self.yg_cb.get()) if self.yg_cb.get() else None
        tg = self.tg_e.get().strip() or None
        template = None if self.tpl_cb.get() in ("", self.SUGGEST) \
            else self.tpl_cb.get()
        scope = " ".join(x for x in (
            year, f"Year {yg}" if yg else "", f"tutor group {tg}" if tg
            else "") if x)
        if not messagebox.askyesno(
                "Open checklists",
                f"Open onboarding checklists for {scope} from "
                f"{template or 'each learner’s suggested template'}?",
                parent=self._parent()):
            return
        try:
            lines = workflow.bulk_open_for_cohort(
                year, year_group=yg, tutor_group=tg, template=template)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Open checklists", str(e),
                                 parent=self._parent())
            return
        self._show(f"Open checklists for {scope}", lines)

    def _reonboard(self) -> None:
        a, b = self.from_e.get().strip(), self.to_e.get().strip()
        if not a or not b:
            messagebox.showinfo("Re-onboard", "Give both academic years.",
                                parent=self._parent())
            return
        if not messagebox.askyesno(
                "Re-onboard Year 13",
                f"Open a Year 13 return checklist in {b} for each learner "
                f"who was in Year 12 here in {a}?", parent=self._parent()):
            return
        try:
            lines = workflow.reonboard_cohort(a, b)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Re-onboard", str(e), parent=self._parent())
            return
        self._show(f"Year 13 re-onboarding {a} → {b}", lines)
