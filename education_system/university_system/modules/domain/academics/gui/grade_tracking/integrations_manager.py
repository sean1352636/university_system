"""Integrations manager for the grade tracking GUI.

Mirrors ``assignment_system/integrations_manager.py`` — provides
dialogs for the read-side (parent grades, child appeal form, audit
export) plus a cross-domain activity panel listing rows produced
by the silent hooks (early-warning indicators, wellbeing referrals,
grade appeals, calendar events, aid GPA reviews, legal cases).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.university_system.modules.domain.academics.gui.grade_tracking.integrations import (
    fetch_child_grades,
    create_wellbeing_referral,
    file_grade_appeal_ticket,
    export_grade_audit_for_legal,
    recent_early_warning_indicators,
    recent_wellbeing_referrals,
    recent_grade_appeal_tickets,
    recent_assessment_calendar_events,
    recent_aid_gpa_reviews,
    recent_grade_legal_cases,
)


class GradeIntegrationsManager:
    """Cross-domain dialogs + activity panel for the grade GUI."""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.auth = getattr(app, "auth", None)

    # ------------------------------------------------------------------
    # Per-student dialogs
    # ------------------------------------------------------------------

    def show_child_grades(self, student_id: str):
        """Show recorded grades for a child — meant for parent users."""
        if not student_id:
            messagebox.showinfo("Child Grades", "No student selected.")
            return
        rows = fetch_child_grades(student_id)
        win = tk.Toplevel(self.root)
        win.title(f"Grades — {student_id}")
        win.geometry("760x500")
        ttk.Label(
            win, text=f"Grades recorded for student {student_id}",
            font=("Helvetica", 12, "bold"),
        ).pack(anchor="w", padx=15, pady=(15, 5))
        if not rows:
            ttk.Label(
                win, text="No grades recorded yet.", foreground="#7f8c8d",
            ).pack(padx=15, pady=20)
        else:
            cols = ("module_code", "module_name", "assessment_name",
                    "grade", "percentage", "grade_date", "is_final")
            tree = ttk.Treeview(win, columns=cols, show="headings")
            for c, w in zip(cols, (90, 180, 160, 80, 80, 110, 70)):
                tree.heading(c, text=c.replace("_", " ").title())
                tree.column(c, width=w, anchor="w")
            for r in rows:
                tree.insert("", "end", values=tuple(
                    r.get(c, "") if r.get(c) is not None else "" for c in cols
                ))
            tree.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))

    def open_wellbeing_referral(self, student_id: str):
        """Prompt for a description, then create a wellbeing referral."""
        if not student_id:
            messagebox.showinfo("Referral", "No student selected.")
            return
        desc = simpledialog.askstring(
            "Wellbeing Referral",
            f"Describe the academic concern for student {student_id}:",
            parent=self.root,
        )
        if not desc:
            return
        urgency = simpledialog.askstring(
            "Wellbeing Referral",
            "Urgency (low / medium / high):",
            initialvalue="medium",
            parent=self.root,
        ) or "medium"
        rid = create_wellbeing_referral(
            student_id=student_id,
            referred_by=(self.auth.current_user or {}).get("username") if self.auth else None,
            description=desc,
            urgency=urgency,
        )
        if rid:
            messagebox.showinfo(
                "Referral", f"Wellbeing referral #{rid} created.",
            )
        else:
            messagebox.showwarning(
                "Referral",
                "Could not create referral (table missing or insert failed).",
            )

    def open_grade_appeal(self, *, student_id: str, module_code: str = "",
                          assessment_name: str = "", current_grade: str = ""):
        """Modal: ask for reason, then file a helpdesk ticket."""
        if not student_id:
            messagebox.showinfo("Appeal", "No student selected.")
            return
        reason = simpledialog.askstring(
            "Grade Appeal",
            f"Reason for appeal of {assessment_name or 'this grade'}:",
            parent=self.root,
        )
        if not reason:
            return
        user = (self.auth.current_user or {}) if self.auth else {}
        ticket_id = file_grade_appeal_ticket(
            user_id=user.get("id"),
            student_id=student_id,
            module_code=module_code,
            assessment_name=assessment_name,
            current_grade=current_grade,
            reason=reason,
        )
        if ticket_id:
            messagebox.showinfo(
                "Appeal Filed",
                f"Helpdesk ticket #{ticket_id} opened. Academic Affairs will follow up.",
            )
        else:
            messagebox.showwarning(
                "Appeal", "Could not file appeal ticket (helpdesk table missing).",
            )

    def export_audit_for_legal(self, student_id: str):
        if not student_id:
            messagebox.showinfo("Audit Export", "No student selected.")
            return
        if not messagebox.askyesno(
            "Audit Export",
            f"Export grade-audit trail for {student_id} and open a legal case?",
        ):
            payload = export_grade_audit_for_legal(student_id=student_id)
            if payload is None:
                return
            messagebox.showinfo(
                "Audit Export",
                f"Bundled {len(payload['audit_rows'])} audit row(s). "
                "No legal case opened.",
            )
            return
        user = (self.auth.current_user or {}) if self.auth else {}
        payload = export_grade_audit_for_legal(
            student_id=student_id,
            open_case=True,
            student_name=user.get("display_name", ""),
            created_by=str(user.get("id", "")),
        )
        if not payload:
            messagebox.showwarning("Audit Export", "Export failed.")
            return
        case_part = (
            f"Legal case #{payload['case_id']} opened. "
            if payload.get("case_id") else
            "Legal case could not be opened (legal services unavailable). "
        )
        messagebox.showinfo(
            "Audit Export",
            f"{case_part}{len(payload['audit_rows'])} audit row(s) attached.",
        )

    # ------------------------------------------------------------------
    # Cross-domain activity panel
    # ------------------------------------------------------------------

    _ACTIVITY_TABS = (
        ("warnings", "Early-Warning Indicators",
         recent_early_warning_indicators,
         ("indicator_id", "student_id", "indicator_value", "severity",
          "detected_at", "is_resolved")),
        ("referrals", "Wellbeing Referrals",
         recent_wellbeing_referrals,
         ("id", "student_id", "referred_by", "urgency", "status", "created_at")),
        ("appeals", "Grade-Appeal Tickets",
         recent_grade_appeal_tickets,
         ("ticket_id", "student_id", "subject", "status", "priority",
          "created_at")),
        ("calendar", "Assessment Calendar",
         recent_assessment_calendar_events,
         ("id", "name", "date", "last_modified")),
        ("aid", "Aid GPA Reviews",
         recent_aid_gpa_reviews,
         ("aid_id", "student_id", "aid_type", "status", "updated_at")),
        ("legal", "Audit-Export Cases",
         recent_grade_legal_cases,
         ("case_id", "case_number", "client_id", "case_title", "status",
          "created_at")),
    )

    def show_integrations_activity(self):
        win = tk.Toplevel(self.root)
        win.title("Cross-Domain Activity — Grade Tracking")
        win.geometry("960x560")
        ttk.Label(
            win,
            text=(
                "Recent rows produced by the grade-tracking GUI in other "
                "subsystems. Empty tabs = the trigger action hasn't fired "
                "yet."
            ),
            wraplength=920, justify="left",
        ).pack(anchor="w", padx=15, pady=(15, 5))
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        trees = {}
        for key, label, fetcher, cols in self._ACTIVITY_TABS:
            tab = ttk.Frame(nb)
            nb.add(tab, text=label)
            tree = ttk.Treeview(tab, columns=cols, show="headings")
            for c in cols:
                tree.heading(c, text=c.replace("_", " ").title())
                tree.column(c, width=140, anchor="w")
            tree.pack(fill="both", expand=True)
            trees[key] = (tree, fetcher, cols)

        def reload(*_):
            for tree, fetcher, cols in trees.values():
                for i in tree.get_children():
                    tree.delete(i)
                for r in (fetcher() or []):
                    tree.insert(
                        "", "end",
                        values=tuple(self._fmt(r.get(c)) for c in cols),
                    )

        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(bar, text="Refresh", command=reload).pack(side="left")
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
        reload()

    @staticmethod
    def _fmt(value) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)
