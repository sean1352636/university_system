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

from education_system.post_18.university_system.modules.domain.student_affairs.safeguarding.api import (
    SEVERITY_COLOUR,
    _LIFECYCLE_STATES,
    _connect,
    audit_log,
    can_view_whistleblowing,
    due_reviews,
    fetch_submissions,
    get_oncall_dsl,
    incident_heatmap,
    refresh_sla_breach_flags,
    require,
    resolve_content,
    risk_trend,
    set_lifecycle_state,
)


class StaffDashboardMixin:
    def show_staff_dashboard(self):
        self._clear()
        self.unbind("<Return>")
        oncall = get_oncall_dsl()
        oncall_label = (
            f"  •  On-call DSL: {oncall['full_name']} ({oncall['username']})"
            if oncall
            else "  •  No on-call DSL configured"
        )
        self._build_topbar(f"Staff console — {self.user['full_name']}{oncall_label}")

        # Recompute SLA breach flags on every dashboard mount
        refresh_sla_breach_flags()

        body = tk.Frame(self.container, bg="#f4f6fa")
        body.pack(fill="both", expand=True, padx=20, pady=10)

        nb = ttk.Notebook(body)
        nb.pack(fill="both", expand=True)

        cases_tab = tk.Frame(nb, bg="#f4f6fa")
        dash_tab = tk.Frame(nb, bg="#f4f6fa")
        nb.add(cases_tab, text="Cases")
        nb.add(dash_tab, text="Dashboard")

        self._build_cases_tab(cases_tab)
        self._build_dashboard_tab(dash_tab)

    def _build_cases_tab(self, host):
        # Filters
        filt = tk.Frame(host, bg="#f4f6fa")
        filt.pack(fill="x", pady=(8, 8))

        tk.Label(filt, text="Status:", bg="#f4f6fa").pack(side="left")
        self.status_var = tk.StringVar(value="All")
        ttk.Combobox(
            filt,
            textvariable=self.status_var,
            values=["All", "Pending", "In progress", "Closed"],
            state="readonly",
            width=12,
        ).pack(side="left", padx=(4, 12))

        tk.Label(filt, text="Severity:", bg="#f4f6fa").pack(side="left")
        self.sev_var = tk.StringVar(value="All")
        ttk.Combobox(
            filt,
            textvariable=self.sev_var,
            values=["All", "CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"],
            state="readonly",
            width=12,
        ).pack(side="left", padx=(4, 12))

        tk.Label(filt, text="Lifecycle:", bg="#f4f6fa").pack(side="left")
        self.lifecycle_var = tk.StringVar(value="All")
        ttk.Combobox(
            filt,
            textvariable=self.lifecycle_var,
            values=["All", *_LIFECYCLE_STATES],
            state="readonly",
            width=12,
        ).pack(side="left", padx=(4, 12))

        ttk.Button(filt, text="Refresh", command=self._refresh_staff_list).pack(side="left")

        split = tk.Frame(host, bg="#f4f6fa")
        split.pack(fill="both", expand=True)

        list_frame = tk.Frame(split, bg="#f4f6fa")
        list_frame.pack(side="left", fill="both", expand=True)

        columns = ("id", "student", "submitted", "severity", "lifecycle", "risk", "sla")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)
        widths = (40, 160, 120, 80, 90, 50, 90)
        for col, w in zip(columns, widths):
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=w, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        for sev, col in SEVERITY_COLOUR.items():
            self.tree.tag_configure(
                sev, background=col, foreground="white" if sev != "LOW" else "black"
            )
        self.tree.tag_configure("BREACH", background="#5b0011", foreground="white")

        self.tree.bind("<<TreeviewSelect>>", self._on_select_submission)

        # Detail panel — wider for tabs
        self.detail = tk.Frame(split, bg="white", bd=1, relief="solid", width=520)
        self.detail.pack(side="right", fill="both", padx=(12, 0))
        self.detail.pack_propagate(False)
        self._render_empty_detail()

        self._refresh_staff_list()

    def _build_dashboard_tab(self, host):
        # Heatmap (department × severity over last 90 days)
        tk.Label(
            host,
            text="Incident heatmap — department × severity (90 days)",
            bg="#f4f6fa",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 4))

        heat_frame = tk.Frame(host, bg="white", bd=1, relief="solid")
        heat_frame.pack(fill="x", padx=12, pady=4)

        grid = incident_heatmap(days=90)
        sevs = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE")
        # Header row
        tk.Label(
            heat_frame,
            text="Department",
            bg="#1f3a5f",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=6,
            pady=4,
        ).grid(row=0, column=0, sticky="we")
        for ci, sev in enumerate(sevs, start=1):
            tk.Label(
                heat_frame,
                text=sev,
                bg="#1f3a5f",
                fg="white",
                font=("Segoe UI", 9, "bold"),
                padx=6,
                pady=4,
            ).grid(row=0, column=ci, sticky="we")
        if not grid:
            tk.Label(heat_frame, text="(no data yet)", bg="white", fg="#888", padx=8, pady=6).grid(
                row=1, column=0, columnspan=len(sevs) + 1
            )
        else:
            for ri, (dept, by_sev) in enumerate(sorted(grid.items()), start=1):
                tk.Label(heat_frame, text=dept, bg="white", anchor="w", padx=6, pady=3).grid(
                    row=ri, column=0, sticky="we"
                )
                for ci, sev in enumerate(sevs, start=1):
                    n = by_sev.get(sev, 0)
                    bg = SEVERITY_COLOUR.get(sev, "#fff") if n else "#f5f5f5"
                    fg = "white" if n and sev != "LOW" else "#333"
                    tk.Label(
                        heat_frame,
                        text=str(n or ""),
                        bg=bg,
                        fg=fg,
                        font=("Segoe UI", 9, "bold" if n else "normal"),
                        padx=6,
                        pady=3,
                    ).grid(row=ri, column=ci, sticky="we")

        # Risk trend (last 8 weeks)
        tk.Label(
            host, text="Risk trend — last 8 weeks", bg="#f4f6fa", font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=12, pady=(18, 4))

        trend = risk_trend(weeks=8)
        trend_frame = tk.Frame(host, bg="white", bd=1, relief="solid")
        trend_frame.pack(fill="x", padx=12, pady=4)
        tk.Label(
            trend_frame,
            text="Week",
            bg="#1f3a5f",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=6,
            pady=4,
        ).grid(row=0, column=0, sticky="we")
        for ci, sev in enumerate(sevs, start=1):
            tk.Label(
                trend_frame,
                text=sev,
                bg="#1f3a5f",
                fg="white",
                font=("Segoe UI", 9, "bold"),
                padx=6,
                pady=4,
            ).grid(row=0, column=ci, sticky="we")
        if not trend:
            tk.Label(trend_frame, text="(no data yet)", bg="white", fg="#888", padx=8, pady=6).grid(
                row=1, column=0, columnspan=len(sevs) + 1
            )
        else:
            for ri, (wk, by_sev) in enumerate(sorted(trend.items()), start=1):
                tk.Label(trend_frame, text=wk, bg="white", anchor="w", padx=6, pady=3).grid(
                    row=ri, column=0, sticky="we"
                )
                for ci, sev in enumerate(sevs, start=1):
                    n = by_sev.get(sev, 0)
                    tk.Label(
                        trend_frame,
                        text=str(n or ""),
                        bg="white",
                        padx=6,
                        pady=3,
                        font=("Segoe UI", 9),
                    ).grid(row=ri, column=ci, sticky="we")

        # Feature 27 — reviews due now or in next 7 days
        tk.Label(
            host,
            text="Reviews due (now or within 7 days)",
            bg="#f4f6fa",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(18, 4))
        rev_frame = tk.Frame(host, bg="white", bd=1, relief="solid")
        rev_frame.pack(fill="x", padx=12, pady=4)
        rev_rows = due_reviews(within_days=7)
        if not rev_rows:
            tk.Label(rev_frame, text="(none due)", bg="white", fg="#888", padx=8, pady=6).pack(
                anchor="w"
            )
        else:
            for rid, fname, uname, rsev, due, lc, assigned in rev_rows[:12]:
                line = (
                    f"#{rid}  {fname} ({uname})  —  {rsev}  —  "
                    f"due {due.replace('T', ' ')[:16]}  —  "
                    f"{lc or 'Open'}  →  {assigned or '(unassigned)'}"
                )
                tk.Label(
                    rev_frame,
                    text=line,
                    bg="white",
                    anchor="w",
                    font=("Segoe UI", 9),
                    padx=8,
                    pady=2,
                ).pack(anchor="w", fill="x")

    def _refresh_staff_list(self):
        if not hasattr(self, "tree"):
            return
        refresh_sla_breach_flags()
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = fetch_submissions(
            self.status_var.get(),
            self.sev_var.get(),
            self.lifecycle_var.get(),
            include_whistleblowing=can_view_whistleblowing(self.user),
        )
        self._rows_cache = {r[0]: r for r in rows}
        # Pull risk/lifecycle/sla data in one shot
        ids = [r[0] for r in rows]
        meta = {}
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn = _connect()
            cur = conn.cursor()
            cur.execute(
                f"SELECT id, lifecycle_state, risk_score, sla_due_at, "
                f" sla_breached FROM safeguarding_submissions "
                f"WHERE id IN ({placeholders})",
                ids,
            )
            for sid, lc, risk, sla_due, breach in cur.fetchall():
                meta[sid] = (lc or "Open", risk or 0, sla_due, bool(breach))
            conn.close()
        for r in rows:
            sid, name, username, ts, sev, _cats, _status, *_ = r
            lc, risk, sla_due, breach = meta.get(sid, ("Open", 0, None, False))
            sla_disp = ""
            if sla_due:
                sla_disp = sla_due.replace("T", " ")[:16]
            tags = ("BREACH",) if breach else (sev,)
            self.tree.insert(
                "",
                "end",
                iid=str(sid),
                values=(
                    sid,
                    f"{name} ({username})",
                    ts.replace("T", " ")[:16],
                    sev,
                    lc,
                    risk,
                    sla_disp,
                ),
                tags=tags,
            )

    def _render_empty_detail(self):
        for w in self.detail.winfo_children():
            w.destroy()
        tk.Label(
            self.detail,
            text="Select a submission to review.",
            bg="white",
            fg="#888",
            font=("Segoe UI", 10),
        ).pack(expand=True)

    def _on_select_submission(self, _evt):
        sel = self.tree.selection()
        if not sel:
            return
        sid = int(sel[0])
        # Feature 36 — gate viewing on role permission and log every access.
        if not require(self.user, "view_case"):
            messagebox.showerror("Permission denied", "Your role cannot view safeguarding cases.")
            return
        audit_log(
            actor=self.user.get("username", "?"),
            actor_role=self.user.get("role", "?"),
            action="view_case",
            case_id=sid,
        )
        row = self._rows_cache[sid]
        (sid, name, username, ts, sev, cats_json, status, content, reviewer, note, reviewed_at) = (
            row
        )
        # Feature 37 — decrypt content + transcription for display.
        decrypted_content, decrypted_trans = resolve_content(sid)
        if decrypted_content:
            content = decrypted_content

        for w in self.detail.winfo_children():
            w.destroy()

        # Fetch all the extended metadata for this submission
        extra = {}
        try:
            conn = _connect()
            cur = conn.cursor()
            cur.execute(
                "SELECT anonymous, on_behalf_of, reporter_username, subject_relation, "
                "       attachments, audio_path, transcription, language, "
                "       consent_disclosure, consent_contact, duplicate_of, "
                "       likelihood, impact, risk_score, nlp_score, nlp_categories, "
                "       sla_due_at, sla_breached, assigned_to, assigned_at, "
                "       linked_subject_id, vulnerability_flags, lifecycle_state, "
                "       case_location, case_department, "
                "       outcome_code, closure_reason, "
                "       mandatory_reporting, mandatory_status, mandatory_reported_at, "
                "       whistleblowing, wb_independent_reviewer, "
                "       linked_wellbeing_appt, linked_conduct_case, "
                "       linked_halls_incident, health_referral_consent, "
                "       health_referral_sent_at, tutor_notified_at, "
                "       tutor_notification_redacted "
                "FROM safeguarding_submissions WHERE id=?",
                (sid,),
            )
            r = cur.fetchone()
            conn.close()
            if r:
                keys = (
                    "anonymous",
                    "on_behalf_of",
                    "reporter_username",
                    "subject_relation",
                    "attachments_json",
                    "audio_path",
                    "transcription",
                    "language",
                    "consent_disclosure",
                    "consent_contact",
                    "duplicate_of",
                    "likelihood",
                    "impact",
                    "risk_score",
                    "nlp_score",
                    "nlp_categories_json",
                    "sla_due_at",
                    "sla_breached",
                    "assigned_to",
                    "assigned_at",
                    "linked_subject_id",
                    "vulnerability_flags_json",
                    "lifecycle_state",
                    "case_location",
                    "case_department",
                    "outcome_code",
                    "closure_reason",
                    "mandatory_reporting",
                    "mandatory_status",
                    "mandatory_reported_at",
                    "whistleblowing",
                    "wb_independent_reviewer",
                    "linked_wellbeing_appt",
                    "linked_conduct_case",
                    "linked_halls_incident",
                    "health_referral_consent",
                    "health_referral_sent_at",
                    "tutor_notified_at",
                    "tutor_notification_redacted",
                )
                extra = dict(zip(keys, r))
                # Decrypted transcription overrides the plaintext column for display.
                if decrypted_trans:
                    extra["transcription"] = decrypted_trans
        except Exception:
            logger.debug("Could not fetch extra metadata for #%s", sid, exc_info=True)

        # Header strip
        header = tk.Frame(self.detail, bg="white")
        header.pack(fill="x", padx=12, pady=(12, 0))
        tk.Label(header, text=f"Case #{sid}", bg="white", font=("Segoe UI", 13, "bold")).pack(
            side="left"
        )
        badge = tk.Label(
            header,
            text=f" {sev} ",
            bg=SEVERITY_COLOUR.get(sev, "#666"),
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=6,
            pady=1,
        )
        badge.pack(side="left", padx=8)
        risk_score = extra.get("risk_score") or 0
        risk_bg = (
            "#b00020"
            if risk_score >= 16
            else "#d9480f"
            if risk_score >= 9
            else "#f38b00"
            if risk_score >= 4
            else "#2e7d32"
        )
        tk.Label(
            header,
            text=f" Risk {risk_score} ({extra.get('likelihood') or 0}×{extra.get('impact') or 0}) ",
            bg=risk_bg,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=6,
            pady=1,
        ).pack(side="left")
        if extra.get("sla_breached"):
            tk.Label(
                header,
                text=" SLA BREACHED ",
                bg="#5b0011",
                fg="white",
                font=("Segoe UI", 9, "bold"),
                padx=6,
                pady=1,
            ).pack(side="left", padx=4)
        if extra.get("mandatory_reporting"):
            mstatus = extra.get("mandatory_status") or "Pending"
            mcolor = "#5b0011" if mstatus == "Pending" else "#1f3a5f"
            tk.Label(
                header,
                text=f" MANDATORY: {mstatus} ",
                bg=mcolor,
                fg="white",
                font=("Segoe UI", 9, "bold"),
                padx=6,
                pady=1,
            ).pack(side="left", padx=4)
        if extra.get("whistleblowing"):
            tk.Label(
                header,
                text=" WHISTLEBLOWING ",
                bg="#4527a0",
                fg="white",
                font=("Segoe UI", 9, "bold"),
                padx=6,
                pady=1,
            ).pack(side="left", padx=4)

        # Lifecycle dropdown right under the header
        lc_row = tk.Frame(self.detail, bg="white")
        lc_row.pack(fill="x", padx=12, pady=(6, 4))
        tk.Label(lc_row, text="Lifecycle:", bg="white", font=("Segoe UI", 9, "bold")).pack(
            side="left"
        )
        lc_var = tk.StringVar(value=extra.get("lifecycle_state") or "Open")
        lc_combo = ttk.Combobox(
            lc_row, textvariable=lc_var, values=list(_LIFECYCLE_STATES), state="readonly", width=14
        )
        lc_combo.pack(side="left", padx=6)

        def _on_lc_change(_e):
            set_lifecycle_state(sid, lc_var.get(), actor=self.user.get("username") or "")
            self._refresh_staff_list()

        lc_combo.bind("<<ComboboxSelected>>", _on_lc_change)

        # Tabbed detail body
        nb = ttk.Notebook(self.detail)
        nb.pack(fill="both", expand=True, padx=8, pady=6)

        overview = tk.Frame(nb, bg="white")
        nb.add(overview, text="Overview")
        notes_tab = tk.Frame(nb, bg="white")
        nb.add(notes_tab, text="Notes")
        actions_tab = tk.Frame(nb, bg="white")
        nb.add(actions_tab, text="Actions")
        referrals_tab = tk.Frame(nb, bg="white")
        nb.add(referrals_tab, text="Referrals")
        integ_tab = tk.Frame(nb, bg="white")
        nb.add(integ_tab, text="Integrations")
        linked_tab = tk.Frame(nb, bg="white")
        nb.add(linked_tab, text="Linked")
        audit_tab = tk.Frame(nb, bg="white")
        nb.add(audit_tab, text="Audit")

        self._render_overview_tab(
            overview,
            sid,
            name,
            username,
            ts,
            sev,
            cats_json,
            status,
            content,
            reviewer,
            note,
            reviewed_at,
            extra,
        )
        self._render_notes_tab(notes_tab, sid)
        self._render_actions_tab(actions_tab, sid)
        self._render_referrals_tab(referrals_tab, sid)
        self._render_integrations_tab(integ_tab, sid, extra)
        self._render_linked_tab(linked_tab, sid, extra)
        self._render_audit_tab(audit_tab, sid, extra)
