"""Tkinter views for Sixth Form Intervention Tracking.

Three tabs: Interventions (with sessions detail), All Sessions, Summary.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.assessment.intervention_tracking import (
    intervention_tracking as data,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.post_16.sixthform_system.modules.domain.assessment.intervention_tracking.intervention_tracking import (
    DEFAULT_DELIVERY_MODE,
    DEFAULT_FREQUENCY,
    DEFAULT_INTERVENTION_TYPE,
    DEFAULT_SESSION_STATUS,
    DEFAULT_STATUS,
    DELIVERY_MODES,
    FREQUENCIES,
    IMPACT_GRADES,
    INTERVENTION_TYPES,
    Intervention,
    SESSION_STATUSES,
    STATUSES,
    Session,
    ValidationError,
    impact_label,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_intervention_tracking_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Intervention Tracking — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    InterventionsTab(nb)
    SessionsTab(nb)
    SummaryTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name
             for s in student_data.list_students()}


def _subject_options() -> list[str]:
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        return [s.name for s in _subjects.list_subjects()]
    except Exception:
        return []


# ══ Interventions tab ═════════════════════════════════════════════

class InterventionsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Interventions")
        self._selected_id: int | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + INTERVENTION_TYPES,
                                     state="readonly", width=20)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Lead:").pack(side="left")
        self.f_lead = ttk.Entry(bar, width=12)
        self.f_lead.pack(side="left", padx=(2, 8))

        self.open_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Open only",
                          variable=self.open_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        pane = ttk.Panedwindow(self.frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=4)

        left = ttk.Frame(pane)
        pane.add(left, weight=3)
        cols = ("id", "student", "name", "type", "subject",
                "status", "impact", "atten", "title")
        self.tree = ttk.Treeview(left, columns=cols, show="headings")
        widths = {"id": 50, "student": 80, "name": 140,
                  "type": 130, "subject": 110,
                  "status": 100, "impact": 60, "atten": 80,
                  "title": 220}
        headings = {"id": "ID", "student": "Stu", "name": "Name",
                    "type": "Type", "subject": "Subject",
                    "status": "Status", "impact": "Impact",
                    "atten": "Att", "title": "Title"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = ("center" if c in ("impact", "atten") else "w")
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(left, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Active",    background="#d8f4d8")
        self.tree.tag_configure("Planned",   background="#eef7ff")
        self.tree.tag_configure("Paused",    background="#fff7d0")
        self.tree.tag_configure("Completed", background="#cce8cc")
        self.tree.tag_configure("Withdrawn", background="#eeeeee")
        self.tree.tag_configure("Cancelled", background="#ffd0d0")
        self.tree.bind("<<TreeviewSelect>>",
                        lambda _e: self._on_select())
        self.tree.bind("<Double-1>",
                        lambda _e: self._edit_selected())

        right = ttk.Frame(pane)
        pane.add(right, weight=2)
        self.detail_var = tk.StringVar(
            value="Select an intervention on the left.")
        ttk.Label(right, textvariable=self.detail_var,
                   font=("", 11, "bold"),
                   anchor="w").pack(fill="x", padx=2, pady=(0, 4))
        self.subdetail_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.subdetail_var,
                   foreground="#555",
                   anchor="w").pack(fill="x", padx=2, pady=(0, 6))

        s_cols = ("id", "date", "status", "mins",
                   "delivered", "topic")
        self.sess_tree = ttk.Treeview(right, columns=s_cols,
                                          show="headings")
        s_widths = {"id": 50, "date": 100, "status": 100,
                     "mins": 50, "delivered": 130, "topic": 200}
        s_headings = {"id": "ID", "date": "Date",
                        "status": "Status", "mins": "Mins",
                        "delivered": "Delivered by",
                        "topic": "Topic"}
        for c in s_cols:
            self.sess_tree.heading(c, text=s_headings[c])
            anchor = "center" if c == "mins" else "w"
            self.sess_tree.column(c, width=s_widths[c], anchor=anchor)
        svs = ttk.Scrollbar(right, orient="vertical",
                              command=self.sess_tree.yview)
        self.sess_tree.configure(yscrollcommand=svs.set)
        self.sess_tree.pack(side="left", fill="both", expand=True)
        svs.pack(side="right", fill="y")
        self.sess_tree.tag_configure("Attended",
                                          background="#d8f4d8")
        self.sess_tree.tag_configure("Late",
                                          background="#fff7d0")
        self.sess_tree.tag_configure("Partial",
                                          background="#fff7d0")
        self.sess_tree.tag_configure("Absent",
                                          background="#ffd0d0")
        self.sess_tree.tag_configure("Cancelled",
                                          background="#eeeeee")
        self.sess_tree.tag_configure("Rescheduled",
                                          background="#eef7ff")

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left")
        ttk.Button(actions, text="Complete with impact",
                    command=self._complete).pack(side="left", padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Delete intervention",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Log session",
                    command=self._log_session).pack(side="left",
                                                      padx=(16, 4))
        ttk.Button(actions, text="Edit session",
                    command=self._edit_session).pack(side="left",
                                                       padx=2)
        ttk.Button(actions, text="Delete session",
                    command=self._delete_session).pack(side="left",
                                                         padx=2)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_type.current(0)
        self.f_status.current(0)
        self.f_lead.delete(0, "end")
        self.open_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_interventions_with_detail(
                student_id=self.f_student.get().strip() or None,
                intervention_type=self.f_type.get() or None,
                status=self.f_status.get() or None,
                lead_like=self.f_lead.get().strip() or None,
                open_only=self.open_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for r in rows:
            iv = r.intervention
            att = f"{r.sessions_attended}/{r.sessions_total}"
            tags = (iv.status,) if iv.status in STATUSES else ()
            self.tree.insert("", "end",
                                  iid=str(iv.intervention_id), values=(
                iv.intervention_id, iv.student_id,
                r.student_name, iv.intervention_type,
                iv.subject_name or "—", iv.status,
                iv.impact_grade if iv.impact_grade is not None else "—",
                att, iv.title,
            ), tags=tags)
        self.count_var.set(f"{len(rows)} intervention(s).")

        if (self._selected_id is not None
                and self.tree.exists(str(self._selected_id))):
            self.tree.selection_set(str(self._selected_id))
            self._render_detail()
        else:
            self._selected_id = None
            self._clear_detail()

    def _on_select(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            self._selected_id = int(sel[0])
        except ValueError:
            return
        self._render_detail()

    def _clear_detail(self) -> None:
        for i in self.sess_tree.get_children():
            self.sess_tree.delete(i)
        self.detail_var.set(
            "Select an intervention on the left.")
        self.subdetail_var.set("")

    def _render_detail(self) -> None:
        for i in self.sess_tree.get_children():
            self.sess_tree.delete(i)
        if self._selected_id is None:
            return
        det = data.get_intervention_detail(self._selected_id)
        if det is None:
            self._clear_detail()
            return
        iv = det.intervention
        self.detail_var.set(
            f"#{iv.intervention_id}  {iv.title}")
        sub_bits = [
            f"{iv.student_id} — {det.student_name}",
            f"{iv.intervention_type}",
            (f"Subject: {iv.subject_name}"
                if iv.subject_name else "Subject: —"),
            f"Lead: {iv.lead_staff or '—'}",
            f"Status: {iv.status}",
            (f"Sessions: {det.sessions_attended}/"
                f"{len(det.sessions)}"
                + (f"  ({det.attendance_pct}%)"
                   if det.attendance_pct is not None else "")),
            f"Mins: {det.total_minutes}",
            (f"Impact: {iv.impact_grade}"
                + f" ({iv.impact_label})"
                if iv.impact_grade else "Impact: —"),
        ]
        self.subdetail_var.set("  ·  ".join(sub_bits))
        for s in det.sessions:
            tags = (s.status,) if s.status in SESSION_STATUSES else ()
            self.sess_tree.insert("", "end",
                                       iid=str(s.session_id), values=(
                s.session_id, s.session_date,
                s.status,
                s.duration_minutes
                    if s.duration_minutes is not None else "—",
                s.delivered_by or "—",
                s.topic or "—",
            ), tags=tags)

    def _selected(self) -> Intervention | None:
        if self._selected_id is None:
            return None
        return data.get_intervention(self._selected_id)

    def _selected_session_id(self) -> int | None:
        sel = self.sess_tree.selection()
        if not sel:
            return None
        return int(sel[0])

    # ── Intervention actions ──────────────────────────────────────
    def _new(self) -> None:
        InterventionDialog(self.frame.winfo_toplevel(),
                              existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        iv = self._selected()
        if iv is None:
            messagebox.showinfo("Edit",
                                  "Select an intervention first.")
            return
        InterventionDialog(self.frame.winfo_toplevel(),
                              existing=iv, on_save=self.refresh)

    def _complete(self) -> None:
        iv = self._selected()
        if iv is None:
            messagebox.showinfo("Complete",
                                  "Select an intervention first.")
            return
        CompleteDialog(self.frame.winfo_toplevel(),
                          iv, on_save=self.refresh)

    def _status_selected(self) -> None:
        iv = self._selected()
        if iv is None:
            messagebox.showinfo("Status",
                                  "Select an intervention first.")
            return
        StatusDialog(self.frame.winfo_toplevel(),
                       iv, on_save=self.refresh)

    def _delete_selected(self) -> None:
        iv = self._selected()
        if iv is None:
            messagebox.showinfo("Delete",
                                  "Select an intervention first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete intervention #{iv.intervention_id}? "
                "Cascade-deletes sessions."):
            return
        try:
            data.delete_intervention(iv.intervention_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self._selected_id = None
        self.refresh()

    # ── Session actions ───────────────────────────────────────────
    def _log_session(self) -> None:
        iv = self._selected()
        if iv is None:
            messagebox.showinfo("Session",
                                  "Select an intervention first.")
            return
        SessionDialog(self.frame.winfo_toplevel(),
                        intervention=iv, existing=None,
                        on_save=self.refresh)

    def _edit_session(self) -> None:
        sid = self._selected_session_id()
        if sid is None:
            messagebox.showinfo("Session",
                                  "Select a session first.")
            return
        existing = data.get_session(sid)
        if existing is None:
            return
        iv = self._selected()
        if iv is None:
            return
        SessionDialog(self.frame.winfo_toplevel(),
                        intervention=iv, existing=existing,
                        on_save=self.refresh)

    def _delete_session(self) -> None:
        sid = self._selected_session_id()
        if sid is None:
            messagebox.showinfo("Delete",
                                  "Select a session first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete session #{sid}?"):
            return
        try:
            data.delete_session(sid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Sessions tab ══════════════════════════════════════════════════

class SessionsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="All Sessions")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + SESSION_STATUSES,
            state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="From:").pack(side="left")
        self.f_from = ttk.Entry(bar, width=12)
        self.f_from.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="To:").pack(side="left")
        self.f_to = ttk.Entry(bar, width=12)
        self.f_to.pack(side="left", padx=(2, 10))

        self.attended_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Attended only",
                          variable=self.attended_var,
                          command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "iv", "student", "title",
                "date", "status", "mins", "delivered", "topic")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "iv": 50, "student": 80,
                  "title": 200, "date": 100, "status": 100,
                  "mins": 50, "delivered": 130, "topic": 200}
        headings = {"id": "ID", "iv": "Iv",
                    "student": "Student", "title": "Intervention",
                    "date": "Date", "status": "Status",
                    "mins": "Mins", "delivered": "Delivered by",
                    "topic": "Topic"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "mins" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Attended", background="#d8f4d8")
        self.tree.tag_configure("Late",     background="#fff7d0")
        self.tree.tag_configure("Absent",   background="#ffd0d0")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_sessions_with_detail(
                status=self.f_status.get() or None,
                attended_only=self.attended_var.get(),
                date_from=self.f_from.get().strip() or None,
                date_to=self.f_to.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for r in rows:
            s = r.session
            tags = (s.status,) if s.status in SESSION_STATUSES else ()
            self.tree.insert("", "end", iid=str(s.session_id), values=(
                s.session_id, s.intervention_id,
                r.student_id, r.intervention_title,
                s.session_date, s.status,
                s.duration_minutes
                    if s.duration_minutes is not None else "—",
                s.delivered_by or "—",
                s.topic or "—",
            ), tags=tags)
        self.count_var.set(f"{len(rows)} session(s).")


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        ttk.Button(self.frame, text="Refresh",
                    command=self.refresh).pack(side="top", anchor="w",
                                                 padx=8, pady=(8, 4))
        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        summ = data.summary()
        lines = [
            f"Total interventions  : {summ.total}",
            f"Open                 : {summ.open_count}",
            f"Distinct students    : {summ.distinct_students}",
            f"Total sessions       : {summ.total_sessions}",
            f"Attended             : {summ.attended_sessions}",
            f"Total minutes        : {summ.total_minutes}",
            f"Average impact       : "
            f"{summ.average_impact if summ.average_impact is not None else '—'}",
            "",
            "By status:",
        ]
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("By type:")
        for t in INTERVENTION_TYPES:
            n = summ.by_type.get(t, 0)
            if n:
                lines.append(f"  {t:<22} : {n}")
        lines.append("")
        lines.append("By impact grade:")
        for g in IMPACT_GRADES:
            n = summ.by_impact.get(g, 0)
            if n:
                lines.append(
                    f"  {g}  {impact_label(g):<22} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: Intervention,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Status — intervention #{existing.intervention_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_status(self.existing.intervention_id,
                               self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class CompleteDialog:
    def __init__(self, parent: tk.Misc, existing: Intervention,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Complete — intervention #{existing.intervention_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form,
                   text=f"Baseline: {existing.baseline_indicator or '—'}",
                   foreground="#555").grid(row=0, column=0,
                                              columnspan=2,
                                              sticky="w",
                                              pady=(0, 8))

        ttk.Label(form, text="Exit indicator:").grid(row=1, column=0,
                                                        sticky="e", pady=4)
        self.exit_e = ttk.Entry(form, width=40)
        if existing.exit_indicator:
            self.exit_e.insert(0, existing.exit_indicator)
        self.exit_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Impact grade:").grid(row=2, column=0,
                                                      sticky="e", pady=4)
        self.impact_cb = ttk.Combobox(
            form, values=("",) + tuple(str(g) for g in IMPACT_GRADES),
            state="readonly", width=8)
        self.impact_cb.set(str(existing.impact_grade)
                              if existing.impact_grade is not None
                              else "")
        self.impact_cb.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Impact summary:").grid(row=3, column=0,
                                                        sticky="ne", pady=4)
        self.summary_t = tk.Text(form, width=44, height=4)
        if existing.impact_summary:
            self.summary_t.insert("1.0", existing.impact_summary)
        self.summary_t.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="End date:").grid(row=4, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        self.end_e.insert(0, existing.end_date or _today())
        self.end_e.grid(row=4, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Complete",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        impact_raw = self.impact_cb.get().strip()
        impact: int | None = None
        if impact_raw:
            try:
                impact = int(impact_raw)
            except ValueError:
                messagebox.showerror("Complete",
                                        "Impact must be 1-4.")
                return
        try:
            data.complete_intervention(
                self.existing.intervention_id,
                exit_indicator=self.exit_e.get().strip() or None,
                impact_grade=impact,
                impact_summary=self.summary_t.get(
                    "1.0", "end").strip() or None,
                end_date=self.end_e.get().strip() or None,
            )
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class SessionDialog:
    def __init__(self, parent: tk.Misc, *,
                 intervention: Intervention,
                 existing: Session | None,
                 on_save: Callable[[], None]) -> None:
        self.intervention = intervention
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Session" if existing
                          else "Log Session")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"Intervention: #{self.intervention.intervention_id} "
                         f"{self.intervention.title}",
                   font=("", 10, "bold"),
                   wraplength=420).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(form, text="Date:").grid(row=1, column=0,
                                              sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, (self.existing.session_date
                                  if self.existing else _today()))
        self.date_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Duration (mins):").grid(row=2, column=0,
                                                          sticky="e", pady=4)
        self.duration_e = ttk.Entry(form, width=8)
        self.duration_e.insert(
            0, (str(self.existing.duration_minutes)
                if self.existing
                  and self.existing.duration_minutes is not None
                else "45"))
        self.duration_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Status:").grid(row=3, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=SESSION_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_SESSION_STATUS)
        self.status_cb.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Delivered by:").grid(row=4, column=0,
                                                      sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        default_by = ((self.existing.delivered_by
                         if self.existing
                           and self.existing.delivered_by
                         else self.intervention.lead_staff) or "")
        if default_by:
            self.by_e.insert(0, default_by)
        self.by_e.grid(row=4, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Topic:").grid(row=5, column=0,
                                               sticky="e", pady=4)
        self.topic_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.topic:
            self.topic_e.insert(0, self.existing.topic)
        self.topic_e.grid(row=5, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Notes:").grid(row=6, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=6, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=7, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        duration_raw = self.duration_e.get().strip()
        try:
            duration = int(duration_raw) if duration_raw else None
        except ValueError:
            raise ValidationError(
                "Duration must be a whole number") from None
        return {
            "intervention_id":  self.intervention.intervention_id,
            "session_date":     self.date_e.get().strip(),
            "duration_minutes": duration,
            "status":           self.status_cb.get().strip(),
            "delivered_by":     self.by_e.get().strip() or None,
            "topic":            self.topic_e.get().strip() or None,
            "notes":            self.notes_t.get(
                                    "1.0", "end").strip() or None,
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_session(
                    self.existing.session_id, payload)
            else:
                data.create_session(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class InterventionDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Intervention | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Intervention" if existing
                          else "New Intervention")
        self.win.transient(parent)
        self.win.geometry("900x720")
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill="both", expand=True)
        meta = ttk.LabelFrame(outer, text="Details", padding=8)
        meta.pack(fill="x", pady=(0, 6))
        r = 0

        ttk.Label(meta, text="Student:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        if self.existing:
            self._student_id = self.existing.student_id
            self.student_cb = None
            names = _name_lookup()
            ttk.Label(meta,
                       text=f"{self._student_id} — "
                             f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, columnspan=3,
                               sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                meta, values=[l for _, l in opts],
                state="readonly", width=44)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, columnspan=3,
                                    sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Title:").grid(row=r, column=0,
                                               sticky="e", pady=3)
        self.title_e = ttk.Entry(meta, width=44)
        if self.existing:
            self.title_e.insert(0, self.existing.title)
        self.title_e.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Type:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.type_cb = ttk.Combobox(meta, values=INTERVENTION_TYPES,
                                       state="readonly", width=22)
        self.type_cb.set(self.existing.intervention_type
                            if self.existing
                            else DEFAULT_INTERVENTION_TYPE)
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Subject:").grid(row=r, column=2,
                                                 sticky="e", pady=3)
        self.subject_cb = ttk.Combobox(
            meta, values=("",) + tuple(_subject_options()),
            width=22)
        if self.existing:
            self.subject_cb.set(self.existing.subject_name or "")
        self.subject_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Lead:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.lead_e = ttk.Entry(meta, width=26)
        if self.existing and self.existing.lead_staff:
            self.lead_e.insert(0, self.existing.lead_staff)
        self.lead_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Status:").grid(row=r, column=2,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(meta, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Mode:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.mode_cb = ttk.Combobox(meta, values=("",) + DELIVERY_MODES,
                                       state="readonly", width=18)
        self.mode_cb.set(self.existing.delivery_mode
                            if self.existing
                              and self.existing.delivery_mode
                            else DEFAULT_DELIVERY_MODE)
        self.mode_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Frequency:").grid(row=r, column=2,
                                                   sticky="e", pady=3)
        self.freq_cb = ttk.Combobox(meta, values=("",) + FREQUENCIES,
                                       state="readonly", width=14)
        self.freq_cb.set(self.existing.frequency
                            if self.existing
                              and self.existing.frequency
                            else DEFAULT_FREQUENCY)
        self.freq_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Location:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.loc_e = ttk.Entry(meta, width=20)
        if self.existing and self.existing.location:
            self.loc_e.insert(0, self.existing.location)
        self.loc_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Sessions planned:").grid(row=r, column=2,
                                                          sticky="e",
                                                          pady=3)
        self.planned_e = ttk.Entry(meta, width=8)
        if (self.existing
                and self.existing.sessions_planned is not None):
            self.planned_e.insert(0,
                                      str(self.existing.sessions_planned))
        self.planned_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=3)
        self.start_e = ttk.Entry(meta, width=14)
        if self.existing and self.existing.start_date:
            self.start_e.insert(0, self.existing.start_date)
        elif not self.existing:
            self.start_e.insert(0, _today())
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="End date:").grid(row=r, column=2,
                                                  sticky="e", pady=3)
        self.end_e = ttk.Entry(meta, width=14)
        if self.existing and self.existing.end_date:
            self.end_e.insert(0, self.existing.end_date)
        self.end_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Referral source:").grid(row=r, column=0,
                                                          sticky="e",
                                                          pady=3)
        self.referral_e = ttk.Entry(meta, width=26)
        if self.existing and self.existing.referral_source:
            self.referral_e.insert(0, self.existing.referral_source)
        self.referral_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(meta, text="Funding source:").grid(row=r, column=2,
                                                        sticky="e", pady=3)
        self.funding_e = ttk.Entry(meta, width=22)
        if self.existing and self.existing.funding_source:
            self.funding_e.insert(0, self.existing.funding_source)
        self.funding_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(meta, text="Impact grade:").grid(row=r, column=0,
                                                      sticky="e", pady=3)
        self.impact_cb = ttk.Combobox(
            meta, values=("",) + tuple(str(g) for g in IMPACT_GRADES),
            state="readonly", width=8)
        self.impact_cb.set(str(self.existing.impact_grade)
                              if self.existing
                                and self.existing.impact_grade is not None
                              else "")
        self.impact_cb.grid(row=r, column=1, sticky="w", padx=6)

        body_nb = ttk.Notebook(outer)
        body_nb.pack(fill="both", expand=True, pady=6)
        self._body_widgets: dict[str, tk.Text] = {}
        for label, attr in (
                ("Rationale",          "rationale"),
                ("Success criteria",   "success_criteria"),
                ("Baseline indicator", "baseline_indicator"),
                ("Exit indicator",     "exit_indicator"),
                ("Impact summary",     "impact_summary"),
                ("Notes",              "notes"),
        ):
            f = ttk.Frame(body_nb)
            body_nb.add(f, text=label)
            t = tk.Text(f, wrap="word", height=6)
            t.pack(fill="both", expand=True)
            if self.existing:
                v = getattr(self.existing, attr, None)
                if v:
                    t.insert("1.0", v)
            self._body_widgets[attr] = t

        bar = ttk.Frame(outer)
        bar.pack(fill="x")
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        if self.existing:
            sid = self._student_id
        elif self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                raise ValidationError("Pick a student")
            sid = self._student_ids[idx]
        else:
            raise ValidationError("Pick a student")
        payload = {
            "student_id":         sid,
            "title":              self.title_e.get().strip(),
            "intervention_type":  self.type_cb.get().strip(),
            "subject_name":       self.subject_cb.get().strip() or None,
            "lead_staff":         self.lead_e.get().strip(),
            "delivery_mode":      self.mode_cb.get().strip() or None,
            "frequency":          self.freq_cb.get().strip() or None,
            "location":           self.loc_e.get().strip(),
            "start_date":         self.start_e.get().strip(),
            "end_date":           self.end_e.get().strip(),
            "sessions_planned":   self.planned_e.get().strip() or None,
            "status":             self.status_cb.get().strip(),
            "referral_source":    self.referral_e.get().strip(),
            "funding_source":     self.funding_e.get().strip(),
            "impact_grade":       self.impact_cb.get().strip() or None,
        }
        for attr, t in self._body_widgets.items():
            payload[attr] = t.get("1.0", "end").strip()
        return payload

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_intervention(
                    self.existing.intervention_id, payload)
            else:
                data.create_intervention(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
