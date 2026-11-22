"""Parameter forms for behaviour and pastoral operations.

Split out of ``bulk_operations_views.py``, which re-exports every name here.
"""

from __future__ import annotations

from tkinter import ttk
import tkinter as tk

from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.view_common import (
    _today,
)


class PastoralFormsMixin:
    """Parameter forms for behaviour and pastoral operations."""

    def _build_behaviour_form(self) -> None:
        f = self.params_frame
        self.p_type   = self._combo(f, 0, "Type:",
                                       ["Positive", "Negative"],
                                       default="Positive")
        self.p_cat    = self._entry(f, 1, "Category:")
        self.p_desc   = self._entry(f, 2, "Description:")
        self.p_date   = self._entry(f, 3, "Date:", _today(), width=14)
        self.p_sev    = self._combo(f, 4, "Severity:",
                                       ["", "Low", "Medium", "High"],
                                       default="")
        self.p_loc    = self._entry(f, 5, "Location:")
        self.p_by     = self._entry(f, 6, "Recorded by:")

    def _build_accommodation_form(self) -> None:
        f = self.params_frame
        self.p_name   = self._entry(f, 0, "Name:")
        self.p_cat    = self._entry(f, 1, "Category:", "Exam Access")
        self.p_desc   = self._entry(f, 2, "Description:")
        self.p_status = self._entry(f, 3, "Status:", "Active", width=14)
        self.p_start  = self._entry(f, 4, "Start date:", _today(), width=14)
        self.p_end    = self._entry(f, 5, "End date:", width=14)
        self.p_appby  = self._entry(f, 6, "Approved by:")
        self.p_appdate = self._entry(f, 7, "Approved date:", width=14)

    def _build_detention_form(self) -> None:
        f = self.params_frame
        self.p_date = self._entry(f, 0, "Date:", _today(), width=14)
        self.p_reason = self._entry(f, 1, "Reason:")
        self.p_duration = self._entry(f, 2, "Duration (min):",
                                          "30", width=8)
        self.p_room = self._entry(f, 3, "Room:")
        self.p_severity = self._combo(f, 4, "Severity:",
                                          ["Low", "Medium", "High"],
                                          default="Low")
        self.p_by = self._entry(f, 5, "Recorded by:")

    def _build_merits_form(self) -> None:
        f = self.params_frame
        self.p_date = self._entry(f, 0, "Date:", _today(), width=14)
        self.p_category = self._combo(
            f, 1, "Category:",
            ["Excellent Work", "Participation", "Helpfulness",
             "Leadership", "Improvement", "Achievement",
             "Attendance", "Effort", "Community Contribution",
             "Other"], default="Achievement")
        self.p_desc = self._entry(f, 2, "Description:")
        self.p_points = self._entry(f, 3, "Points:", "5", width=8)
        self.p_by = self._entry(f, 4, "Recorded by:")

    def _build_escalate_form(self) -> None:
        f = self.params_frame
        self.p_date = self._entry(f, 0, "Date:", _today(), width=14)
        self.p_reason = self._entry(f, 1, "Reason:")
        self.p_to = self._entry(f, 2, "Escalate to:", "Senior Tutor")
        self.p_followup = self._entry(f, 3, "Follow-up date:", width=14)
        self.p_by = self._entry(f, 4, "Recorded by:")

    def _build_safeguarding_form(self) -> None:
        from education_system.systems.sixth_form.domain.safeguarding.safeguarding import (
            CONCERN_TYPES, CATEGORIES, RISK_LEVELS,
        )
        f = self.params_frame
        self.p_cdate = self._entry(f, 0, "Concern date:",
                                       _today(), width=14)
        self.p_rdate = self._entry(f, 1, "Reported date:",
                                       _today(), width=14)
        self.p_ctype = self._combo(f, 2, "Concern type:",
                                       list(CONCERN_TYPES),
                                       default=CONCERN_TYPES[0])
        self.p_category = self._combo(f, 3, "Category:",
                                          list(CATEGORIES),
                                          default=CATEGORIES[0])
        self.p_risk = self._combo(f, 4, "Risk level:",
                                      list(RISK_LEVELS),
                                      default="Medium")
        self.p_by = self._entry(f, 5, "Reported by:")
        self.p_desc = self._entry(f, 6, "Description:")
        self.p_dsl = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="DSL notified",
                          variable=self.p_dsl).grid(
            row=7, column=1, sticky="w", padx=6, pady=3)
        self.p_dsl_name = self._entry(f, 8, "DSL name:")

    def _build_mentors_form(self) -> None:
        from education_system.systems.sixth_form.domain.pastoral.peer_mentoring.peer_mentoring import (
            PROGRAMMES, FREQUENCIES, DEFAULT_FREQUENCY,
        )
        f = self.params_frame
        ttk.Label(f, text="Selected students above are MENTEES.",
                   foreground="#555").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.p_mentor = self._entry(f, 1, "Mentor student id:", width=14)
        self.p_programme = self._combo(f, 2, "Programme:",
                                            list(PROGRAMMES),
                                            default=PROGRAMMES[0])
        self.p_start = self._entry(f, 3, "Start date:",
                                       _today(), width=14)
        self.p_frequency = self._combo(f, 4, "Frequency:",
                                            list(FREQUENCIES),
                                            default=DEFAULT_FREQUENCY)
        self.p_coord = self._entry(f, 5, "Coordinator:")
        self.p_planned = self._entry(f, 6, "Planned end:", width=14)
        self.p_sessions = self._entry(f, 7, "Sessions planned:",
                                          width=8)

    # ── Comms / finance / exams form builders ─────────────────────
    def _build_reset_points_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "Window from:", width=14)
        self.p_date_to = self._entry(f, 1, "Window to:",
                                       _today(), width=14)
        self.p_reset_date = self._entry(f, 2, "Reset date:",
                                          _today(), width=14)
        self.p_note = self._entry(f, 3, "Note:", "Term reset")
        self.p_by = self._entry(f, 4, "Recorded by:")
