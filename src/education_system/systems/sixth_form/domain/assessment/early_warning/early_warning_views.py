"""Tkinter views for Sixth Form Early Warning."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.assessment.early_warning import (
    early_warning as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.assessment.early_warning.early_warning import (
    ALERT_TYPES,
    Alert,
    DEFAULT_ALERT_TYPE,
    DEFAULT_SEVERITY,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    SEVERITIES,
    SOURCES,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_early_warning_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Early Warning — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    AlertsTab(nb, scope="open",     label="Open Alerts")
    AlertsTab(nb, scope="critical", label="Critical / High")
    AlertsTab(nb, scope="all",      label="All Alerts")
    ScanTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name
             for s in student_data.list_students()}


# ══ Alerts tab ════════════════════════════════════════════════════

class AlertsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, values=("",) + ALERT_TYPES,
                                     state="readonly", width=18)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Severity:").pack(side="left")
        self.f_severity = ttk.Combobox(bar, values=("",) + SEVERITIES,
                                         state="readonly", width=10)
        self.f_severity.current(0)
        self.f_severity.pack(side="left", padx=(2, 8))

        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                            state="readonly",
                                            width=14)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None

        ttk.Label(bar, text="Title:").pack(side="left")
        self.f_title = ttk.Entry(bar, width=16)
        self.f_title.pack(side="left", padx=(2, 8))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New alert",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "type", "severity",
                "status", "raised", "age", "source", "title")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "student": 80, "name": 140,
                  "type": 130, "severity": 90, "status": 110,
                  "raised": 100, "age": 60, "source": 130,
                  "title": 220}
        headings = {"id": "ID", "student": "Stu", "name": "Name",
                    "type": "Type", "severity": "Severity",
                    "status": "Status", "raised": "Raised",
                    "age": "Age", "source": "Source",
                    "title": "Title"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "age" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Critical",     background="#ffd0d0")
        self.tree.tag_configure("High",         background="#ffe6d0")
        self.tree.tag_configure("Medium",       background="#fff7d0")
        self.tree.tag_configure("Low",          background="#eef7ff")
        self.tree.tag_configure("Acknowledged", background="#d8f4d8")
        self.tree.tag_configure("Resolved",     background="#eeeeee")
        self.tree.tag_configure("Dismissed",    background="#eeeeee")
        self.tree.tag_configure("Aged",         background="#ffe6e6")
        self.tree.bind("<Double-1>",
                        lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left",
                                                        padx=4)
        ttk.Button(actions, text="Acknowledge",
                    command=self._acknowledge).pack(side="left",
                                                      padx=4)
        ttk.Button(actions, text="Resolve",
                    command=self._resolve).pack(side="left", padx=2)
        ttk.Button(actions, text="Dismiss",
                    command=self._dismiss).pack(side="left", padx=2)
        ttk.Button(actions, text="Escalate",
                    command=self._escalate).pack(side="left", padx=2)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_type.current(0)
        self.f_severity.current(0)
        if self.f_status is not None:
            self.f_status.current(0)
        self.f_title.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        kwargs: dict = {
            "student_id":   self.f_student.get().strip() or None,
            "alert_type":   self.f_type.get() or None,
            "severity":     self.f_severity.get() or None,
            "title_like":   self.f_title.get().strip() or None,
        }
        if self.scope == "open":
            kwargs["open_only"] = True
        elif self.scope == "critical":
            kwargs["open_only"] = True
            kwargs["min_severity"] = "High"
        else:
            if self.f_status is not None:
                kwargs["status"] = self.f_status.get() or None
        try:
            rows = data.list_alerts(**kwargs)
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for a in rows:
            tags = []
            if a.is_open and a.severity in SEVERITIES:
                tags.append(a.severity)
            elif a.status in ("Acknowledged", "Resolved",
                                 "Dismissed"):
                tags.append(a.status)
            if a.is_open and a.age_days >= 14:
                tags.append("Aged")
            self.tree.insert("", "end", iid=str(a.alert_id), values=(
                a.alert_id, a.student_id,
                names.get(a.student_id, "?"),
                a.alert_type, a.severity, a.status,
                a.raised_on, f"{a.age_days}d",
                a.source, a.title,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} alert(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected(self) -> Alert | None:
        aid = self._selected_id()
        if aid is None:
            return None
        return data.get_alert(aid)

    def _view_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("View",
                                  "Select an alert first.")
            return
        names = _name_lookup()
        lines = [
            f"#{a.alert_id}  {a.title}",
            f"Student         : {a.student_id} — "
            f"{names.get(a.student_id, '?')}",
            f"Type            : {a.alert_type}",
            f"Severity        : {a.severity}",
            f"Status          : {a.status}  (age "
            f"{a.age_days}d)",
            f"Source          : {a.source}",
            f"Raised          : {a.raised_on} by "
            f"{a.raised_by or '—'}",
        ]
        if a.acknowledged_on:
            lines.append(
                f"Acknowledged    : {a.acknowledged_on} by "
                f"{a.acknowledged_by or '—'}")
        if a.resolved_on:
            lines.append(
                f"Resolved        : {a.resolved_on} by "
                f"{a.resolved_by or '—'}")
        if a.trigger_metric:
            lines.append(f"Trigger metric  : {a.trigger_metric}")
        if a.threshold:
            lines.append(f"Threshold       : {a.threshold}")
        if a.linked_ilp_id:
            lines.append(f"Linked ILP      : #{a.linked_ilp_id}")
        if a.linked_intervention_id:
            lines.append(
                f"Linked iv'tion  : #{a.linked_intervention_id}")
        if a.description:
            lines.extend(["", "Description:", a.description])
        if a.action_taken:
            lines.extend(["", "Action taken:", a.action_taken])
        if a.notes:
            lines.extend(["", "Notes:", a.notes])
        messagebox.showinfo(f"Alert #{a.alert_id}",
                              "\n".join(lines))

    def _new(self) -> None:
        AlertDialog(self.frame.winfo_toplevel(),
                      existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Edit",
                                  "Select an alert first.")
            return
        AlertDialog(self.frame.winfo_toplevel(),
                      existing=a, on_save=self.refresh)

    def _acknowledge(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Acknowledge",
                                  "Select an alert first.")
            return
        AckDialog(self.frame.winfo_toplevel(),
                    a, on_save=self.refresh)

    def _resolve(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Resolve",
                                  "Select an alert first.")
            return
        ResolveDialog(self.frame.winfo_toplevel(),
                        a, on_save=self.refresh)

    def _dismiss(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Dismiss",
                                  "Select an alert first.")
            return
        DismissDialog(self.frame.winfo_toplevel(),
                        a, on_save=self.refresh)

    def _escalate(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Escalate",
                                  "Select an alert first.")
            return
        if not messagebox.askyesno(
                "Escalate",
                f"Escalate alert #{a.alert_id}? "
                "Bumps severity up one level."):
            return
        try:
            data.escalate(a.alert_id)
        except ValidationError as e:
            messagebox.showerror("Escalate", str(e))
            return
        self.refresh()

    def _status_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Status",
                                  "Select an alert first.")
            return
        StatusDialog(self.frame.winfo_toplevel(),
                       a, on_save=self.refresh)

    def _delete_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Delete",
                                  "Select an alert first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete alert #{a.alert_id}?"):
            return
        try:
            data.delete_alert(a.alert_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Scan tab ══════════════════════════════════════════════════════

class ScanTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Auto-Scan")
        self._build()

    def _build(self) -> None:
        intro = ttk.LabelFrame(self.frame, text="Auto-Scan",
                                  padding=10)
        intro.pack(fill="x", padx=12, pady=12)
        ttk.Label(
            intro,
            text=("Walks attendance, behaviour, and target-setting "
                  "to auto-raise alerts where measurable thresholds "
                  "are tripped. Existing open alerts of the same "
                  "(student × type × source) are skipped — re-runs "
                  "are idempotent."),
            foreground="#555", wraplength=820,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w",
                pady=(0, 8))

        ttk.Label(intro, text="Attendance window (days):").grid(
            row=1, column=0, sticky="e", pady=4)
        self.att_win_e = ttk.Entry(intro, width=6)
        self.att_win_e.insert(0, "28")
        self.att_win_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(intro, text="Min attendance %:").grid(
            row=1, column=2, sticky="e", pady=4)
        self.att_min_e = ttk.Entry(intro, width=6)
        self.att_min_e.insert(0, "90")
        self.att_min_e.grid(row=1, column=3, sticky="w", padx=6)

        ttk.Label(intro, text="Behaviour window (days):").grid(
            row=2, column=0, sticky="e", pady=4)
        self.beh_win_e = ttk.Entry(intro, width=6)
        self.beh_win_e.insert(0, "28")
        self.beh_win_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(intro, text="Max negatives in window:").grid(
            row=2, column=2, sticky="e", pady=4)
        self.beh_max_e = ttk.Entry(intro, width=6)
        self.beh_max_e.insert(0, "5")
        self.beh_max_e.grid(row=2, column=3, sticky="w", padx=6)

        ttk.Label(intro, text="Raised by:").grid(row=3, column=0,
                                                    sticky="e", pady=4)
        self.by_e = ttk.Entry(intro, width=22)
        self.by_e.insert(0, "Auto Scanner")
        self.by_e.grid(row=3, column=1, sticky="w", padx=6)

        bar = ttk.Frame(intro)
        bar.grid(row=4, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Run scan",
                    command=self._run).pack(side="left")

        self.status_var = tk.StringVar(value="")
        ttk.Label(intro, textvariable=self.status_var,
                   foreground="#444",
                   wraplength=820, justify="left").grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))

    def _run(self) -> None:
        try:
            att_win = int(self.att_win_e.get().strip() or "28")
            att_min = float(self.att_min_e.get().strip() or "90")
            beh_win = int(self.beh_win_e.get().strip() or "28")
            beh_max = int(self.beh_max_e.get().strip() or "5")
        except ValueError:
            messagebox.showerror("Scan",
                                    "Window / threshold values "
                                    "must be numeric.")
            return
        try:
            result = data.scan(
                raised_by=self.by_e.get().strip() or None,
                attendance_window_days=att_win,
                attendance_min_pct=att_min,
                behaviour_window_days=beh_win,
                behaviour_max_negatives=beh_max,
            )
        except Exception as e:
            messagebox.showerror("Scan", str(e))
            return
        lines = [
            f"✓ Created {result.created} alert(s), "
            f"skipped {result.skipped_duplicates} duplicate(s).",
        ]
        if result.sources:
            lines.append("")
            lines.append("By source:")
            for src, n in result.sources.items():
                lines.append(f"  {src}: {n}")
        self.status_var.set("\n".join(lines))


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
            f"Total alerts        : {summ.total}",
            f"Open                : {summ.open_count}",
            f"Critical open       : {summ.critical_open}",
            f"High open           : {summ.high_open}",
            f"Aged ≥ 14d (open)   : {summ.aged_over_14_days}",
            f"Distinct students   : {summ.distinct_students}",
            "",
            "By status:",
        ]
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("By severity:")
        for s in SEVERITIES:
            n = summ.by_severity.get(s, 0)
            if n:
                lines.append(f"  {s:<10} : {n}")
        lines.append("")
        lines.append("By type:")
        for t in ALERT_TYPES:
            n = summ.by_type.get(t, 0)
            if n:
                lines.append(f"  {t:<22} : {n}")
        lines.append("")
        lines.append("By source:")
        for s in SOURCES:
            n = summ.by_source.get(s, 0)
            if n:
                lines.append(f"  {s:<22} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: Alert,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — alert #{existing.alert_id}")
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
            data.set_status(self.existing.alert_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AckDialog:
    def __init__(self, parent: tk.Misc, existing: Alert,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Acknowledge — alert #{existing.alert_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Acknowledged by:").grid(
            row=0, column=0, sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if existing.acknowledged_by:
            self.by_e.insert(0, existing.acknowledged_by)
        self.by_e.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Acknowledge",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.acknowledge(self.existing.alert_id,
                                acknowledged_by=self.by_e.get().strip()
                                                  or None)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ResolveDialog:
    def __init__(self, parent: tk.Misc, existing: Alert,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Resolve — alert #{existing.alert_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Resolved by:").grid(row=0, column=0,
                                                     sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if existing.resolved_by:
            self.by_e.insert(0, existing.resolved_by)
        self.by_e.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Action taken:").grid(row=1, column=0,
                                                      sticky="ne", pady=4)
        self.action_t = tk.Text(form, width=44, height=4)
        if existing.action_taken:
            self.action_t.insert("1.0", existing.action_taken)
        self.action_t.grid(row=1, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Resolve",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.resolve(
                self.existing.alert_id,
                resolved_by=self.by_e.get().strip() or None,
                action_taken=self.action_t.get(
                    "1.0", "end").strip() or None,
            )
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class DismissDialog:
    def __init__(self, parent: tk.Misc, existing: Alert,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Dismiss — alert #{existing.alert_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Dismissed by:").grid(
            row=0, column=0, sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        self.by_e.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Reason:").grid(row=1, column=0,
                                                sticky="ne", pady=4)
        self.reason_t = tk.Text(form, width=44, height=4)
        self.reason_t.grid(row=1, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Dismiss",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.dismiss(
                self.existing.alert_id,
                resolved_by=self.by_e.get().strip() or None,
                reason=self.reason_t.get(
                    "1.0", "end").strip() or None,
            )
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AlertDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Alert | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Alert" if existing else "New Alert")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        if self.existing:
            self._student_id = self.existing.student_id
            self.student_cb = None
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{self._student_id} — "
                             f"{names.get(self._student_id, '?')}"
                       ).grid(row=r, column=1, columnspan=3,
                               sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                form, values=[l for _, l in opts],
                state="readonly", width=44)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, columnspan=3,
                                    sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Title:").grid(row=r, column=0,
                                               sticky="e", pady=3)
        self.title_e = ttk.Entry(form, width=44)
        if self.existing:
            self.title_e.insert(0, self.existing.title)
        self.title_e.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Type:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.type_cb = ttk.Combobox(form, values=ALERT_TYPES,
                                       state="readonly", width=22)
        self.type_cb.set(self.existing.alert_type if self.existing
                            else DEFAULT_ALERT_TYPE)
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Severity:").grid(row=r, column=2,
                                                  sticky="e", pady=3)
        self.sev_cb = ttk.Combobox(form, values=SEVERITIES,
                                      state="readonly", width=10)
        self.sev_cb.set(self.existing.severity if self.existing
                           else DEFAULT_SEVERITY)
        self.sev_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Source:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.src_cb = ttk.Combobox(form, values=SOURCES,
                                      state="readonly", width=22)
        self.src_cb.set(self.existing.source if self.existing
                           else DEFAULT_SOURCE)
        self.src_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Status:").grid(row=r, column=2,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Raised on:").grid(row=r, column=0,
                                                   sticky="e", pady=3)
        self.raised_e = ttk.Entry(form, width=14)
        self.raised_e.insert(0, (self.existing.raised_on
                                    if self.existing
                                    else _dt.date.today().isoformat()))
        self.raised_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Raised by:").grid(row=r, column=2,
                                                   sticky="e", pady=3)
        self.raised_by_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.raised_by:
            self.raised_by_e.insert(0, self.existing.raised_by)
        self.raised_by_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Trigger metric:").grid(row=r, column=0,
                                                        sticky="e", pady=3)
        self.metric_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.trigger_metric:
            self.metric_e.insert(0, self.existing.trigger_metric)
        self.metric_e.grid(row=r, column=1, columnspan=3,
                              sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Threshold:").grid(row=r, column=0,
                                                   sticky="e", pady=3)
        self.threshold_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.threshold:
            self.threshold_e.insert(0, self.existing.threshold)
        self.threshold_e.grid(row=r, column=1, columnspan=3,
                                  sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Linked ILP id:").grid(row=r, column=0,
                                                       sticky="e", pady=3)
        self.ilp_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.linked_ilp_id:
            self.ilp_e.insert(0, str(self.existing.linked_ilp_id))
        self.ilp_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Linked iv'tion id:").grid(row=r, column=2,
                                                             sticky="e",
                                                             pady=3)
        self.iv_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.linked_intervention_id:
            self.iv_e.insert(0,
                               str(self.existing.linked_intervention_id))
        self.iv_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                     sticky="ne", pady=3)
        self.desc_t = tk.Text(form, width=60, height=3)
        if self.existing and self.existing.description:
            self.desc_t.insert("1.0", self.existing.description)
        self.desc_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Action taken:").grid(row=r, column=0,
                                                      sticky="ne", pady=3)
        self.action_t = tk.Text(form, width=60, height=3)
        if self.existing and self.existing.action_taken:
            self.action_t.insert("1.0", self.existing.action_taken)
        self.action_t.grid(row=r, column=1, columnspan=3,
                              sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=60, height=2)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=4, pady=(12, 0))
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
        return {
            "student_id":             sid,
            "title":                  self.title_e.get().strip(),
            "alert_type":             self.type_cb.get().strip(),
            "severity":               self.sev_cb.get().strip(),
            "source":                 self.src_cb.get().strip(),
            "status":                 self.status_cb.get().strip(),
            "raised_on":              self.raised_e.get().strip(),
            "raised_by":              self.raised_by_e.get().strip(),
            "trigger_metric":         self.metric_e.get().strip(),
            "threshold":              self.threshold_e.get().strip(),
            "linked_ilp_id":          self.ilp_e.get().strip() or None,
            "linked_intervention_id": self.iv_e.get().strip() or None,
            "description":            self.desc_t.get(
                                          "1.0", "end").strip(),
            "action_taken":           self.action_t.get(
                                          "1.0", "end").strip(),
            "notes":                  self.notes_t.get(
                                          "1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_alert(self.existing.alert_id, payload)
            else:
                data.create_alert(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
