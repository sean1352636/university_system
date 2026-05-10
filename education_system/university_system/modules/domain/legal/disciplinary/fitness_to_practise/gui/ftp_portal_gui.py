"""FtP Portal GUI — extracted from ``fitness_to_practise.py`` (8.117.141).

Adds an Open-in bar + drill-throughs to sibling university modules,
matching the EQA / IR pattern. ``app=None`` is the
``UnifiedManagementGUI`` instance (only present when launched
in-process via ``UnifiedManagementGUI.show_fitness_to_practise_gui``).
"""

from __future__ import annotations

import csv
import logging
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from education_system.university_system.modules.domain.legal.disciplinary.fitness_to_practise._db_init import (
    CONCERN_CATEGORIES,
    OUTCOMES,
    REGULATORS,
    STAGES,
)
from education_system.university_system.modules.domain.legal.disciplinary.fitness_to_practise.services.ftp_service import (
    FtPDataAccess,
    current_username,
)

logger = logging.getLogger(__name__)


class FitnessToPractisePortal:
    """Top-level Tk app. One Notebook, four tabs:

    * Cases       — list / filter / open / close / delete
    * Concerns    — per-case concerns list and add form
    * Events      — chronological audit trail
    * Outcomes    — committee decisions and sanctions
    """

    # Open-in bar targets — same convention as EQA / IR. Buttons
    # auto-disable when the parent app doesn't expose the launcher.
    _OPEN_IN_TARGETS = (
        ("Student Records", "show_student_records"),
        ("Disciplinary Portal", "show_new_feature_disciplinary_portal"),
        ("Information Rights", "show_information_rights_gui"),
        ("Background Checker", "show_new_feature_background_checker"),
        ("Documents", "show_data_documents_gui"),
        ("Communication Hub", "show_communication_hub_gui"),
        ("Security Dashboard", "show_security_dashboard"),
        ("Business Intel", "show_business_intelligence_gui"),
    )

    def __init__(self, root, app=None):
        self.root = root
        self.app = app
        self.db = FtPDataAccess()
        self.selected_case_id = None

        # Window sizing follows the project convention
        # (memory: feedback_window_sizing — 1400x900 + minsize(1200,800);
        #  no zoomed/fullscreen).
        self.root.title("Fitness to Practise Portal")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        self._build_ui()
        self._refresh_cases()
        self._refresh_stats()

        # Live-reference for reverse drills (mirrors EQA's _eqa_dash
        # and IR's _ir_window).
        if self.app is not None:
            try:
                self.app._ftp_window = self
                self.root.bind("<Destroy>", self._on_destroy, add="+")
            except Exception:
                pass

    def _on_destroy(self, event) -> None:
        if event.widget is not self.root:
            return
        try:
            if getattr(self.app, "_ftp_window", None) is self:
                self.app._ftp_window = None
        except Exception:
            pass

    # ---- Layout ----
    def _build_ui(self):
        header = ttk.Frame(self.root, padding=10)
        header.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(header, text="⚖  Fitness to Practise",
                  font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)
        self.stats_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.stats_var,
                  font=('Helvetica', 10)).pack(side=tk.RIGHT)

        self._build_open_in_bar(self.root)

        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.notebook = nb

        self.cases_tab = ttk.Frame(nb)
        self.concerns_tab = ttk.Frame(nb)
        self.events_tab = ttk.Frame(nb)
        self.outcomes_tab = ttk.Frame(nb)
        nb.add(self.cases_tab, text="Cases")
        nb.add(self.concerns_tab, text="Concerns")
        nb.add(self.events_tab, text="Events")
        nb.add(self.outcomes_tab, text="Outcomes")

        self._build_cases_tab(self.cases_tab)
        self._build_concerns_tab(self.concerns_tab)
        self._build_events_tab(self.events_tab)
        self._build_outcomes_tab(self.outcomes_tab)

    # =================================================================
    # Open-in bar + drill-throughs
    # =================================================================

    def _build_open_in_bar(self, parent) -> None:
        bar = ttk.Frame(parent, padding=(10, 0, 10, 4))
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="Open in:",
                  font=('Helvetica', 9, 'bold')).pack(side=tk.LEFT,
                                                       padx=(0, 6))
        for label, method in self._OPEN_IN_TARGETS:
            btn = ttk.Button(
                bar, text=label,
                command=lambda m=method, lab=label: self._open_in(m, lab),
            )
            btn.pack(side=tk.LEFT, padx=2)
            if not (self.app and hasattr(self.app, method)):
                btn.state(["disabled"])

        ttk.Separator(bar, orient="vertical").pack(side=tk.LEFT,
                                                    padx=8, fill=tk.Y)
        ttk.Label(bar, text="Selected case:",
                  font=('Helvetica', 9, 'italic')).pack(side=tk.LEFT,
                                                        padx=(0, 4))
        for label, method in (
            ("Student", "drill_to_student_record"),
            ("Source disciplinary", "drill_to_source_disciplinary"),
            ("Audit log", "drill_to_audit_log"),
            ("Comms", "drill_to_communications"),
        ):
            ttk.Button(bar, text=label,
                       command=getattr(self, method)).pack(side=tk.LEFT,
                                                            padx=2)

    def _open_in(self, method_name: str, label: str) -> None:
        self._dispatch_with_context(method_name, label, context=None)

    def _dispatch_with_context(self, method_name: str, label: str,
                                 context: dict | None) -> None:
        if not self.app:
            messagebox.showinfo(
                "Not available",
                "Cross-module navigation requires the main GUI; open "
                "this dashboard from the main menu rather than standalone.",
                parent=self.root,
            )
            return
        fn = getattr(self.app, method_name, None)
        if fn is None:
            messagebox.showwarning("Not available",
                                    f"{label} is not registered on this build.",
                                    parent=self.root)
            return
        try:
            self.app._last_academic_context = context
        except Exception:
            pass
        try:
            fn()
        except Exception as exc:
            logger.exception("Open-in %s failed", method_name)
            messagebox.showerror("Failed to open",
                                  f"Could not open {label}: {exc}",
                                  parent=self.root)

    def _selected_case(self) -> dict | None:
        if not self.selected_case_id:
            return None
        row = self.db.get_case(self.selected_case_id)
        if not row:
            return None
        return {
            "case_id": row[0], "student_id": row[1], "programme": row[2],
            "regulator": row[3], "registration_no": row[4], "stage": row[5],
            "risk_level": row[6], "interim_order": row[7],
            "placement_status": row[8], "date_opened": row[9],
            "date_closed": row[10], "case_officer": row[11],
            "panel_chair": row[12], "summary": row[13],
            "source_record_id": row[14],
        }

    def _require_case_for(self, action: str) -> dict | None:
        case = self._selected_case()
        if not case:
            messagebox.showinfo("Pick a case",
                                 f"Select a case in the Cases tab first to {action}.",
                                 parent=self.root)
        return case

    # ---- six drill-throughs ----
    def drill_to_student_record(self) -> dict | None:
        """Open Student Records for the case's student."""
        case = self._require_case_for("open the student record")
        if not case:
            return None
        payload = {
            "source": "ftp.case",
            "ftp_case_id": case["case_id"],
            "student_id": case["student_id"],
            "programme": case["programme"],
            "regulator": case["regulator"],
        }
        self._dispatch_with_context("show_student_records",
                                      "Student Records", payload)
        return payload

    def drill_to_source_disciplinary(self) -> dict | None:
        """Open the originating disciplinary record (when this FtP case
        was referred from the general disciplinary portal)."""
        case = self._require_case_for("open the source disciplinary record")
        if not case:
            return None
        if not case.get("source_record_id"):
            messagebox.showinfo(
                "No source",
                "This FtP case wasn't referred from a disciplinary record.",
                parent=self.root)
            return None
        payload = {
            "source": "ftp.case",
            "ftp_case_id": case["case_id"],
            "disciplinary_record_id": case["source_record_id"],
        }
        self._dispatch_with_context(
            "show_new_feature_disciplinary_portal",
            "Disciplinary Portal", payload)
        return payload

    def drill_to_audit_log(self) -> dict | None:
        """Open the Security Dashboard filtered to this case's events."""
        case = self._require_case_for("view its audit log")
        if not case:
            return None
        payload = {
            "source": "ftp.case",
            "audit_action_prefix": "ftp.",
            "resource_type": "ftp_case",
            "resource_id": str(case["case_id"]),
        }
        self._dispatch_with_context("show_security_dashboard",
                                      "Security Dashboard", payload)
        return payload

    def drill_to_communications(self) -> dict | None:
        """Open the Communication Hub focused on this case's thread."""
        case = self._require_case_for("open its communications thread")
        if not case:
            return None
        payload = {
            "source": "ftp.case",
            "ftp_case_id": case["case_id"],
            "student_id": case["student_id"],
            "thread_subject": f"FtP case #{case['case_id']}",
        }
        self._dispatch_with_context("show_communication_hub_gui",
                                      "Communication Hub", payload)
        return payload

    def drill_to_information_rights(self) -> dict | None:
        """Open Information Rights to file/inspect a SAR for the
        case's student (FtP cases are common SAR triggers)."""
        case = self._require_case_for("open Information Rights")
        if not case:
            return None
        payload = {
            "source": "ftp.case",
            "ftp_case_id": case["case_id"],
            "subject_id": case["student_id"],
        }
        self._dispatch_with_context("show_information_rights_gui",
                                      "Information Rights", payload)
        return payload

    def drill_to_response_kpis(self) -> dict:
        """Open Business Intelligence with the FtP KPI category."""
        payload = {"source": "ftp.kpis",
                   "kpi_category": "fitness_to_practise"}
        self._dispatch_with_context("show_business_intelligence_gui",
                                      "Business Intel", payload)
        return payload

    # =================================================================
    # set_focus + register_open_in
    # =================================================================

    _TAB_INDEX = {"cases": 0, "concerns": 1, "events": 2, "outcomes": 3}

    def set_focus(self, case_id: int | None = None,
                   tab: str | None = None) -> None:
        """Programmatic focus API: switch tab and optionally select a
        case in the cases tree."""
        try:
            if tab and tab.lower() in self._TAB_INDEX:
                self.notebook.select(self._TAB_INDEX[tab.lower()])
            if case_id is not None:
                for iid in self.cases_tree.get_children():
                    vals = self.cases_tree.item(iid)["values"]
                    if vals and int(vals[0]) == int(case_id):
                        self.cases_tree.selection_set(iid)
                        self.cases_tree.see(iid)
                        self._on_case_selected()
                        break
        except Exception:
            logger.exception("set_focus failed")

    @classmethod
    def register_open_in(cls, label: str, method_name: str,
                          replace: bool = False) -> None:
        new = list(cls._OPEN_IN_TARGETS)
        if replace:
            new = [(lab, m) for lab, m in new if lab != label]
        else:
            for lab, _ in new:
                if lab == label:
                    return
        new.append((label, method_name))
        cls._OPEN_IN_TARGETS = tuple(new)

    # ---- Cases tab ----
    def _build_cases_tab(self, parent):
        toolbar = ttk.Frame(parent, padding=(8, 8))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(toolbar, text="Stage:").pack(side=tk.LEFT)
        self.filter_stage = ttk.Combobox(
            toolbar, values=('All', *STAGES), state='readonly', width=20)
        self.filter_stage.set('All')
        self.filter_stage.pack(side=tk.LEFT, padx=(2, 10))
        self.filter_stage.bind('<<ComboboxSelected>>',
                               lambda *_: self._refresh_cases())

        ttk.Label(toolbar, text="Regulator:").pack(side=tk.LEFT)
        self.filter_regulator = ttk.Combobox(
            toolbar, values=('All', *REGULATORS), state='readonly', width=10)
        self.filter_regulator.set('All')
        self.filter_regulator.pack(side=tk.LEFT, padx=(2, 10))
        self.filter_regulator.bind('<<ComboboxSelected>>',
                                   lambda *_: self._refresh_cases())

        ttk.Label(toolbar, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.search_var, width=24).pack(
            side=tk.LEFT, padx=(2, 4))
        ttk.Button(toolbar, text="Go",
                   command=self._refresh_cases).pack(side=tk.LEFT)

        ttk.Button(toolbar, text="New Case",
                   command=self._open_new_case_dialog).pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="Export CSV",
                   command=self._export_cases_csv).pack(
            side=tk.RIGHT, padx=(0, 6))

        cols = ('id', 'student', 'name', 'programme', 'regulator',
                'stage', 'risk', 'officer', 'opened')
        headings = ('Case', 'Student ID', 'Name', 'Programme',
                    'Regulator', 'Stage', 'Risk', 'Officer', 'Opened')
        widths = (60, 90, 180, 180, 90, 140, 70, 130, 110)
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.cases_tree = ttk.Treeview(tree_frame, columns=cols,
                                       show='headings')
        for c, h, w in zip(cols, headings, widths):
            self.cases_tree.heading(c, text=h)
            self.cases_tree.column(c, width=w, anchor=tk.W)
        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                           command=self.cases_tree.yview)
        self.cases_tree.configure(yscrollcommand=sb.set)
        self.cases_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.cases_tree.bind('<<TreeviewSelect>>', self._on_case_selected)
        self.cases_tree.bind('<Double-1>',
                             lambda *_: self._open_stage_dialog())

        action_bar = ttk.Frame(parent, padding=(8, 0, 8, 8))
        action_bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(action_bar, text="Change Stage",
                   command=self._open_stage_dialog).pack(side=tk.LEFT)
        ttk.Button(action_bar, text="Close Case",
                   command=lambda: self._quick_stage('Closed')).pack(
            side=tk.LEFT, padx=6)
        ttk.Button(action_bar, text="Delete",
                   command=self._delete_selected_case).pack(side=tk.LEFT)

    # ---- Concerns tab ----
    def _build_concerns_tab(self, parent):
        top = ttk.Frame(parent, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)
        self.concerns_case_label = ttk.Label(
            top, text="(select a case in the Cases tab)",
            font=('Helvetica', 10, 'italic'))
        self.concerns_case_label.pack(side=tk.LEFT)

        cols = ('id', 'category', 'description', 'raised_by', 'raised_at')
        self.concerns_tree = ttk.Treeview(
            parent, columns=cols, show='headings', height=10)
        for c, w in zip(cols, (50, 160, 600, 140, 160)):
            self.concerns_tree.heading(c, text=c.replace('_', ' ').title())
            self.concerns_tree.column(c, width=w, anchor=tk.W)
        self.concerns_tree.pack(fill=tk.BOTH, expand=True, padx=8)

        form = ttk.LabelFrame(parent, text="Add Concern", padding=8)
        form.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=8)
        ttk.Label(form, text="Category:").grid(row=0, column=0, sticky=tk.W)
        self.concern_cat = ttk.Combobox(form, values=CONCERN_CATEGORIES,
                                        state='readonly', width=30)
        self.concern_cat.grid(row=0, column=1, sticky=tk.W, padx=4)
        ttk.Label(form, text="Description:").grid(row=1, column=0,
                                                  sticky=tk.NW, pady=4)
        self.concern_desc = tk.Text(form, height=3, width=80)
        self.concern_desc.grid(row=1, column=1, sticky=tk.W, padx=4)
        ttk.Button(form, text="Add", command=self._add_concern).grid(
            row=2, column=1, sticky=tk.E, pady=4)

    # ---- Events tab ----
    def _build_events_tab(self, parent):
        top = ttk.Frame(parent, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)
        self.events_case_label = ttk.Label(
            top, text="(select a case in the Cases tab)",
            font=('Helvetica', 10, 'italic'))
        self.events_case_label.pack(side=tk.LEFT)

        cols = ('id', 'event_type', 'notes', 'actor', 'occurred_at')
        self.events_tree = ttk.Treeview(
            parent, columns=cols, show='headings', height=10)
        for c, w in zip(cols, (50, 200, 600, 140, 160)):
            self.events_tree.heading(c, text=c.replace('_', ' ').title())
            self.events_tree.column(c, width=w, anchor=tk.W)
        self.events_tree.pack(fill=tk.BOTH, expand=True, padx=8)

        form = ttk.LabelFrame(parent, text="Add Event", padding=8)
        form.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=8)
        ttk.Label(form, text="Type:").grid(row=0, column=0, sticky=tk.W)
        self.event_type = ttk.Entry(form, width=40)
        self.event_type.grid(row=0, column=1, sticky=tk.W, padx=4)
        ttk.Label(form, text="Notes:").grid(row=1, column=0,
                                            sticky=tk.NW, pady=4)
        self.event_notes = tk.Text(form, height=3, width=80)
        self.event_notes.grid(row=1, column=1, sticky=tk.W, padx=4)
        ttk.Button(form, text="Add", command=self._add_event).grid(
            row=2, column=1, sticky=tk.E, pady=4)

    # ---- Outcomes tab ----
    def _build_outcomes_tab(self, parent):
        top = ttk.Frame(parent, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)
        self.outcomes_case_label = ttk.Label(
            top, text="(select a case in the Cases tab)",
            font=('Helvetica', 10, 'italic'))
        self.outcomes_case_label.pack(side=tk.LEFT)

        cols = ('id', 'outcome', 'sanction', 'conditions', 'review',
                'decided_by', 'decided_at')
        self.outcomes_tree = ttk.Treeview(
            parent, columns=cols, show='headings', height=10)
        for c, w in zip(cols, (50, 200, 160, 360, 100, 140, 160)):
            self.outcomes_tree.heading(c, text=c.replace('_', ' ').title())
            self.outcomes_tree.column(c, width=w, anchor=tk.W)
        self.outcomes_tree.pack(fill=tk.BOTH, expand=True, padx=8)

        form = ttk.LabelFrame(parent, text="Record Outcome", padding=8)
        form.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=8)
        ttk.Label(form, text="Outcome:").grid(row=0, column=0, sticky=tk.W)
        self.outcome_var = ttk.Combobox(form, values=OUTCOMES,
                                        state='readonly', width=35)
        self.outcome_var.grid(row=0, column=1, sticky=tk.W, padx=4)
        ttk.Label(form, text="Sanction:").grid(row=0, column=2, sticky=tk.W)
        self.sanction_var = ttk.Entry(form, width=25)
        self.sanction_var.grid(row=0, column=3, sticky=tk.W, padx=4)
        ttk.Label(form, text="Review date (YYYY-MM-DD):").grid(
            row=1, column=0, sticky=tk.W, pady=4)
        self.review_var = ttk.Entry(form, width=20)
        self.review_var.grid(row=1, column=1, sticky=tk.W, padx=4)
        ttk.Label(form, text="Conditions:").grid(row=2, column=0,
                                                 sticky=tk.NW, pady=4)
        self.conditions_text = tk.Text(form, height=3, width=80)
        self.conditions_text.grid(row=2, column=1, columnspan=3,
                                  sticky=tk.W, padx=4)
        ttk.Button(form, text="Record",
                   command=self._add_outcome).grid(
            row=3, column=3, sticky=tk.E, pady=4)

    # ============================================================
    # ACTIONS
    # ============================================================
    def _refresh_stats(self):
        s = self.db.stats()
        self.stats_var.set(
            f"Total: {s['total']}    Open: {s['open']}    "
            f"At Hearing: {s['hearing']}    High Risk: {s['high']}")

    def _refresh_cases(self):
        for r in self.cases_tree.get_children():
            self.cases_tree.delete(r)
        rows = self.db.list_cases(
            stage=self.filter_stage.get(),
            regulator=self.filter_regulator.get(),
            search=self.search_var.get().strip() or None)
        for row in rows:
            self.cases_tree.insert('', tk.END, values=row)
        self._refresh_stats()

    def _on_case_selected(self, *_):
        sel = self.cases_tree.selection()
        if not sel:
            return
        case_id = self.cases_tree.item(sel[0])['values'][0]
        self.selected_case_id = case_id
        case = self.db.get_case(case_id)
        if not case:
            return
        label = (f"Case #{case[0]} — Student {case[1]} — "
                 f"{case[3] or '?'} ({case[5]})")
        self.concerns_case_label.config(text=label)
        self.events_case_label.config(text=label)
        self.outcomes_case_label.config(text=label)
        self._reload_concerns()
        self._reload_events()
        self._reload_outcomes()

    def _reload_concerns(self):
        for r in self.concerns_tree.get_children():
            self.concerns_tree.delete(r)
        if self.selected_case_id:
            for row in self.db.list_concerns(self.selected_case_id):
                self.concerns_tree.insert('', tk.END, values=row)

    def _reload_events(self):
        for r in self.events_tree.get_children():
            self.events_tree.delete(r)
        if self.selected_case_id:
            for row in self.db.list_events(self.selected_case_id):
                self.events_tree.insert('', tk.END, values=row)

    def _reload_outcomes(self):
        for r in self.outcomes_tree.get_children():
            self.outcomes_tree.delete(r)
        if self.selected_case_id:
            for row in self.db.list_outcomes(self.selected_case_id):
                self.outcomes_tree.insert('', tk.END, values=row)

    def _require_case(self):
        if not self.selected_case_id:
            messagebox.showinfo("FtP", "Select a case in the Cases tab first.")
            return False
        return True

    # ---- New case dialog ----
    def _open_new_case_dialog(self):
        d = tk.Toplevel(self.root)
        d.title("New FtP Case")
        d.transient(self.root)
        d.grab_set()
        d.geometry("560x520")

        fields = {}

        def add(label, widget, row):
            ttk.Label(d, text=label).grid(row=row, column=0,
                                          sticky=tk.W, padx=8, pady=4)
            widget.grid(row=row, column=1, sticky=tk.W, padx=8, pady=4)

        fields['student_id'] = ttk.Entry(d, width=30)
        add("Student ID:", fields['student_id'], 0)
        fields['programme'] = ttk.Entry(d, width=30)
        add("Programme:", fields['programme'], 1)
        fields['regulator'] = ttk.Combobox(d, values=REGULATORS,
                                           state='readonly', width=27)
        fields['regulator'].set('NMC')
        add("Regulator:", fields['regulator'], 2)
        fields['registration_no'] = ttk.Entry(d, width=30)
        add("Registration #:", fields['registration_no'], 3)
        fields['stage'] = ttk.Combobox(d, values=STAGES,
                                       state='readonly', width=27)
        fields['stage'].set('Concern Raised')
        add("Stage:", fields['stage'], 4)
        fields['risk_level'] = ttk.Combobox(
            d, values=('Low', 'Medium', 'High'),
            state='readonly', width=27)
        fields['risk_level'].set('Medium')
        add("Risk Level:", fields['risk_level'], 5)
        fields['interim_order'] = ttk.Combobox(
            d, values=('None', 'Interim Conditions', 'Interim Suspension'),
            state='readonly', width=27)
        fields['interim_order'].set('None')
        add("Interim Order:", fields['interim_order'], 6)
        fields['placement_status'] = ttk.Combobox(
            d, values=('Continuing', 'Suspended', 'Withdrawn'),
            state='readonly', width=27)
        fields['placement_status'].set('Continuing')
        add("Placement:", fields['placement_status'], 7)
        fields['case_officer'] = ttk.Entry(d, width=30)
        fields['case_officer'].insert(0, current_username())
        add("Case Officer:", fields['case_officer'], 8)
        fields['panel_chair'] = ttk.Entry(d, width=30)
        add("Panel Chair:", fields['panel_chair'], 9)
        fields['source_record_id'] = ttk.Entry(d, width=30)
        add("Source disciplinary id (optional):",
            fields['source_record_id'], 10)
        ttk.Label(d, text="Summary:").grid(
            row=11, column=0, sticky=tk.NW, padx=8, pady=4)
        summary = tk.Text(d, height=5, width=40)
        summary.grid(row=11, column=1, sticky=tk.W, padx=8, pady=4)

        def save():
            sid = fields['student_id'].get().strip()
            if not sid:
                messagebox.showerror("FtP", "Student ID is required.")
                return
            try:
                src = fields['source_record_id'].get().strip()
                src_id = int(src) if src else None
            except ValueError:
                messagebox.showerror("FtP",
                                     "Source record id must be numeric.")
                return
            data = {k: w.get().strip() if hasattr(w, 'get') else None
                    for k, w in fields.items()}
            data['source_record_id'] = src_id
            data['summary'] = summary.get('1.0', tk.END).strip()
            try:
                case_id = self.db.create_case(data)
            except sqlite3.Error as e:
                messagebox.showerror("FtP", f"Could not create case:\n{e}")
                return
            messagebox.showinfo("FtP", f"Case #{case_id} opened.")
            d.destroy()
            self._refresh_cases()

        ttk.Button(d, text="Save", command=save).grid(
            row=12, column=1, sticky=tk.E, padx=8, pady=10)

    # ---- Stage change ----
    def _open_stage_dialog(self):
        if not self._require_case():
            return
        d = tk.Toplevel(self.root)
        d.title("Change Stage")
        d.transient(self.root)
        d.grab_set()
        ttk.Label(d, text="New stage:").grid(row=0, column=0,
                                             padx=8, pady=8, sticky=tk.W)
        cb = ttk.Combobox(d, values=STAGES, state='readonly', width=28)
        cb.grid(row=0, column=1, padx=8, pady=8)
        ttk.Label(d, text="Notes:").grid(row=1, column=0,
                                         padx=8, pady=4, sticky=tk.NW)
        notes = tk.Text(d, height=4, width=40)
        notes.grid(row=1, column=1, padx=8, pady=4)

        def apply():
            new_stage = cb.get()
            if not new_stage:
                return
            self.db.update_stage(self.selected_case_id, new_stage,
                                 notes.get('1.0', tk.END).strip())
            d.destroy()
            self._refresh_cases()
            self._reload_events()

        ttk.Button(d, text="Apply", command=apply).grid(
            row=2, column=1, sticky=tk.E, padx=8, pady=10)

    def _quick_stage(self, stage):
        if not self._require_case():
            return
        if not messagebox.askyesno(
                "FtP", f"Set case #{self.selected_case_id} to '{stage}'?"):
            return
        self.db.update_stage(self.selected_case_id, stage)
        self._refresh_cases()
        self._reload_events()

    def _delete_selected_case(self):
        if not self._require_case():
            return
        if not messagebox.askyesno(
                "FtP",
                f"Delete case #{self.selected_case_id} and all its "
                "concerns/events/outcomes? This cannot be undone."):
            return
        self.db.delete_case(self.selected_case_id)
        self.selected_case_id = None
        self._refresh_cases()
        self._reload_concerns()
        self._reload_events()
        self._reload_outcomes()

    # ---- Concerns / events / outcomes adders ----
    def _add_concern(self):
        if not self._require_case():
            return
        cat = self.concern_cat.get()
        desc = self.concern_desc.get('1.0', tk.END).strip()
        if not cat or not desc:
            messagebox.showerror("FtP", "Category and description required.")
            return
        self.db.add_concern(self.selected_case_id, cat, desc)
        self.concern_desc.delete('1.0', tk.END)
        self._reload_concerns()
        self._reload_events()

    def _add_event(self):
        if not self._require_case():
            return
        et = self.event_type.get().strip()
        notes = self.event_notes.get('1.0', tk.END).strip()
        if not et:
            messagebox.showerror("FtP", "Event type required.")
            return
        self.db.add_event(self.selected_case_id, et, notes)
        self.event_type.delete(0, tk.END)
        self.event_notes.delete('1.0', tk.END)
        self._reload_events()

    def _add_outcome(self):
        if not self._require_case():
            return
        outcome = self.outcome_var.get()
        if not outcome:
            messagebox.showerror("FtP", "Select an outcome.")
            return
        self.db.add_outcome(
            self.selected_case_id,
            outcome,
            self.sanction_var.get().strip(),
            self.conditions_text.get('1.0', tk.END).strip(),
            self.review_var.get().strip())
        self.sanction_var.delete(0, tk.END)
        self.review_var.delete(0, tk.END)
        self.conditions_text.delete('1.0', tk.END)
        self._reload_outcomes()
        self._reload_events()

    # ---- Export ----
    def _export_cases_csv(self):
        path = filedialog.asksaveasfilename(
            title="Export FtP cases",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"ftp_cases_{datetime.now():%Y%m%d}.csv")
        if not path:
            return
        rows = self.db.list_cases(
            stage=self.filter_stage.get(),
            regulator=self.filter_regulator.get(),
            search=self.search_var.get().strip() or None)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(('case_id', 'student_id', 'name', 'programme',
                        'regulator', 'stage', 'risk', 'officer', 'opened'))
            w.writerows(rows)
        messagebox.showinfo("FtP", f"Exported {len(rows)} rows.")
