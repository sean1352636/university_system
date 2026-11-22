"""Tkinter views for Sixth Form Onboarding.

Sidebar sections:

* Checklists  — master list (filterable by year, archived on request)
                with a per-checklist detail pane on the right: items,
                status changes through the evidence rules, second checks,
                history, consents, re-check from records, templates,
                bursary link.
* Templates   — stored, versioned templates (templates_views.py).
* Summary     — counts + overdue / upcoming alerts.
* My queue, Cohort (queue_views.py), Induction (induction_views.py),
  Reports, Outstanding, Chase log (reports_views.py).
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
    simpledialog,
)
from typing import Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding.onboarding import (
    CATEGORIES,
    CHECKLIST_STATUSES,
    Checklist,
    DEFAULT_CATEGORY,
    DEFAULT_CHECKLIST_STATUS,
    DEFAULT_ITEM_STATUS,
    DEFAULT_TEMPLATE,
    Item,
    ITEM_STATUSES,
    ValidationError,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    templates as tpl,
)
from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding import (
    checklist_extras as extras,
)
from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding import (
    onboarding_actions as actions,
)
from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding.templates_views import (
    TemplatesTab,
    apply_template_dialog,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_onboarding_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = make_toplevel(master) if master is not None else tk.Tk()
    win.title(f"Onboarding — {branding.SYSTEM_NAME}")
    window_sizing.fit(win, WIN_GEOMETRY, WIN_MINSIZE)

    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ChecklistsTab(nb)
    TemplatesTab(nb)
    SummaryTab(nb)
    from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding import (
        induction_views,
        queue_views,
        reports_views,
    )
    queue_views.QueueTab(nb)
    queue_views.CohortTab(nb)
    induction_views.InductionTab(nb)
    reports_views.ReportsTab(nb)
    reports_views.OutstandingTab(nb)
    reports_views.ChaseLogTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


def _username() -> str | None:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:  # noqa: BLE001 — recorded as unknown
        return None


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name
             for s in student_data.list_students()}


# ══ Checklists tab ════════════════════════════════════════════════

class ChecklistsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Checklists")
        self._selected_chk: int | None = None
        self._write_buttons: list[ttk.Button] = []
        self._writable = actions.can_write()
        self._logins = extras.LoginStates()
        self._build()
        self.refresh()

    def _wbtn(self, parent: tk.Misc, text: str,
              command: Callable[[], None]) -> ttk.Button:
        """A button that changes data (disabled for read-only users)."""
        b = ttk.Button(parent, text=text, command=command)
        self._write_buttons.append(b)
        return b

    def _build(self) -> None:
        # ── Top filter bar ─────────────────────────────────────────
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Student:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + CHECKLIST_STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Assigned to:").pack(side="left")
        self.f_assigned = ttk.Entry(bar, width=16)
        self.f_assigned.pack(side="left", padx=(2, 10))

        self.open_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only",
                          variable=self.open_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.overdue_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Overdue only",
                          variable=self.overdue_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear_filters).pack(side="left")
        self._wbtn(bar, "New checklist…",
                   self._new).pack(side="left", padx=(16, 0))

        # Second filter row: academic year + archived.
        bar2 = ttk.Frame(self.frame)
        bar2.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(bar2, text="Academic year:").pack(side="left")
        self.f_year = ttk.Combobox(bar2, values=self._year_options(),
                                   width=10)
        self.f_year.pack(side="left", padx=(2, 10))
        self.f_year.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.f_year.bind("<Return>", lambda _e: self.refresh())
        self.archived_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Show archived",
                        variable=self.archived_var,
                        command=self.refresh).pack(side="left", padx=4)
        if not self._writable:
            ttk.Label(bar2, foreground="#a33", text=(
                "Read-only: you can view onboarding but not change it "
                "(needs admissions or students.manage).")).pack(
                side="left", padx=(16, 0))

        # ── Split: left = checklists, right = items ───────────────
        pane = ttk.Panedwindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(left, weight=2)
        pane.add(right, weight=3)

        # Left actions — packed before the table so they always show.
        chk_actions = ttk.Frame(left)
        chk_actions.pack(side="bottom", fill="x", padx=2, pady=(4, 0))
        self._wbtn(chk_actions, "Edit",
                   self._edit_checklist).pack(side="left")
        self._wbtn(chk_actions, "Status",
                   self._status_chk).pack(side="left", padx=4)
        self._wbtn(chk_actions, "Delete",
                   self._delete_chk).pack(side="left", padx=4)
        self.restore_btn = self._wbtn(chk_actions, "Restore",
                                      self._restore_chk)
        self.restore_btn.pack(side="left", padx=4)
        ttk.Button(chk_actions, text="History…",
                   command=self._history_chk).pack(side="left", padx=4)
        ttk.Button(chk_actions, text="Student history…",
                   command=self._history_student).pack(side="left", padx=4)
        ttk.Button(chk_actions, text="Refresh",
                    command=self.refresh).pack(side="right")
        chk_actions2 = ttk.Frame(left)
        chk_actions2.pack(side="bottom", fill="x", padx=2, pady=(4, 0))
        self._wbtn(chk_actions2, "Apply template…",
                   self._apply_template).pack(side="left")
        self._wbtn(chk_actions2, "Re-check from records",
                   self._resync).pack(side="left", padx=4)
        self._wbtn(chk_actions2, "Re-check all…",
                   self._resync_all).pack(side="left", padx=4)
        ttk.Button(chk_actions2, text="Chase log…",
                   command=self._chase_log).pack(side="left", padx=4)

        # Left: checklists table
        cols = ("id", "student", "name", "year", "enrolment", "status",
                "progress", "due", "assigned")
        tree_box = ttk.Frame(left)
        tree_box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_box, columns=cols, show="headings")
        headings = {"id": "ID", "student": "Student", "name": "Name",
                    "year": "Year", "enrolment": "Enrolment",
                    "status": "Status", "progress": "Progress",
                    "due": "Due", "assigned": "Assigned"}
        widths = {"id": 45, "student": 75, "name": 180, "year": 70,
                  "enrolment": 75, "status": 110, "progress": 110,
                  "due": 90, "assigned": 110}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(tree_box, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("Completed",   background="#d8f4d8")
        self.tree.tag_configure("In Progress", background="#fff7d0")
        self.tree.tag_configure("Not Started", background="#eef7ff")
        self.tree.tag_configure("On Hold",     background="#eeeeee")
        self.tree.tag_configure("Cancelled",   background="#eeeeee")
        self.tree.tag_configure("Overdue",     background="#ffd0d0")
        self.tree.tag_configure("Archived",    foreground="#888")
        self.tree.bind("<<TreeviewSelect>>",
                        lambda _e: self._on_select())
        self.tree.bind("<Double-1>",
                        lambda _e: self._edit_checklist())

        # Right: detail header + items
        self.detail_var = tk.StringVar(
            value="Select a checklist on the left.")
        ttk.Label(right, textvariable=self.detail_var,
                   font=("", 11, "bold"),
                   anchor="w").pack(fill="x", padx=2, pady=(0, 4))
        self.subdetail_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.subdetail_var,
                   foreground="#555", wraplength=760, justify="left",
                   anchor="w").pack(fill="x", padx=2, pady=(0, 6))

        # Item actions — packed (bottom first) before the table.
        item_actions2 = ttk.Frame(right)
        item_actions2.pack(side="bottom", fill="x", padx=2, pady=(4, 0))
        item_actions = ttk.Frame(right)
        item_actions.pack(side="bottom", fill="x", padx=2, pady=(4, 0))
        self._wbtn(item_actions, "Toggle ✓",
                   self._toggle_item).pack(side="left")
        self._wbtn(item_actions, "Status",
                   self._status_item).pack(side="left", padx=4)
        self._wbtn(item_actions, "New item",
                   self._new_item).pack(side="left", padx=4)
        self._wbtn(item_actions, "Edit",
                   self._edit_item).pack(side="left", padx=4)
        self._wbtn(item_actions, "Delete",
                   self._delete_item).pack(side="left", padx=4)
        ttk.Button(item_actions, text="Consents…",
                    command=self._consents).pack(side="left", padx=(12, 4))
        ttk.Button(item_actions, text="Photo & ID…",
                    command=self._identity).pack(side="left")
        self.confirm_btn = self._wbtn(item_actions2,
                                      "Confirm evidence (second check)",
                                      self._confirm_item)
        self.confirm_btn.pack(side="left")
        self._wbtn(item_actions2, "Mark N/A…",
                   lambda: self._quick_status("N/A")).pack(side="left",
                                                           padx=4)
        self._wbtn(item_actions2, "Mark blocked…",
                   lambda: self._quick_status("Blocked")).pack(side="left",
                                                               padx=4)
        self._wbtn(item_actions2, "Link bursary application…",
                   self._link_bursary).pack(side="left", padx=(12, 4))

        self.item_detail = tk.Text(right, height=7, wrap="word",
                                   background="#fafafa")
        self.item_detail.pack(side="bottom", fill="x", padx=2, pady=(4, 0))
        self.item_detail.configure(state="disabled")

        item_cols = ("done", "req", "id", "category", "task",
                     "status", "due", "completed", "evidence", "verified",
                     "reason", "second")
        items_box = ttk.Frame(right)
        items_box.pack(fill="both", expand=True)
        self.items_tree = ttk.Treeview(items_box, columns=item_cols,
                                          show="headings")
        item_headings = {"done": "✓", "req": "*", "id": "ID",
                          "category": "Category", "task": "Task",
                          "status": "Status", "due": "Due",
                          "completed": "Completed", "evidence": "Evidence",
                          "verified": "Verified by / on",
                          "reason": "N/A / blocked reason",
                          "second": "Second check"}
        item_widths = {"done": 26, "req": 26, "id": 45,
                        "category": 120, "task": 230,
                        "status": 85, "due": 85, "completed": 130,
                        "evidence": 160, "verified": 140, "reason": 160,
                        "second": 130}
        for c in item_cols:
            self.items_tree.heading(c, text=item_headings[c])
            anchor = "center" if c in ("done", "req") else "w"
            self.items_tree.column(c, width=item_widths[c], anchor=anchor,
                                   stretch=c == "task")
        ivs = ttk.Scrollbar(items_box, orient="vertical",
                              command=self.items_tree.yview)
        ihs = ttk.Scrollbar(items_box, orient="horizontal",
                            command=self.items_tree.xview)
        self.items_tree.configure(yscrollcommand=ivs.set,
                                  xscrollcommand=ihs.set)
        ihs.pack(side="bottom", fill="x")
        ivs.pack(side="right", fill="y")
        self.items_tree.pack(side="left", fill="both", expand=True)
        self.items_tree.tag_configure("done", background="#d8f4d8")
        self.items_tree.tag_configure("Blocked", background="#ffd0d0")
        self.items_tree.tag_configure("N/A", background="#eeeeee")
        self.items_tree.tag_configure("second", background="#fff2c4")
        self.items_tree.bind("<<TreeviewSelect>>",
                             lambda _e: self._on_item_select())
        self.items_tree.bind("<Double-1>",
                                lambda _e: self._toggle_item())
        actions.set_write_state(self._write_buttons, self._writable)

    @staticmethod
    def _year_options() -> list[str]:
        try:
            years = {c.academic_year for c in data.list_checklists(
                include_archived=True) if c.academic_year}
        except Exception:  # noqa: BLE001 — the filter still takes typing
            logger.exception("Onboarding academic years failed to load")
            years = set()
        return [""] + sorted(years, reverse=True)

    def _parent(self) -> tk.Misc:
        return self.frame.winfo_toplevel()

    def _consents(self) -> None:
        """Parental / medical / photo consent items ↔ GDPR consent records.

        Opening the dialog only reads; syncing is its explicit button."""
        if self._selected_chk is None:
            messagebox.showinfo("Consents", "Select a checklist first.")
            return
        from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding.consent_views import (
            ConsentDialog,
        )
        ConsentDialog(self._parent(), self._selected_chk,
                      on_change=self.refresh)

    def _identity(self) -> None:
        if self._selected_chk is None:
            messagebox.showinfo("Photo & ID", "Select a checklist first.")
            return
        c = data.get_checklist(self._selected_chk)
        from education_system.systems.sixth_form.interfaces.gui.admissions.enrolments.identity_checks_views import (
            open_identity_checks_window,
        )
        open_identity_checks_window(self._parent(),
                                    student_id=c.student_id if c else None)

    def _clear_filters(self) -> None:
        self.f_student.delete(0, "end")
        self.f_status.current(0)
        self.f_assigned.delete(0, "end")
        self.f_year.set("")
        self.open_var.set(True)
        self.overdue_var.set(False)
        self.archived_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        self._logins.clear()
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_checklists_with_detail(
                student_id=self.f_student.get().strip() or None,
                status=self.f_status.get() or None,
                assigned_to=self.f_assigned.get().strip() or None,
                open_only=self.open_var.get(),
                overdue_only=self.overdue_var.get(),
                academic_year=self.f_year.get().strip() or None,
                include_archived=self.archived_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        today = _today()
        for r in rows:
            c = r.checklist
            progress = (f"{r.done}/{r.total}  "
                        f"(req {r.required_done}/{r.required_total})")
            tags: list[str] = []
            if c.status in CHECKLIST_STATUSES:
                tags.append(c.status)
            if (c.is_open and c.due_date and c.due_date < today):
                tags.append("Overdue")
            if c.is_archived:
                tags.append("Archived")
            self.tree.insert("", "end", iid=str(c.checklist_id), values=(
                c.checklist_id, c.student_id, c.name,
                c.academic_year or "—",
                f"#{c.enrolment_id}" if c.enrolment_id else "—",
                c.status + (" (archived)" if c.is_archived else ""),
                progress, c.due_date or "—",
                c.assigned_to or "—",
            ), tags=tuple(tags))

        # Re-select previously selected row if it still exists
        if self._selected_chk is not None and self.tree.exists(
                str(self._selected_chk)):
            self.tree.selection_set(str(self._selected_chk))
            self._render_items()
        else:
            self._selected_chk = None
            self._clear_detail()

    def _on_select(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            self._selected_chk = int(sel[0])
        except ValueError:
            return
        self._render_items()

    def _clear_detail(self) -> None:
        for i in self.items_tree.get_children():
            self.items_tree.delete(i)
        self.detail_var.set("Select a checklist on the left.")
        self.subdetail_var.set("")
        self._set_item_detail("")

    def _set_item_detail(self, text: str) -> None:
        self.item_detail.configure(state="normal")
        self.item_detail.delete("1.0", "end")
        self.item_detail.insert("1.0", text)
        self.item_detail.configure(state="disabled")

    def _render_items(self) -> None:
        keep = self._selected_item_id()
        for i in self.items_tree.get_children():
            self.items_tree.delete(i)
        if self._selected_chk is None:
            return
        detail = data.get_checklist_detail(self._selected_chk)
        if detail is None:
            self._clear_detail()
            return
        c = detail.checklist
        self.detail_var.set(
            f"#{c.checklist_id}  {c.name}"
            + ("  [ARCHIVED]" if c.is_archived else ""))
        extra = []
        if c.status_reason and c.status in ("On Hold", "Cancelled"):
            extra.append(f"{c.status}: {c.status_reason}")
        if c.is_archived:
            extra.append(f"Archived {c.archived_at} by "
                         f"{c.archived_by or '—'}: {c.archived_reason or '—'}")
        self.subdetail_var.set(
            f"Student: {c.student_id} — {detail.student_name}  ·  "
            f"Year: {c.academic_year or '—'}  ·  Enrolment: "
            f"{('#' + str(c.enrolment_id)) if c.enrolment_id else 'not linked'}"
            + (f"  ·  {c.learner_type}" if c.learner_type else "")
            + f"  ·  IT login: {self._logins.label(c.student_id)}"
            + f"\nStatus: {c.status}  ·  Due: {c.due_date or '—'}  ·  "
            f"Progress: {detail.done_items}/{detail.total_items} "
            f"({detail.percent_complete}%)  ·  "
            f"Required: {detail.required_done}/{detail.required_total}"
            + ("\n" + "  ·  ".join(extra) if extra else ""))
        self._items = {it.item_id: it for it in detail.items}
        for it in detail.items:
            mark = "✓" if it.is_done else ""
            req = "*" if it.required else ""
            comp = (f"{it.completed_on} by {it.completed_by or '—'}"
                    if it.completed_on else "")
            evidence = it.evidence or (f"record {it.evidence_ref}"
                                       if it.evidence_ref else "")
            verified = (f"{it.verified_by or '—'} {it.verified_on or ''}"
                        if (it.verified_by or it.verified_on) else "")
            reason = (f"N/A: {it.na_reason}" if it.na_reason else
                      f"Blocked: {it.blocked_reason}"
                      if it.blocked_reason else "")
            second = (f"{it.second_check_by} {it.second_check_on or ''}"
                      if it.second_check_by else
                      "awaiting" if it.awaiting_second_check else "")
            tags: list[str] = []
            if it.is_done:
                tags.append("done")
            if it.status in ("Blocked", "N/A"):
                tags.append(it.status)
            if it.awaiting_second_check:
                tags.append("second")
            self.items_tree.insert("", "end", iid=str(it.item_id), values=(
                mark, req, it.item_id, it.category, it.task_name,
                it.status, it.due_date or "—", comp, evidence, verified,
                reason, second,
            ), tags=tuple(tags))
        if keep is not None and self.items_tree.exists(str(keep)):
            self.items_tree.selection_set(str(keep))
        self._update_buttons(c)
        self._on_item_select()

    def _update_buttons(self, c: Checklist | None) -> None:
        """Write buttons follow can_write(); an archived checklist only
        offers Restore."""
        actions.set_write_state(self._write_buttons, self._writable)
        if not self._writable:
            return
        archived = bool(c and c.is_archived)
        for b in self._write_buttons:
            if b is self.restore_btn:
                b.configure(state="normal" if archived else "disabled")
            elif archived and b.cget("text") != "New checklist…":
                b.configure(state="disabled")

    def _on_item_select(self) -> None:
        iid = self._selected_item_id()
        it = getattr(self, "_items", {}).get(iid) if iid is not None else None
        self._set_item_detail(actions.describe_item(it) if it else
                              "Select a task to see its evidence and "
                              "reasons.")

    def _selected_chk_id(self) -> int | None:
        return self._selected_chk

    def _selected_item_id(self) -> int | None:
        sel = self.items_tree.selection()
        if not sel:
            return None
        return int(sel[0])

    # ── Checklist actions ─────────────────────────────────────────
    def _new(self) -> None:
        ChecklistDialog(self._parent(),
                          existing=None, on_save=self._after_new)

    def _after_new(self) -> None:
        self.f_year.configure(values=self._year_options())
        self.refresh()

    def _edit_checklist(self) -> None:
        if not self._writable:
            return
        cid = self._selected_chk_id()
        if cid is None:
            messagebox.showinfo("Edit", "Select a checklist first.")
            return
        existing = data.get_checklist(cid)
        if existing is None:
            return
        if existing.is_archived:
            messagebox.showinfo("Edit", "This checklist is archived — "
                                "restore it first.")
            return
        ChecklistDialog(self._parent(),
                          existing=existing, on_save=self.refresh)

    def _status_chk(self) -> None:
        cid = self._selected_chk_id()
        if cid is None:
            messagebox.showinfo("Status", "Select a checklist first.")
            return
        existing = data.get_checklist(cid)
        if existing is None:
            return
        ChecklistStatusDialog(self._parent(),
                                existing, on_save=self.refresh)

    def _delete_chk(self) -> None:
        """"Delete" archives: the checklist and its history are kept and
        can be restored with "Show archived" → Restore."""
        cid = self._selected_chk_id()
        if cid is None:
            messagebox.showinfo("Delete", "Select a checklist first.")
            return
        reason = actions.prompt_text(
            self._parent(), "Archive checklist",
            f"Archive checklist #{cid}?\n\nIt leaves every list but is "
            "kept, with its tasks and history; tick \"Show archived\" and "
            "use Restore to bring it back.", label="Why is it being "
            "archived?", min_chars=3,
            on_submit=lambda t: data.delete_checklist(cid, reason=t))
        if reason is None:
            return
        self._selected_chk = None
        self.refresh()

    def _restore_chk(self) -> None:
        cid = self._selected_chk_id()
        if cid is None:
            messagebox.showinfo("Restore", "Select an archived checklist "
                                "(tick \"Show archived\").")
            return
        c = data.get_checklist(cid)
        if c is None or not c.is_archived:
            messagebox.showinfo("Restore", "That checklist is not archived.")
            return
        if not messagebox.askyesno("Restore",
                                   f"Restore checklist #{cid}?"):
            return
        try:
            data.restore_checklist(cid)
        except Exception as e:  # noqa: BLE001 — ValidationError / AccessDenied
            messagebox.showerror("Restore failed", str(e))
            return
        self.refresh()

    def _history_chk(self) -> None:
        cid = self._selected_chk_id()
        if cid is None:
            messagebox.showinfo("History", "Select a checklist first.")
            return
        actions.HistoryWindow(self._parent(), checklist_id=cid)

    def _history_student(self) -> None:
        sid = None
        if self._selected_chk is not None:
            c = data.get_checklist(self._selected_chk)
            sid = c.student_id if c else None
        sid = sid or self.f_student.get().strip() or None
        if not sid:
            sid = simpledialog.askstring("Student history",
                                         "Student ID:",
                                         parent=self._parent())
            sid = (sid or "").strip() or None
        if not sid:
            return
        actions.HistoryWindow(self._parent(), student_id=sid)

    def _require_chk(self, title: str) -> int | None:
        cid = self._selected_chk_id()
        if cid is None:
            messagebox.showinfo(title, "Select a checklist first.")
        return cid

    def _apply_template(self) -> None:
        cid = self._require_chk("Apply template")
        if cid is not None and apply_template_dialog(self._parent(),
                                                     cid) is not None:
            self.refresh()

    def _resync(self) -> None:
        cid = self._require_chk("Re-check from records")
        if cid is not None and extras.resync_one(self._parent(), cid):
            self.refresh()

    def _resync_all(self) -> None:
        if extras.resync_everything(self._parent(),
                                    self.f_year.get().strip() or None):
            self.refresh()

    def _chase_log(self) -> None:
        from education_system.systems.sixth_form.interfaces.gui import popout
        from education_system.systems.sixth_form.interfaces.gui.admissions.onboarding.reports_views import (
            ChaseLogTab,
        )
        cid = self._selected_chk_id()
        popout.open_book_page(
            self._parent(), "Onboarding chase log"
            + (f" — checklist #{cid}" if cid else ""),
            lambda book: ChaseLogTab(book, checklist_id=cid))

    def _link_bursary(self) -> None:
        cid = self._require_chk("Link bursary application")
        if cid is not None and extras.link_bursary(self._parent(), cid):
            self.refresh()

    # ── Item actions ──────────────────────────────────────────────
    def _selected_item(self, title: str) -> Item | None:
        iid = self._selected_item_id()
        if iid is None:
            messagebox.showinfo(title, "Select an item first.")
            return None
        return data.get_item(iid)

    def _toggle_item(self) -> None:
        if not self._writable:
            return
        existing = self._selected_item("Toggle")
        if existing is None:
            return
        status = "Pending" if existing.is_done else "Done"
        if actions.change_status(self._parent(), existing, status,
                                 completed_by=_username()) is not None:
            self.refresh()

    def _quick_status(self, status: str) -> None:
        existing = self._selected_item(status)
        if existing is None:
            return
        if actions.change_status(self._parent(), existing, status,
                                 completed_by=_username()) is not None:
            self.refresh()

    def _confirm_item(self) -> None:
        existing = self._selected_item("Confirm evidence")
        if existing is None:
            return
        if actions.confirm_second_check(self._parent(),
                                        existing) is not None:
            self.refresh()

    def _status_item(self) -> None:
        existing = self._selected_item("Status")
        if existing is None:
            return
        ItemStatusDialog(self._parent(),
                           existing, on_save=self.refresh)

    def _new_item(self) -> None:
        cid = self._selected_chk_id()
        if cid is None:
            messagebox.showinfo("New item",
                                  "Select a checklist first.")
            return
        ItemDialog(self._parent(), checklist_id=cid,
                      existing=None, on_save=self.refresh)

    def _edit_item(self) -> None:
        existing = self._selected_item("Edit")
        if existing is None:
            return
        ItemDialog(self._parent(),
                      checklist_id=existing.checklist_id,
                      existing=existing, on_save=self.refresh)

    def _delete_item(self) -> None:
        iid = self._selected_item_id()
        if iid is None:
            messagebox.showinfo("Delete", "Select an item first.")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete item #{iid}?\n\nOnly a task added in "
                "error can be removed; a done or evidenced task stays on the "
                "record (re-open it or mark it N/A instead)."):
            return
        try:
            data.delete_item(iid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Upcoming-due window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=6)
        self.window_e.insert(0, "14")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        body = ttk.Frame(self.frame)
        body.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text = tk.Text(body, wrap="none", height=30, width=48,
                              font=("TkFixedFont", 10))
        self.text.pack(side="left", fill="y")
        self.text.configure(state="disabled")
        right = ttk.LabelFrame(body, text="Outstanding required items "
                               "(open checklists)")
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        cols = (("sid", "Student", 90), ("name", "Name", 160),
                ("chk", "Checklist", 160), ("task", "Task", 220),
                ("status", "Status", 90), ("due", "Due", 90))
        self.out_tree = ttk.Treeview(right, columns=[c[0] for c in cols],
                                     show="headings", height=20)
        for key, text, width in cols:
            self.out_tree.heading(key, text=text)
            self.out_tree.column(key, width=width, anchor="w")
        osb = ttk.Scrollbar(right, orient="vertical",
                            command=self.out_tree.yview)
        self.out_tree.configure(yscrollcommand=osb.set)
        osb.pack(side="right", fill="y")
        self.out_tree.pack(side="left", fill="both", expand=True)
        self.out_tree.tag_configure("overdue", foreground="#a33")

    def refresh(self) -> None:
        try:
            win = int(self.window_e.get().strip() or "14")
        except ValueError:
            messagebox.showerror("Summary",
                                    "Window must be a number.")
            return
        summ = data.summary(upcoming_window_days=win)
        lines = [
            f"Total checklists   : {summ.total_checklists}",
            f"Open               : {summ.open_count}",
            f"Completed          : {summ.completed_count}",
            f"Overdue            : {summ.overdue}",
            f"Upcoming due ({win}d){' ' * (8 - len(str(win)))}: "
            f"{summ.upcoming_due}",
            "",
            f"Items total        : {summ.items_total}",
            f"Items done         : {summ.items_done}",
            f"Items overdue      : {summ.items_overdue}",
            "",
            "By checklist status:",
        ]
        for s in CHECKLIST_STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("Items by category:")
        for c in CATEGORIES:
            n = summ.by_category.get(c, 0)
            if n:
                lines.append(f"  {c:<24} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")
        self._outstanding()

    def _outstanding(self) -> None:
        for i in self.out_tree.get_children():
            self.out_tree.delete(i)
        try:
            checklists = {c.checklist_id: c
                          for c in data.list_checklists(open_only=True)}
            items = [it for it in data.list_items(required_only=True)
                     if not it.is_done and it.checklist_id in checklists]
            names = _name_lookup()
        except Exception as e:  # noqa: BLE001 — shown in the list
            logger.exception("Outstanding onboarding items failed to load")
            self.out_tree.insert("", "end", values=("", f"Error: {e}",
                                                    "", "", "", ""))
            return
        today = _today()
        items.sort(key=lambda it: (it.due_date or "9999",
                                   checklists[it.checklist_id].student_id))
        for it in items:
            c = checklists[it.checklist_id]
            late = bool(it.due_date and it.due_date < today)
            self.out_tree.insert("", "end", values=(
                c.student_id, names.get(c.student_id, ""), c.name,
                it.task_name, it.status, it.due_date or "—"),
                tags=("overdue",) if late else ())


# ══ Dialogs ═══════════════════════════════════════════════════════

class ChecklistDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Checklist | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self._choice = None          # workflow.TemplateChoice from Suggest
        self.win = make_toplevel(parent)
        self.win.title("Edit Checklist" if existing else "New Checklist")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                 sticky="e", pady=4)
        if self.existing:
            self._student_id = self.existing.student_id
            self.student_cb = None
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{self._student_id} — "
                             f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                form, values=[l for _, l in opts],
                state="readonly", width=44)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Template:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        if self.existing:
            ttk.Label(form,
                       text=self.existing.template_name or "—"
                       ).grid(row=r, column=1, sticky="w", padx=6)
            self.template_cb = None
        else:
            tbox = ttk.Frame(form)
            tbox.grid(row=r, column=1, columnspan=2, sticky="w", padx=6)
            try:
                names = tpl.template_names()
            except Exception:  # noqa: BLE001 — the default is still offered
                logger.exception("Onboarding template names failed to load")
                names = [DEFAULT_TEMPLATE]
            self.template_cb = ttk.Combobox(tbox, values=names,
                                            state="readonly", width=30)
            self.template_cb.set(DEFAULT_TEMPLATE)
            self.template_cb.pack(side="left")
            ttk.Button(tbox, text="Suggest",
                       command=self._suggest).pack(side="left", padx=6)
            r += 1
            self.addons_var = tk.BooleanVar(value=True)
            self.addons_chk = ttk.Checkbutton(
                form, variable=self.addons_var,
                text="Also add the suggested add-ons: (none)")
            self.addons_chk.grid(row=r, column=1, columnspan=2, sticky="w",
                                 padx=6)
            self.addons_chk.state(["disabled"])

        r += 1
        ttk.Label(form, text="Academic year:").grid(row=r, column=0,
                                                       sticky="e", pady=4)
        self.year_e = self.enrol_e = None
        if self.existing:
            eid = self.existing.enrolment_id
            ttk.Label(form, text=(
                f"{self.existing.academic_year or '—'}   ·   enrolment "
                f"{('#' + str(eid)) if eid else 'not linked'}")).grid(
                row=r, column=1, sticky="w", padx=6)
        else:
            self.year_e = ttk.Entry(form, width=14)
            self.year_e.grid(row=r, column=1, sticky="w", padx=6)
            ttk.Label(form, text="(blank = the enrolment's year, else the "
                                 "current year)",
                      foreground="#888").grid(row=r, column=2, sticky="w")
            r += 1
            ttk.Label(form, text="Enrolment #:").grid(row=r, column=0,
                                                     sticky="e", pady=4)
            self.enrol_e = ttk.Entry(form, width=10)
            self.enrol_e.grid(row=r, column=1, sticky="w", padx=6)
            ttk.Label(form, text="(optional link)",
                      foreground="#888").grid(row=r, column=2, sticky="w")

        r += 1
        ttk.Label(form, text="Name:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=44)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        self.name_e.grid(row=r, column=1, sticky="w", padx=6)
        if not self.existing:
            ttk.Label(form, text="(blank = auto)",
                       foreground="#888").grid(row=r, column=2,
                                                  sticky="w")

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(
            form, values=(CHECKLIST_STATUSES if self.existing
                          else ("Not Started", "In Progress")),
            state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_CHECKLIST_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Started on:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.started_on:
            self.start_e.insert(0, self.existing.started_on)
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Due date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.due_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.due_date:
            self.due_e.insert(0, self.existing.due_date)
        self.due_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Assigned to:").grid(row=r, column=0,
                                                     sticky="e", pady=4)
        self.assigned_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.assigned_to:
            self.assigned_e.insert(0, self.existing.assigned_to)
        self.assigned_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _suggest(self) -> None:
        """workflow.choose_template for the chosen learner: sets the
        template and offers the add-ons, showing why."""
        idx = self.student_cb.current() if self.student_cb else -1
        if idx < 0:
            messagebox.showinfo("Suggest", "Select a student first.",
                                parent=self.win)
            return
        from education_system.systems.sixth_form.domain.admissions.onboarding import (
            workflow,
        )
        try:
            choice = workflow.choose_template(self._student_ids[idx])
        except Exception as e:  # noqa: BLE001 — ValidationError shown
            messagebox.showerror("Suggest", str(e), parent=self.win)
            return
        self._choice = choice
        if choice.template in self.template_cb.cget("values"):
            self.template_cb.set(choice.template)
        addons = ", ".join(choice.addons) or "(none)"
        self.addons_chk.configure(
            text=f"Also add the suggested add-ons: {addons}")
        self.addons_chk.state(["!disabled"] if choice.addons
                              else ["disabled"])
        lines = [f"Suggested: {choice.template}  ({choice.label})", "",
                 "Why:"] + [f"• {x}" for x in choice.reasons or ["(default)"]]
        if choice.addons:
            lines += ["", "Add-ons:"] + [f"• {a}" for a in choice.addons]
        if choice.not_applicable:
            lines += ["", "Add-on tasks that will be marked N/A:"] + [
                f"• {k}: {v}" for k, v in choice.not_applicable.items()]
        if choice.not_checked:
            lines += ["", "Not checked (could not be read):"] + [
                f"• {x}" for x in choice.not_checked]
        messagebox.showinfo("Suggested template", "\n".join(lines),
                            parent=self.win)

    def _apply_addons(self, checklist_id: int) -> list[str]:
        """After creating: add the suggested add-ons and mark add-on tasks
        that do not apply N/A (with the reason). Returns problems."""
        choice = self._choice
        if choice is None or not self.addons_var.get() or not choice.addons:
            return []
        problems: list[str] = []
        for name in choice.addons:
            try:
                tpl.apply_template(checklist_id, name)
            except Exception as e:  # noqa: BLE001
                problems.append(f"{name}: {e}")
        for item in data.list_items(checklist_id=checklist_id):
            why = choice.not_applicable.get(item.key)
            if why and item.status == "Pending":
                try:
                    data.set_item_status(item.item_id, "N/A", reason=why)
                except Exception as e:  # noqa: BLE001
                    problems.append(f"{item.task_name}: {e}")
        return problems

    def _collect(self) -> dict:
        if self.existing:
            sid = self._student_id
            template = self.existing.template_name
        elif self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                raise ValidationError("Select a student")
            sid = self._student_ids[idx]
            template = (self.template_cb.get()
                         if self.template_cb else "")
        else:
            raise ValidationError("Select a student")
        out = {}
        if self.year_e is not None:
            year = self.year_e.get().strip()
            if year:
                out["academic_year"] = year
        if self.enrol_e is not None:
            eid = self.enrol_e.get().strip().lstrip("#")
            if eid:
                if not eid.isdigit():
                    raise ValidationError("Enrolment # must be a number")
                out["enrolment_id"] = int(eid)
        return {
            **out,
            "student_id":    sid,
            "template_name": template,
            "name":          self.name_e.get().strip() or None,
            "status":        self.status_cb.get().strip(),
            "started_on":    self.start_e.get().strip() or None,
            "due_date":      self.due_e.get().strip() or None,
            "assigned_to":   self.assigned_e.get().strip() or None,
            "notes":         self.notes_t.get("1.0", "end").strip() or None,
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                status = payload["status"]
                if (status != self.existing.status
                        and status in ("Cancelled", "On Hold")):
                    reason = _ask_status_reason(self.win, status)
                    if reason is None:
                        return
                    payload["status_reason"] = reason
                data.update_checklist(self.existing.checklist_id,
                                        payload)
            else:
                if self._choice is not None and \
                        payload["template_name"] == self._choice.template:
                    payload["learner_type"] = self._choice.label
                chk = data.create_checklist(payload)
                problems = self._apply_addons(chk.checklist_id)
                if problems:
                    messagebox.showwarning(
                        "Add-ons", "The checklist was made, but:\n"
                        + "\n".join(problems), parent=self.win)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


def _ask_status_reason(parent: tk.Misc, status: str,
                       initial: str = "") -> str | None:
    return actions.prompt_text(
        parent, f"Checklist {status.lower()}",
        f"Say why the checklist is {status.lower()}.", label="Reason:",
        initial=initial, min_chars=3)


class ChecklistStatusDialog:
    """Checklist status. Completed needs every required task done;
    Cancelled and On Hold need a reason (the domain enforces both and its
    message is shown)."""

    def __init__(self, parent: tk.Misc, existing: Checklist,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = make_toplevel(parent)
        self.win.title(f"Status — checklist #{existing.checklist_id}")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=CHECKLIST_STATUSES,
                                  state="readonly", width=18)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Reason:").grid(row=1, column=0,
                                                sticky="ne", pady=4)
        self.reason_t = tk.Text(form, width=48, height=3, wrap="word")
        if existing.status_reason:
            self.reason_t.insert("1.0", existing.status_reason)
        self.reason_t.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, foreground="#777", text=(
            "Needed for Cancelled or On Hold. Completed needs every "
            "required task done or N/A.")).grid(row=2, column=1,
                                                 sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        status = self.cb.get()
        reason = self.reason_t.get("1.0", "end").strip() or None
        try:
            data.update_checklist(self.existing.checklist_id,
                                  {"status": status, "status_reason": reason})
        except Exception as e:  # noqa: BLE001 — ValidationError / AccessDenied
            messagebox.showerror("Save failed", str(e), parent=self.win)
            return
        self.win.destroy()
        self.on_save()


class ItemStatusDialog:
    """Pick a status; Done / N/A / Blocked then ask for whatever the
    evidence rules need (see onboarding_actions.change_status)."""

    def __init__(self, parent: tk.Misc, existing: Item,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = make_toplevel(parent)
        self.win.title(f"Status — item #{existing.item_id}")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"Task: {existing.task_name}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="New status:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=ITEM_STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Completed by:").grid(row=2, column=0,
                                                      sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if existing.completed_by:
            self.by_e.insert(0, existing.completed_by)
        self.by_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(form, foreground="#777", wraplength=360, justify="left",
                  text=("Done asks for evidence when the record is not on "
                        "file; N/A and Blocked ask for a reason. Notes are "
                        "never evidence.")).grid(row=3, column=0,
                                                 columnspan=2, sticky="w")
        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        status = self.cb.get()
        if status == self.existing.status:
            self.win.destroy()
            return
        out = actions.change_status(
            self.win, self.existing, status,
            completed_by=self.by_e.get().strip() or _username())
        if out is None:
            return
        self.win.destroy()
        self.on_save()


class ItemDialog:
    def __init__(self, parent: tk.Misc, *,
                 checklist_id: int,
                 existing: Item | None,
                 on_save: Callable[[], None]) -> None:
        self.checklist_id = checklist_id
        self.existing = existing
        self.on_save = on_save
        self.win = make_toplevel(parent)
        self.win.title("Edit Item" if existing else "New Item")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="Task:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.task_e = ttk.Entry(form, width=44)
        if self.existing:
            self.task_e.insert(0, self.existing.task_name)
        self.task_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Category:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.cat_cb = ttk.Combobox(form, values=CATEGORIES,
                                      state="readonly", width=22)
        self.cat_cb.set(self.existing.category if self.existing
                           else DEFAULT_CATEGORY)
        self.cat_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        self.required_var = tk.BooleanVar(
            value=(self.existing.required if self.existing else True))
        ttk.Checkbutton(form, text="Required for completion",
                          variable=self.required_var).grid(
            row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=ITEM_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_ITEM_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Due date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.due_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.due_date:
            self.due_e.insert(0, self.existing.due_date)
        self.due_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Completed by:").grid(row=r, column=0,
                                                      sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.completed_by:
            self.by_e.insert(0, self.existing.completed_by)
        self.by_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=3)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        """Save the task's details, then move its status (if changed)
        through the evidence rules — so Done / N/A / Blocked ask for
        evidence or a reason exactly as the Status button does."""
        status = self.status_cb.get().strip()
        by = self.by_e.get().strip() or _username()
        payload = {
            "checklist_id": self.checklist_id,
            "task_name":    self.task_e.get().strip(),
            "category":     self.cat_cb.get().strip(),
            "required":     self.required_var.get(),
            "due_date":     self.due_e.get().strip() or None,
            "notes":        self.notes_t.get("1.0", "end").strip() or None,
        }
        try:
            if self.existing:
                item = data.update_item(self.existing.item_id, payload)
            else:
                item = data.create_item({**payload,
                                         "status": DEFAULT_ITEM_STATUS})
        except Exception as e:  # noqa: BLE001 — ValidationError / AccessDenied
            messagebox.showerror("Save failed", str(e), parent=self.win)
            return
        self.existing = item
        if status and status != item.status:
            if actions.change_status(self.win, item, status,
                                     completed_by=by) is None:
                messagebox.showinfo(
                    "Status not changed",
                    f"The task's details were saved; it is still "
                    f"{item.status}.", parent=self.win)
        self.win.destroy()
        self.on_save()
