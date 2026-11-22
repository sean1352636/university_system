"""Job log, Summary, Schedules and Logs tabs of the bulk operations window.

Split out of ``bulk_operations_views.py``, which re-exports every name here.
"""

from __future__ import annotations

from tkinter import ttk
import tkinter as tk

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.platform.delivery.gui.parented_dialogs import simpledialog
from education_system.systems.sixth_form.domain.learners.bulk_operations import base as bulk_base
from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_records as bulk_ops_records
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import OPERATIONS
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import ValidationError

from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.view_common import (
    OPERATION_LABELS,
)
from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.dialogs import (
    JobDetailDialog,
    _ResultDialog,
)


# ══ Job log tab ════════════════════════════════════════════════════

class JobsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Job log")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Operation:").pack(side="left")
        self.f_op = ttk.Combobox(bar, values=("",) + OPERATIONS,
                                    state="readonly", width=20)
        self.f_op.current(0)
        self.f_op.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Limit:").pack(side="left")
        self.f_limit = ttk.Entry(bar, width=6)
        self.f_limit.insert(0, "100")
        self.f_limit.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "ts", "operation", "targets", "ok",
                "fail", "ran_by", "summary")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 60, "ts": 150, "operation": 140,
                  "targets": 70, "ok": 60, "fail": 60,
                  "ran_by": 120, "summary": 500}
        headings = {"id": "ID", "ts": "When",
                    "operation": "Operation", "targets": "Targets",
                    "ok": "OK", "fail": "Fail",
                    "ran_by": "Ran by", "summary": "Summary"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c in ("targets", "ok", "fail") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("hasfail", background="#fff7d0")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            limit = int(self.f_limit.get().strip() or "100")
        except ValueError:
            messagebox.showerror("Limit", "Must be a number.")
            return
        try:
            rows = bulk_base.list_jobs(operation=self.f_op.get() or None,
                                     limit=limit)
        except ValidationError as e:
            messagebox.showerror("Filter", str(e))
            return
        for j in rows:
            tags = ("hasfail",) if j.failure_count else ()
            self.tree.insert("", "end", iid=str(j.job_id), values=(
                j.job_id, j.ran_at, j.operation,
                j.target_count, j.success_count, j.failure_count,
                j.ran_by or "—", j.summary,
            ), tags=tags)
        self.count_var.set(f"{len(rows)} job(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _view_selected(self) -> None:
        jid = self._selected_id()
        if jid is None:
            messagebox.showinfo("View", "Select a job first.")
            return
        j = bulk_base.get_job(jid)
        if j is None:
            return
        JobDetailDialog(self.frame.winfo_toplevel(), j)

    def _delete_selected(self) -> None:
        jid = self._selected_id()
        if jid is None:
            messagebox.showinfo("Delete", "Select a job first.")
            return
        if not messagebox.askyesno("Delete", f"Delete job #{jid}?\n"
                                     "(Audit row only — the actions "
                                     "themselves are not undone.)"):
            return
        try:
            bulk_base.delete_job(jid)
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
        ttk.Button(self.frame, text="Refresh",
                    command=self.refresh).pack(side="top", anchor="w",
                                                 padx=8, pady=(8, 4))
        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        summ = bulk_ops_records.summary()
        lines = [
            f"Total jobs        : {summ.total_jobs}",
            f"Total targets     : {summ.total_targets}",
            f"Total successes   : {summ.total_successes}",
            f"Total failures    : {summ.total_failures}",
            f"Most recent       : {summ.most_recent_ts or '—'}",
            "",
            "By operation:",
        ]
        for op in OPERATIONS:
            n = summ.by_operation.get(op, 0)
            if n:
                lines.append(f"  {OPERATION_LABELS.get(op, op):<24} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Schedules tab ═════════════════════════════════════════════════

class SchedulesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Schedules")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Enable / disable",
                    command=self._toggle).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "on", "name", "operation",
                "cron", "next", "last_job", "by")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "on": 50, "name": 180,
                  "operation": 150, "cron": 140, "next": 130,
                  "last_job": 80, "by": 100}
        heads = {"id": "ID", "on": "Enabled",
                 "name": "Name", "operation": "Operation",
                 "cron": "Cron", "next": "Next run",
                 "last_job": "Last job", "by": "Created by"}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            anchor = "center" if c in ("id", "on", "last_job") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("off", foreground="#888")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = bulk_ops_records.list_schedules()
        for s in rows:
            tags = () if s.enabled else ("off",)
            self.tree.insert("", "end", iid=str(s.schedule_id),
                                values=(s.schedule_id,
                                         "yes" if s.enabled else "no",
                                         s.name, s.operation,
                                         s.cron_expr,
                                         s.next_run_at or "—",
                                         s.last_job_id or "—",
                                         s.created_by or "—"),
                                tags=tags)
        self.count_var.set(f"{len(rows)} schedule(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _toggle(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Toggle", "Select a schedule first.")
            return
        s = bulk_ops_records.get_schedule(sid)
        if s is None:
            return
        try:
            bulk_ops_records.set_schedule_enabled(sid, not s.enabled)
        except ValidationError as e:
            messagebox.showerror("Toggle failed", str(e))
            return
        self.refresh()

    def _delete(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Delete", "Select a schedule first.")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete schedule #{sid}?"):
            return
        bulk_ops_records.delete_schedule(sid)
        self.refresh()


# ══ Logs tab ═══════════════════════════════════════════════════════

class LogsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Logs")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Level:").pack(side="left")
        self.f_level = ttk.Combobox(
            bar, state="readonly", width=10,
            values=("", "DEBUG", "INFO", "WARNING", "ERROR",
                    "CRITICAL"))
        self.f_level.current(0)
        self.f_level.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Operation:").pack(side="left")
        self.f_op = ttk.Combobox(
            bar, state="readonly", width=24,
            values=("",) + OPERATIONS)
        self.f_op.current(0)
        self.f_op.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Limit:").pack(side="left")
        self.f_limit = ttk.Entry(bar, width=6)
        self.f_limit.insert(0, "200")
        self.f_limit.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Clear all…",
                    command=self._clear_all).pack(side="right")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "ts", "level", "operation", "job", "message")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 60, "ts": 140, "level": 70,
                  "operation": 160, "job": 60, "message": 520}
        heads = {"id": "ID", "ts": "When", "level": "Level",
                 "operation": "Operation", "job": "Job",
                 "message": "Message"}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            anchor = ("center"
                      if c in ("id", "level", "job") else "w")
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("warn", background="#fff7d0")
        self.tree.tag_configure("err", background="#ffd6d0")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            limit = int(self.f_limit.get().strip() or "200")
        except ValueError:
            messagebox.showerror("Limit", "Must be a number.")
            return
        try:
            rows = bulk_base.list_logs(
                level=self.f_level.get() or None,
                operation=self.f_op.get() or None,
                limit=limit)
        except ValidationError as e:
            messagebox.showerror("Filter", str(e))
            return
        for r in rows:
            tag = ()
            if r.level in ("ERROR", "CRITICAL"):
                tag = ("err",)
            elif r.level == "WARNING":
                tag = ("warn",)
            self.tree.insert("", "end", iid=str(r.log_id),
                                values=(r.log_id, r.ts, r.level,
                                         r.operation or "—",
                                         r.job_id or "—",
                                         r.message),
                                tags=tag)
        self.count_var.set(f"{len(rows)} log row(s).")

    def _view_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            rows = bulk_base.list_logs(limit=10000)
        except ValidationError:
            return
        target_id = int(sel[0])
        match = next((r for r in rows if r.log_id == target_id), None)
        if not match:
            return
        lines = [
            f"#{match.log_id}  {match.ts}  [{match.level}]",
            f"logger:    {match.logger or '—'}",
            f"operation: {match.operation or '—'}",
            f"job:       {match.job_id or '—'}",
            "",
            "message:",
            "  " + (match.message or ""),
        ]
        if match.exc_info:
            lines += ["", "traceback:", match.exc_info]
        _ResultDialog(self.frame.winfo_toplevel(),
                       f"Log #{match.log_id}", lines)

    def _clear_all(self) -> None:
        days_raw = simpledialog.askstring(
            "Clear logs",
            "Delete logs older than N days "
            "(blank/0 = ALL logs):",
            parent=self.frame.winfo_toplevel())
        if days_raw is None:
            return
        days = None
        days_raw = days_raw.strip()
        if days_raw:
            try:
                d = int(days_raw)
                days = d if d > 0 else None
            except ValueError:
                messagebox.showerror("Clear logs",
                                       "Must be a whole number.")
                return
        label = (f"older than {days} days" if days is not None
                 else "ALL logs")
        if not messagebox.askyesno("Clear logs",
                                       f"Delete {label}?"):
            return
        try:
            n = bulk_base.clear_logs(older_than_days=days)
        except ValidationError as e:
            messagebox.showerror("Clear logs", str(e))
            return
        messagebox.showinfo("Clear logs", f"Deleted {n} row(s).")
        self.refresh()
