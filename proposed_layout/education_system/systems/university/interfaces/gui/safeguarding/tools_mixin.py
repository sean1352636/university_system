import base64
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import sys
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, scrolledtext, filedialog

logger = logging.getLogger(__name__)

from education_system.systems.university.domain.safeguarding.api import (
    can,
    can_view_whistleblowing,
    daily_dsl_digest,
    disable_webhook,
    export_cases_csv,
    generate_sar_bundle,
    leadership_stats,
    list_audit_log,
    list_mandatory_cases,
    list_webhooks,
    list_whistleblowing_cases,
    purge_due_records,
    record_training,
    register_webhook,
    require,
    stuck_case_alerts,
    training_compliance_summary,
    training_status,
)


class ToolsMixin:
    def _open_tools_menu(self):
        win = tk.Toplevel(self._host)
        win.title("Safeguarding tools")
        win.configure(bg="#f4f6fa")
        tk.Label(
            win, text="Privacy / reporting tools", bg="#f4f6fa", font=("Segoe UI", 11, "bold")
        ).pack(padx=14, pady=(12, 6))

        def _bulk_export():
            if not require(self.user, "export"):
                messagebox.showerror("Permission denied", "Your role cannot export cases.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                initialfile=f"safeguarding_export_{datetime.now():%Y%m%d}.csv",
            )
            if not path:
                return
            _, n = export_cases_csv(path, actor=self.user.get("username", "?"))
            messagebox.showinfo("Export", f"Wrote {n} rows to {path}.")

        def _sar_export():
            if not require(self.user, "export"):
                messagebox.showerror("Permission denied", "Your role cannot export SAR bundles.")
                return
            who = self._prompt("SAR — subject username", "Enter username:")
            if not who:
                return
            out_dir = filedialog.askdirectory(title="Choose output folder")
            if not out_dir:
                return
            path, n = generate_sar_bundle(who, out_dir, actor=self.user.get("username", "?"))
            messagebox.showinfo("SAR bundle", f"Wrote {n} case(s) to {path}.")

        def _audit_log():
            self._show_audit_log()

        def _purge():
            if not require(self.user, "*"):
                # Only admin-tier roles (which have * via _ROLE_PERMISSIONS).
                if not can(self.user, "export"):
                    messagebox.showerror(
                        "Permission denied", "Only admins may run retention purge."
                    )
                    return
            n, ids = purge_due_records(actor=self.user.get("username", "?"), dry_run=True)
            if not n:
                messagebox.showinfo("Retention", "No records past retention horizon.")
                return
            if messagebox.askyesno("Retention purge", f"{n} case(s) past retention. Purge now?"):
                purge_due_records(actor=self.user.get("username", "?"))
                messagebox.showinfo("Retention", f"Purged {n} case(s).")

        def _sla_alerts():
            n = stuck_case_alerts(actor=self.user.get("username", "?"))
            messagebox.showinfo("SLA alerts", f"Queued {n} SLA-breach notification(s).")

        def _digest():
            body = daily_dsl_digest(actor=self.user.get("username", "?"))
            messagebox.showinfo("Daily digest", body)

        def _mandatory_panel():
            self._show_mandatory_panel()

        def _wb_panel():
            if not can_view_whistleblowing(self.user):
                messagebox.showerror(
                    "Permission denied",
                    "Only independent reviewers can open the whistleblowing channel.",
                )
                return
            self._show_wb_panel()

        def _webhooks():
            self._show_webhook_panel()

        def _leadership():
            self._show_leadership_stats()

        def _training():
            self._show_training_panel()

        for label, cmd in (
            ("Bulk CSV export (statutory)…", _bulk_export),
            ("Subject Access Request bundle…", _sar_export),
            ("View audit log", _audit_log),
            ("Run retention purge", _purge),
            ("Queue SLA-breach alerts now", _sla_alerts),
            ("Send daily DSL digest now", _digest),
            ("Mandatory-reporting queue", _mandatory_panel),
            ("Whistleblowing channel (independent)", _wb_panel),
            ("Webhook endpoints (SIEM)…", _webhooks),
            ("Leadership stats (anonymised)", _leadership),
            ("Training tracker", _training),
        ):
            ttk.Button(win, text=label, command=cmd, width=34).pack(padx=14, pady=4)
        ttk.Button(win, text="Close", command=win.destroy).pack(padx=14, pady=(8, 12))

    def _show_mandatory_panel(self):
        win = tk.Toplevel(self._host)
        win.title("Mandatory-reporting queue")
        win.configure(bg="#f4f6fa")
        cols = ("id", "student", "severity", "status", "reported_at")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (50, 220, 90, 100, 160)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for r in list_mandatory_cases():
            sid, fname, uname, sev, mstatus, rep_at = r
            tree.insert(
                "",
                "end",
                iid=str(sid),
                values=(sid, f"{fname} ({uname})", sev, mstatus or "Pending", (rep_at or "")[:19]),
            )

        def _ack():
            sel = tree.selection()
            if not sel:
                return
            self._ack_mandatory(int(sel[0]))
            win.destroy()

        ttk.Button(win, text="Mark selected as Reported…", command=_ack).pack(pady=(0, 8))

    def _show_wb_panel(self):
        win = tk.Toplevel(self._host)
        win.title("Whistleblowing channel — independent reviewers only")
        win.configure(bg="#f4f6fa")
        cols = ("id", "student", "submitted", "severity", "status", "reviewer")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (50, 200, 130, 90, 100, 140)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for r in list_whistleblowing_cases(self.user):
            sid, fname, uname, ts, sev, status, reviewer = r
            tree.insert(
                "",
                "end",
                iid=str(sid),
                values=(
                    sid,
                    f"{fname} ({uname})",
                    ts.replace("T", " ")[:16],
                    sev,
                    status,
                    reviewer or "(unassigned)",
                ),
            )

    def _show_webhook_panel(self):
        win = tk.Toplevel(self._host)
        win.title("Webhook endpoints")
        win.configure(bg="#f4f6fa")
        cols = ("id", "url", "filter", "active", "last_status", "last_sent")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (40, 280, 120, 60, 90, 140)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="x", padx=8, pady=8)

        def _reload():
            for it in tree.get_children():
                tree.delete(it)
            for wid, url, evf, active, _created, ls, lst in list_webhooks():
                tree.insert(
                    "",
                    "end",
                    iid=str(wid),
                    values=(
                        wid,
                        url,
                        evf or "*",
                        "Yes" if active else "No",
                        ls or "—",
                        (lst or "")[:19],
                    ),
                )

        _reload()

        form = tk.Frame(win, bg="#f4f6fa")
        form.pack(fill="x", padx=8, pady=8)
        tk.Label(form, text="URL:", bg="#f4f6fa").grid(row=0, column=0, sticky="w")
        u_e = ttk.Entry(form, width=40)
        u_e.grid(row=0, column=1, padx=4)
        tk.Label(form, text="Secret:", bg="#f4f6fa").grid(row=0, column=2, sticky="w")
        s_e = ttk.Entry(form, width=20)
        s_e.grid(row=0, column=3, padx=4)
        tk.Label(form, text="Events (comma or *):", bg="#f4f6fa").grid(
            row=1, column=0, sticky="w", pady=4
        )
        f_e = ttk.Entry(form, width=30)
        f_e.insert(0, "*")
        f_e.grid(row=1, column=1, sticky="w", padx=4)

        def _add():
            if not require(self.user, "*"):
                messagebox.showerror("Permission denied", "Admins only.")
                return
            url = u_e.get().strip()
            sec = s_e.get().strip()
            if not url or not sec:
                messagebox.showerror("Invalid", "URL and secret are required.")
                return
            register_webhook(
                url, sec, f_e.get().strip() or "*", actor=self.user.get("username", "?")
            )
            u_e.delete(0, "end")
            s_e.delete(0, "end")
            _reload()

        def _disable():
            sel = tree.selection()
            if not sel:
                return
            if not require(self.user, "*"):
                return
            disable_webhook(int(sel[0]), actor=self.user.get("username", "?"))
            _reload()

        ttk.Button(form, text="Add webhook", command=_add).grid(row=1, column=3, padx=4)
        ttk.Button(form, text="Disable selected", command=_disable).grid(row=1, column=4, padx=4)

    def _show_leadership_stats(self):
        win = tk.Toplevel(self._host)
        win.title("Leadership stats (90 days, anonymised)")
        win.configure(bg="#f4f6fa")
        stats = leadership_stats(days=90)
        body = (
            f"Period: last {stats['period_days']} days\n"
            f"Total cases: {stats['total']}\n"
            f"SLA breaches: {stats['sla_breaches']}\n"
            f"Mandatory-reporting flags: {stats['mandatory_flags']}\n"
            f"Avg days to close: {stats['avg_days_to_close']}\n\n"
            f"By severity: {stats['by_severity']}\n"
            f"By lifecycle: {stats['by_lifecycle']}\n"
            f"By outcome: {stats['by_outcome']}\n"
        )
        tk.Label(
            win, text=body, bg="#f4f6fa", justify="left", font=("Segoe UI", 10), padx=14, pady=14
        ).pack()

    def _show_training_panel(self):
        win = tk.Toplevel(self._host)
        win.title("Safeguarding training tracker")
        win.configure(bg="#f4f6fa")
        summary = training_compliance_summary()
        tk.Label(
            win,
            text=(
                f"Staff tracked: {summary['users_tracked']}  •  "
                f"Current: {summary['current']} ({summary['current_pct']}%)  •  "
                f"Expiring soon: {summary['expiring_soon']}  •  "
                f"Expired: {summary['expired']}"
            ),
            bg="#f4f6fa",
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=10,
        ).pack()

        # Per-user lookup
        row = tk.Frame(win, bg="#f4f6fa")
        row.pack(fill="x", padx=14)
        tk.Label(row, text="Lookup username:", bg="#f4f6fa").pack(side="left")
        u = ttk.Entry(row, width=18)
        u.pack(side="left", padx=4)
        out = tk.Label(win, text="", bg="#f4f6fa", justify="left", font=("Segoe UI", 9))
        out.pack(padx=14, pady=4, anchor="w")

        def _go():
            st = training_status(u.get().strip())
            out.config(text=str(st) if st else "(no records on file)")

        ttk.Button(row, text="Check", command=_go).pack(side="left")

        # Record completion
        form = tk.Frame(win, bg="#f4f6fa")
        form.pack(fill="x", padx=14, pady=(12, 14))
        tk.Label(form, text="Record completion — username:", bg="#f4f6fa").grid(
            row=0, column=0, sticky="w"
        )
        ru = ttk.Entry(form, width=16)
        ru.grid(row=0, column=1, padx=4)
        tk.Label(form, text="Module:", bg="#f4f6fa").grid(row=0, column=2, sticky="w")
        rm = ttk.Combobox(
            form,
            width=24,
            values=[
                "KCSIE basics",
                "Prevent duty",
                "Online safety",
                "Trauma-informed practice",
                "GDPR refresher",
            ],
        )
        rm.grid(row=0, column=3, padx=4)

        def _record():
            if not (ru.get().strip() and rm.get().strip()):
                return
            record_training(
                ru.get().strip(),
                ru.get().strip(),
                rm.get().strip(),
                actor=self.user.get("username", "?"),
            )
            messagebox.showinfo("Recorded", f"Training recorded for {ru.get().strip()}.")
            win.destroy()

        ttk.Button(form, text="Record", command=_record).grid(row=0, column=4, padx=6)

    def _show_audit_log(self):
        win = tk.Toplevel(self._host)
        win.title("Safeguarding audit log")
        win.configure(bg="#f4f6fa")
        cols = ("ts", "actor", "role", "action", "case", "details")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=20)
        for c, w in zip(cols, (140, 110, 90, 130, 60, 320)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for _id, ts, actor, role, action, cid, details in list_audit_log(limit=500):
            tree.insert(
                "",
                "end",
                values=(
                    ts.replace("T", " ")[:19],
                    actor,
                    role or "",
                    action,
                    cid if cid is not None else "",
                    details or "",
                ),
            )
