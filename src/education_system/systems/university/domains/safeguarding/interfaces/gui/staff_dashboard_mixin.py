
from education_system.systems.university.infrastructure.i18n import get_text as _t
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
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from tkinter import ttk, messagebox, filedialog

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.safeguarding.application.api import (
    SEVERITY_COLOUR,
    _LIFECYCLE_STATES,
    _connect,
    audit_log,
    can,
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
    category_breakdown,
    dashboard_counters,
    export_case_rows_csv,
)
from education_system.systems.university.domains.safeguarding.interfaces.gui.widgets import (
    ACCENT,
    BarChart,
    CANVAS_BG,
    INK,
    INK_SOFT,
    LINE,
    SURFACE,
    StatCard,
    configure_risk_tags,
    row_tag,
)


class StaffDashboardMixin:
    def show_staff_dashboard(self):
        self._clear()
        # _clear() destroys the widgets but not the attributes pointing at
        # them. The Cases tab is built first and refreshes the Overview off
        # the back of it, so any surviving reference from a previous build
        # would be a destroyed widget by then. Drop them up front.
        for stale in (
            "cards",
            "overview_tree",
            "category_chart",
            "register_tree",
            "subject_chip",
        ):
            self.__dict__.pop(stale, None)
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

        overview_tab = tk.Frame(nb, bg="#f4f6fa")
        cases_tab = tk.Frame(nb, bg="#f4f6fa")
        register_tab = tk.Frame(nb, bg="#f4f6fa")
        dash_tab = tk.Frame(nb, bg="#f4f6fa")
        nb.add(overview_tab, text=_t('gui.safeguarding.staff_dashboard_mixin.tabs.overview', default="Overview"))
        nb.add(cases_tab, text=_t('gui.safeguarding.staff_dashboard_mixin.tabs.cases', default="Cases"))
        nb.add(register_tab, text=_t('gui.safeguarding.staff_dashboard_mixin.tabs.register', default="Student register"))
        nb.add(dash_tab, text=_t('gui.safeguarding.staff_dashboard_mixin.tabs.analytics', default="Analytics"))

        self._notebook = nb
        self._cases_tab_index = 1
        # Cases first — the Overview and Register tabs both hand off to it.
        self._build_cases_tab(cases_tab)
        self._build_overview_tab(overview_tab)
        self._build_register_tab(register_tab)
        self._build_dashboard_tab(dash_tab)
        self._refresh_overview()

    def _build_cases_tab(self, host):
        # Filters
        filt = tk.Frame(host, bg="#f4f6fa")
        filt.pack(fill="x", pady=(8, 8))

        tk.Label(filt, text=_t('gui.safeguarding.staff_dashboard_mixin.labels.status', default="Status:"), bg="#f4f6fa").pack(side="left")
        self.status_var = tk.StringVar(value=_t('gui.safeguarding.staff_dashboard_mixin.values.all', default="All"))
        ttk.Combobox(
            filt,
            textvariable=self.status_var,
            values=["All", "Pending", "In progress", "Closed"],
            state="readonly",
            width=12,
        ).pack(side="left", padx=(4, 12))

        tk.Label(filt, text=_t('gui.safeguarding.staff_dashboard_mixin.labels.severity', default="Severity:"), bg="#f4f6fa").pack(side="left")
        self.sev_var = tk.StringVar(value=_t('gui.safeguarding.staff_dashboard_mixin.values.all', default="All"))
        ttk.Combobox(
            filt,
            textvariable=self.sev_var,
            values=["All", "CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"],
            state="readonly",
            width=12,
        ).pack(side="left", padx=(4, 12))

        tk.Label(filt, text=_t('gui.safeguarding.staff_dashboard_mixin.labels.lifecycle', default="Lifecycle:"), bg="#f4f6fa").pack(side="left")
        self.lifecycle_var = tk.StringVar(value=_t('gui.safeguarding.staff_dashboard_mixin.values.all', default="All"))
        ttk.Combobox(
            filt,
            textvariable=self.lifecycle_var,
            values=["All", *_LIFECYCLE_STATES],
            state="readonly",
            width=12,
        ).pack(side="left", padx=(4, 12))

        ttk.Button(filt, text=_t('gui.safeguarding.staff_dashboard_mixin.buttons.refresh', default="Refresh"), command=self._refresh_staff_list).pack(side="left")

        # Exports exactly what the filters left on screen, unlike the bulk
        # export under Tools which writes the whole table by date range.
        ttk.Button(
            filt,
            text=_t('gui.safeguarding.staff_dashboard_mixin.buttons.export_view', default="Export view…"),
            command=self._export_current_view,
        ).pack(side="left", padx=(8, 0))

        # Subject chip — set when the register hands a student over, so it is
        # obvious the list is narrowed and how to widen it again.
        self._username_filter = ""
        self.subject_chip = tk.Frame(host, bg="#e8eef7")
        self.subject_chip_label = tk.Label(
            self.subject_chip, bg="#e8eef7", fg=INK, font=("Segoe UI", 9)
        )
        self.subject_chip_label.pack(side="left", padx=(10, 6), pady=4)
        ttk.Button(
            self.subject_chip,
            text=_t('gui.safeguarding.staff_dashboard_mixin.buttons.show_all', default="Show all"),
            command=self._clear_username_filter,
            width=10,
        ).pack(side="left", padx=(0, 8), pady=3)

        split = tk.Frame(host, bg="#f4f6fa")
        split.pack(fill="both", expand=True)
        # Kept so the chip can pack itself *above* the expanding table.
        self._cases_split = split

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
        # Softer per-risk row tints plus a greyed "closed" state, from the
        # prototype. Lowercase names, so they sit alongside the uppercase
        # SEVERITY_COLOUR tags above rather than replacing them.
        configure_risk_tags(self.tree)

        self.tree.bind("<<TreeviewSelect>>", self._on_select_submission)

        # Detail panel — wider for tabs
        self.detail = tk.Frame(split, bg="white", bd=1, relief="solid", width=520)
        self.detail.pack(side="right", fill="both", padx=(12, 0))
        self.detail.pack_propagate(False)
        self._render_empty_detail()

        self._refresh_staff_list()

    # ------------------------------------------------------------------
    # Overview tab — headline counters, attention list and category chart.
    # Ported from the UniGuard prototype's dashboard; the heavier analytics
    # (heatmap, trend, review diary) stay on their own tab.
    # ------------------------------------------------------------------

    def _build_overview_tab(self, host):
        page = tk.Frame(host, bg=CANVAS_BG, padx=18, pady=16)
        page.pack(fill="both", expand=True)

        cards = tk.Frame(page, bg=CANVAS_BG)
        cards.pack(fill="x")
        self.cards = {}
        spec = [
            ("open", _t('gui.safeguarding.staff_dashboard_mixin.cards.open_cases', default="Open cases"), INK),
            ("high", _t('gui.safeguarding.staff_dashboard_mixin.cards.high_or_critical', default="High or critical"), "#8f1d1d"),
            ("unassigned", _t('gui.safeguarding.staff_dashboard_mixin.cards.awaiting_assignment', default="Awaiting assignment"), "#8a3d10"),
            ("mine", _t('gui.safeguarding.staff_dashboard_mixin.cards.assigned_to_me', default="Assigned to me"), ACCENT),
            ("raised", _t('gui.safeguarding.staff_dashboard_mixin.cards.raised_by_me', default="Raised by me"), INK),
        ]
        if not can(self.user, "assign"):
            # Reviewers without assignment rights only see what is theirs.
            spec = [c for c in spec if c[0] in ("open", "mine", "raised")]
        for i, (key, caption, colour) in enumerate(spec):
            card = StatCard(cards, caption, accent=colour)
            card.grid(row=0, column=i, sticky="ew", padx=(0, 12))
            cards.columnconfigure(i, weight=1)
            self.cards[key] = card

        body = tk.Frame(page, bg=CANVAS_BG)
        body.pack(fill="both", expand=True, pady=(16, 0))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        attention = tk.Frame(body, bg=SURFACE, highlightbackground=LINE, highlightthickness=1)
        attention.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        tk.Label(
            attention,
            text=_t('gui.safeguarding.staff_dashboard_mixin.labels.cases_needing_attention', default="Cases needing attention"),
            bg=SURFACE, fg=INK, font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(
            attention,
            text=_t('gui.safeguarding.staff_dashboard_mixin.labels.attention_hint', default="Open cases ordered by severity, highest first. Double-click to open one."),
            bg=SURFACE, fg=INK_SOFT, font=("Segoe UI", 8),
        ).pack(anchor="w", padx=16, pady=(0, 10))

        cols = ("id", "student", "severity", "lifecycle", "risk", "owner")
        self.overview_tree = ttk.Treeview(
            attention, columns=cols, show="headings", height=11, selectmode="browse"
        )
        for col, text, width in (
            ("id", _t('gui.safeguarding.staff_dashboard_mixin.columns.case', default="Case"), 60),
            ("student", _t('gui.safeguarding.staff_dashboard_mixin.columns.subject', default="Subject"), 170),
            ("severity", _t('gui.safeguarding.staff_dashboard_mixin.columns.severity', default="Severity"), 85),
            ("lifecycle", _t('gui.safeguarding.staff_dashboard_mixin.columns.lifecycle', default="Lifecycle"), 95),
            ("risk", _t('gui.safeguarding.staff_dashboard_mixin.columns.risk', default="Risk"), 50),
            ("owner", _t('gui.safeguarding.staff_dashboard_mixin.columns.owner', default="Case owner"), 130),
        ):
            self.overview_tree.heading(col, text=text)
            self.overview_tree.column(col, width=width, anchor="w")
        configure_risk_tags(self.overview_tree)
        self.overview_tree.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.overview_tree.bind("<Double-1>", self._open_overview_selection)

        chart_panel = tk.Frame(body, bg=SURFACE, highlightbackground=LINE, highlightthickness=1)
        chart_panel.grid(row=0, column=1, sticky="nsew")
        tk.Label(
            chart_panel,
            text=_t('gui.safeguarding.staff_dashboard_mixin.labels.open_cases_by_category', default="Open cases by category"),
            bg=SURFACE, fg=INK, font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 10))
        self.category_chart = BarChart(
            chart_panel,
            empty_text=_t('gui.safeguarding.staff_dashboard_mixin.labels.no_open_cases_to_display', default="No open cases to display."),
        )
        self.category_chart.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def _refresh_overview(self):
        # __dict__.get, never hasattr/getattr: tk.Misc.__getattr__ proxies a
        # missing attribute to self.tk and recurses when embedded.
        if "cards" not in self.__dict__:
            return
        wb = can_view_whistleblowing(self.user)
        try:
            counters = dashboard_counters(self.user, include_whistleblowing=wb)
        except Exception:
            logger.warning("dashboard counters failed", exc_info=True)
            counters = {}
        for key, card in self.cards.items():
            card.set(counters.get(key, 0))

        try:
            self.category_chart.set_data(category_breakdown(include_whistleblowing=wb))
        except Exception:
            logger.warning("category breakdown failed", exc_info=True)
            self.category_chart.set_data([])

        self.overview_tree.delete(*self.overview_tree.get_children())
        rows = self.__dict__.get("_rows_cache") or {}
        meta = self.__dict__.get("_meta_cache") or {}
        open_rows = [r for r in rows.values() if (r[6] or "") != "Closed"]
        for r in open_rows[:40]:
            sid, name, username, _ts, sev, _cats, status, *_ = r
            lc, risk, _sla, breach = meta.get(sid, ("Open", 0, None, False))
            owner = (self.__dict__.get("_assignees_cache") or {}).get(sid) or _t(
                'gui.safeguarding.staff_dashboard_mixin.values.unassigned', default="Unassigned"
            )
            self.overview_tree.insert(
                "", "end", iid=str(sid),
                values=(sid, f"{name} ({username})", sev, lc, risk, owner),
                tags=(row_tag(sev, status, breach),),
            )

    def _open_overview_selection(self, _event=None):
        selection = self.overview_tree.selection()
        if not selection:
            return
        self._show_case_in_cases_tab(selection[0])

    def _show_case_in_cases_tab(self, iid):
        """Jump to the Cases tab and select ``iid`` there."""
        try:
            self._notebook.select(self._cases_tab_index)
        except Exception:
            logger.debug("could not switch to cases tab", exc_info=True)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.see(iid)
            self._on_select_submission(None)

    def _filter_cases_to_username(self, username):
        """Called from the register — show only this person's cases."""
        self._username_filter = username or ""
        try:
            self._notebook.select(self._cases_tab_index)
        except Exception:
            logger.debug("could not switch to cases tab", exc_info=True)
        self._refresh_staff_list()

    def _clear_username_filter(self):
        self._username_filter = ""
        self._refresh_staff_list()

    def _export_current_view(self):
        if not require(self.user, "export"):
            messagebox.showerror(
                _t('gui.safeguarding.staff_dashboard_mixin.dialogs.permission_denied', default="Permission denied"),
                _t('gui.safeguarding.staff_dashboard_mixin.dialogs.your_role_cannot_export_cases', default="Your role cannot export cases."),
            )
            return
        ids = list(self.tree.get_children())
        if not ids:
            messagebox.showinfo(
                _t('gui.safeguarding.staff_dashboard_mixin.dialogs.nothing_to_export', default="Nothing to export"),
                _t('gui.safeguarding.staff_dashboard_mixin.dialogs.no_cases_match_the_current_filters', default="No cases match the current filters."),
            )
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"safeguarding_view_{datetime.now():%Y%m%d}.csv",
        )
        if not path:
            return
        _, n = export_case_rows_csv(path, ids, actor=self.user.get("username", "?"))
        messagebox.showinfo(
            _t('gui.safeguarding.staff_dashboard_mixin.dialogs.export', default="Export"),
            f"Wrote {n} row(s) to {os.path.basename(path)}.\n\n"
            + _t(
                'gui.safeguarding.staff_dashboard_mixin.dialogs.personal_data_warning',
                default=(
                    "This file contains personal data. Store it on approved "
                    "university storage and delete it when you no longer need it."
                ),
            ),
        )

    def _build_dashboard_tab(self, host):
        # Heatmap (department × severity over last 90 days)
        tk.Label(
            host,
            text=_t('gui.safeguarding.staff_dashboard_mixin.labels.incident_heatmap_department_severity_90_days', default="Incident heatmap — department × severity (90 days)"),
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
            text=_t('gui.safeguarding.staff_dashboard_mixin.labels.department', default="Department"),
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
            tk.Label(heat_frame, text=_t('gui.safeguarding.staff_dashboard_mixin.labels.no_data_yet', default="(no data yet)"), bg="white", fg="#888", padx=8, pady=6).grid(
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
            host, text=_t('gui.safeguarding.staff_dashboard_mixin.labels.risk_trend_last_8_weeks', default="Risk trend — last 8 weeks"), bg="#f4f6fa", font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=12, pady=(18, 4))

        trend = risk_trend(weeks=8)
        trend_frame = tk.Frame(host, bg="white", bd=1, relief="solid")
        trend_frame.pack(fill="x", padx=12, pady=4)
        tk.Label(
            trend_frame,
            text=_t('gui.safeguarding.staff_dashboard_mixin.labels.week', default="Week"),
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
            tk.Label(trend_frame, text=_t('gui.safeguarding.staff_dashboard_mixin.labels.no_data_yet', default="(no data yet)"), bg="white", fg="#888", padx=8, pady=6).grid(
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
            text=_t('gui.safeguarding.staff_dashboard_mixin.labels.reviews_due_now_or_within_7_days', default="Reviews due (now or within 7 days)"),
            bg="#f4f6fa",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(18, 4))
        rev_frame = tk.Frame(host, bg="white", bd=1, relief="solid")
        rev_frame.pack(fill="x", padx=12, pady=4)
        rev_rows = due_reviews(within_days=7)
        if not rev_rows:
            tk.Label(rev_frame, text=_t('gui.safeguarding.staff_dashboard_mixin.labels.none_due', default="(none due)"), bg="white", fg="#888", padx=8, pady=6).pack(
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
        if "tree" not in self.__dict__:
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
        # Subject narrowing from the register. Applied here rather than in
        # fetch_submissions so the whistleblowing gate above still decides
        # what is visible at all.
        subject = self.__dict__.get("_username_filter") or ""
        if subject:
            rows = [r for r in rows if (r[2] or "").lower() == subject.lower()]
        # Display the username as it is actually spelled, not case-folded.
        self._sync_subject_chip(subject, len(rows))

        self._rows_cache = {r[0]: r for r in rows}
        # Pull risk/lifecycle/sla/owner data in one shot
        ids = [r[0] for r in rows]
        meta = {}
        assignees = {}
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn = _connect()
            cur = conn.cursor()
            # db-audit: ignore[DBW001] - string literal
            cur.execute(
                f"SELECT id, lifecycle_state, risk_score, sla_due_at, "
                f" sla_breached, assigned_to FROM safeguarding_submissions "
                f"WHERE id IN ({placeholders})",
                ids,
            )
            for sid, lc, risk, sla_due, breach, assigned in cur.fetchall():
                meta[sid] = (lc or "Open", risk or 0, sla_due, bool(breach))
                assignees[sid] = assigned or ""
            conn.close()
        self._meta_cache = meta
        self._assignees_cache = assignees

        for r in rows:
            sid, name, username, ts, sev, _cats, status, *_ = r
            lc, risk, sla_due, breach = meta.get(sid, ("Open", 0, None, False))
            sla_disp = ""
            if sla_due:
                sla_disp = sla_due.replace("T", " ")[:16]
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
                tags=(row_tag(sev, status, breach),),
            )

        # Counters and the category chart read the same data, so refresh them
        # off the back of this rather than querying twice.
        self._refresh_overview()

    def _sync_subject_chip(self, subject, matched):
        chip = self.__dict__.get("subject_chip")
        if chip is None:
            return
        if not subject:
            chip.pack_forget()
            return
        label = _t(
            'gui.safeguarding.staff_dashboard_mixin.labels.showing_cases_for',
            default="Showing cases for",
        )
        self.subject_chip_label.config(text=f"{label} {subject} — {matched}")
        chip.pack(fill="x", padx=12, pady=(0, 6), before=self._cases_split)

    def _render_empty_detail(self):
        for w in self.detail.winfo_children():
            w.destroy()
        tk.Label(
            self.detail,
            text=_t('gui.safeguarding.staff_dashboard_mixin.labels.select_a_submission_to_review', default="Select a submission to review."),
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
            messagebox.showerror(_t('gui.safeguarding.staff_dashboard_mixin.dialogs.permission_denied', default="Permission denied"), _t('gui.safeguarding.staff_dashboard_mixin.dialogs.your_role_cannot_view_safeguarding_cases', default="Your role cannot view safeguarding cases."))
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
                text=_t('gui.safeguarding.staff_dashboard_mixin.labels.sla_breached', default=" SLA BREACHED "),
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
                text=_t('gui.safeguarding.staff_dashboard_mixin.labels.whistleblowing', default=" WHISTLEBLOWING "),
                bg="#4527a0",
                fg="white",
                font=("Segoe UI", 9, "bold"),
                padx=6,
                pady=1,
            ).pack(side="left", padx=4)

        # Lifecycle dropdown right under the header
        lc_row = tk.Frame(self.detail, bg="white")
        lc_row.pack(fill="x", padx=12, pady=(6, 4))
        tk.Label(lc_row, text=_t('gui.safeguarding.staff_dashboard_mixin.labels.lifecycle', default="Lifecycle:"), bg="white", font=("Segoe UI", 9, "bold")).pack(
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
        nb.add(overview, text=_t('gui.safeguarding.staff_dashboard_mixin.tabs.overview', default="Overview"))
        notes_tab = tk.Frame(nb, bg="white")
        nb.add(notes_tab, text=_t('gui.safeguarding.staff_dashboard_mixin.tabs.notes', default="Notes"))
        actions_tab = tk.Frame(nb, bg="white")
        nb.add(actions_tab, text=_t('gui.safeguarding.staff_dashboard_mixin.tabs.actions', default="Actions"))
        referrals_tab = tk.Frame(nb, bg="white")
        nb.add(referrals_tab, text=_t('gui.safeguarding.staff_dashboard_mixin.tabs.referrals', default="Referrals"))
        integ_tab = tk.Frame(nb, bg="white")
        nb.add(integ_tab, text=_t('gui.safeguarding.staff_dashboard_mixin.tabs.integrations', default="Integrations"))
        linked_tab = tk.Frame(nb, bg="white")
        nb.add(linked_tab, text=_t('gui.safeguarding.staff_dashboard_mixin.tabs.linked', default="Linked"))
        audit_tab = tk.Frame(nb, bg="white")
        nb.add(audit_tab, text=_t('gui.safeguarding.staff_dashboard_mixin.tabs.audit', default="Audit"))

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
