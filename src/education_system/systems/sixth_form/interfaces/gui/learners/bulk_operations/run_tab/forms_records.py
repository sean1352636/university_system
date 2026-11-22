"""Parameter forms for records / lifecycle operations.

Split out of ``bulk_operations_views.py``, which re-exports every name here.
"""

from __future__ import annotations

from datetime import date as _date
from tkinter import ttk
import tkinter as tk

from education_system.systems.sixth_form.domain.learners.bulk_operations import base as bulk_base
from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_records as bulk_ops_records
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import SAFE_STUDENT_FIELDS

from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.view_common import (
    _today,
)


class RecordsFormsMixin:
    """Parameter forms for records / lifecycle operations."""

    def _build_update_form(self) -> None:
        f = self.params_frame
        self.p_field = self._combo(f, 0, "Field:",
                                      list(SAFE_STUDENT_FIELDS),
                                      default=SAFE_STUDENT_FIELDS[0])
        self.p_value = self._entry(f, 1, "New value:")

    def _build_archive_form(self) -> None:
        from education_system.systems.sixth_form.domain.learners.alumni.models import (
            DESTINATION_TYPES,
            LEAVING_REASONS,
            DEFAULT_DESTINATION,
            DEFAULT_LEAVING_REASON,
        )
        f = self.params_frame
        self.p_year   = self._entry(f, 0, "Leaving year:",
                                       str(_date.today().year), width=8)
        self.p_date   = self._entry(f, 1, "Leaving date:",
                                       _today(), width=14)
        self.p_reason = self._combo(f, 2, "Leaving reason:",
                                       list(LEAVING_REASONS),
                                       default=DEFAULT_LEAVING_REASON)
        self.p_dest   = self._combo(f, 3, "Destination:",
                                       list(DESTINATION_TYPES),
                                       default=DEFAULT_DESTINATION)
        self.p_delete = tk.BooleanVar(value=False)
        ttk.Checkbutton(f,
                          text="Also delete student rows "
                                "(cascade-removes history)",
                          variable=self.p_delete).grid(
            row=4, column=1, sticky="w", padx=6, pady=3)

    def _build_promote_form(self) -> None:
        f = self.params_frame
        self.p_year = self._entry(f, 0, "New academic year:",
                                       width=14)
        self.p_bump = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Bump year_group +1",
                          variable=self.p_bump).grid(
            row=1, column=1, sticky="w", padx=6, pady=3)

    def _build_leavers_form(self) -> None:
        f = self.params_frame
        self.p_date = self._entry(f, 0, "Leaving date:",
                                       _today(), width=14)
        self.p_reason = self._entry(f, 1, "Leaving reason:")

    def _build_reinstate_form(self) -> None:
        self.p_ids = self._entry(
            self.params_frame, 0, "Alumni ids (comma):", width=30)

    def _build_gdpr_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=("Blank = phone, personal_email, and "
                            "emergency_contact_*"),
                   foreground="#555").grid(row=0, column=0,
                                              columnspan=2,
                                              sticky="w", pady=(0, 4))
        self.p_fields = self._entry(
            f, 1, "Fields (comma):", width=46)

    def _build_export_records_form(self) -> None:
        self.p_outpath = self._file_picker(
            self.params_frame, 0, "Output CSV:", save=True)

    def _build_anonymise_form(self) -> None:
        self.p_ids = self._entry(
            self.params_frame, 0, "Alumni ids (comma):", width=30)

    def _build_inventory_form(self) -> None:
        f = self.params_frame
        self.p_kind = self._combo(
            f, 0, "Kind:", list(bulk_ops_records.VALID_INVENTORY_KINDS),
            default="Locker")
        self.p_start = self._entry(f, 1, "Starting number:",
                                        "1", width=8)
        self.p_prefix = self._entry(f, 2, "Prefix:", width=12)
        self.p_pad = self._entry(f, 3, "Zero-pad digits:",
                                       "4", width=4)
        self.p_by = self._entry(f, 4, "Assigned by:")

    def _build_photos_form(self) -> None:
        f = self.params_frame
        self.p_zip = self._file_picker(f, 0, "ZIP:")
        self.p_outdir = self._file_picker(
            f, 1, "Output dir:", dir_only=True)

    def _build_contacts_csv_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=("Required: student_id\n"
                            "Optional: phone, "
                            "emergency_contact_name/phone/relation"),
                   foreground="#555").grid(row=0, column=0, columnspan=3,
                                              sticky="w", pady=(0, 6))
        self.p_csv = self._file_picker(f, 1, "CSV:")

    def _build_pwreset_form2(self) -> None:
        f = self.params_frame
        self.p_clear = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f, text="Clear flag (instead of setting it)",
            variable=self.p_clear).grid(row=0, column=1,
                                            sticky="w", padx=6, pady=3)
        self.p_reason = self._entry(f, 1, "Reason:")
        self.p_by = self._entry(f, 2, "Flagged by:")

    def _build_undo_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=("Undoable: " + ", ".join(bulk_ops_records._UNDOABLE)),
                   foreground="#555", wraplength=520,
                   justify="left").grid(row=0, column=0, columnspan=2,
                                            sticky="w", pady=(0, 6))
        self.p_jid = self._entry(f, 1, "Job id to undo:", width=10)

    def _build_schedule_form(self) -> None:
        f = self.params_frame
        self.p_name = self._entry(f, 0, "Schedule name:")
        self.p_op = self._combo(
            f, 1, "Operation:", list(bulk_base.OPERATIONS),
            default="log_behaviour", width=28)
        self.p_cron = self._entry(f, 2,
                                       "Cron (e.g. 0 9 * * 1):",
                                       width=20)
        self.p_next = self._entry(f, 3,
                                       "First run (YYYY-MM-DD HH:MM):",
                                       width=20)
        self.p_params = self._entry(
            f, 4, "Parameters (k=v,...):", width=40)
        self.p_by = self._entry(f, 5, "Created by:")
