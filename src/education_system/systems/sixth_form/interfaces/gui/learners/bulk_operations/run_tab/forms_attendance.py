"""Parameter forms for attendance operations.

Split out of ``bulk_operations_views.py``, which re-exports every name here.
"""

from __future__ import annotations

from tkinter import ttk
import tkinter as tk

from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.view_common import (
    _today,
)


class AttendanceFormsMixin:
    """Parameter forms for attendance operations."""

    def _build_mark_attendance_form(self) -> None:
        f = self.params_frame
        self.p_slot = self._slot_combo(f, 0, "Slot:")
        self.p_date = self._entry(f, 1, "Date:", _today(), width=14)
        self.p_status = self._combo(
            f, 2, "Status:",
            ["Present", "Late", "Absent", "Authorised"],
            default="Present")
        self.p_minutes = self._entry(f, 3, "Minutes late:", width=8)
        self.p_notes = self._entry(f, 4, "Notes:")

    def _build_authorise_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "From date:", width=14)
        self.p_date_to = self._entry(f, 1, "To date:",
                                       _today(), width=14)
        self.p_target = self._combo(f, 2, "Target status:",
                                       ["Authorised", "Absent"],
                                       default="Authorised")
        self.p_reason = self._entry(f, 3, "Reason / code:")

    def _build_lateness_form(self) -> None:
        f = self.params_frame
        self.p_slot = self._slot_combo(f, 0, "Slot:")
        self.p_date = self._entry(f, 1, "Date:", _today(), width=14)
        self.p_minutes = self._entry(f, 2, "Minutes late:", "5", width=8)
        self.p_threshold = self._entry(
            f, 3, "Auto-log behaviour at ≥ min (blank=off):", width=8)
        self.p_by = self._entry(f, 4, "Behaviour recorded-by:")

    def _build_import_csv_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=("Required columns: student_id, slot_id, "
                            "date, status\n"
                            "Optional columns: minutes_late, notes"),
                   foreground="#555").grid(row=0, column=0, columnspan=3,
                                             sticky="w", pady=(0, 6))
        self.p_csv = self._entry(f, 1, "CSV path:", width=46)
        from education_system.platform.delivery.gui.parented_dialogs import filedialog

        def _browse() -> None:
            path = filedialog.askopenfilename(
                title="Pick attendance CSV",
                filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
            if path:
                self.p_csv.delete(0, "end")
                self.p_csv.insert(0, path)

        ttk.Button(f, text="Browse…", command=_browse).grid(
            row=1, column=2, sticky="w", padx=4)

    def _build_recalc_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0,
                                          "From date (blank=all):",
                                          width=14)
        self.p_date_to = self._entry(f, 1,
                                        "To date (blank=all):", width=14)

    def _build_flag_low_form(self) -> None:
        f = self.params_frame
        self.p_threshold = self._entry(f, 0, "Threshold %:",
                                          "90", width=8)
        self.p_window = self._entry(f, 1, "Window (days):",
                                       "28", width=8)
        self.p_level = self._combo(f, 2, "Level:",
                                      ["Low", "Medium", "High", "Critical"],
                                      default="Medium")
        self.p_reason = self._entry(f, 3, "Reason:",
                                       "Low overall attendance")
        self.p_by = self._entry(f, 4, "Raised by:")
        self.p_skip_open = tk.BooleanVar(value=True)
        ttk.Checkbutton(f,
                          text="Skip students who already have an open "
                                "concern",
                          variable=self.p_skip_open).grid(
            row=5, column=1, sticky="w", padx=6, pady=3)

    def _build_signoff_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text="Slots:").grid(row=0, column=0,
                                            sticky="ne", pady=3)
        list_frame = ttk.Frame(f)
        list_frame.grid(row=0, column=1, sticky="w", padx=6, pady=3)
        opts = self._slot_options()
        self._signoff_slot_map: dict[str, int] = {}
        self.p_slots_lb = tk.Listbox(list_frame, selectmode="extended",
                                       height=8, width=52,
                                       exportselection=False)
        for sid, lbl in opts:
            iid = self.p_slots_lb.size()
            self.p_slots_lb.insert("end", lbl)
            self._signoff_slot_map[str(iid)] = sid
        vs = ttk.Scrollbar(list_frame, orient="vertical",
                            command=self.p_slots_lb.yview)
        self.p_slots_lb.configure(yscrollcommand=vs.set)
        self.p_slots_lb.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.p_date = self._entry(f, 1, "Date:", _today(), width=14)
        self.p_default = self._combo(f, 2, "Fill blanks as:",
                                        ["Present", "Absent", "Authorised"],
                                        default="Present")

    # ── Items 1–10 forms ──────────────────────────────────────────

    def _build_mark_holiday_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "From date:", width=14)
        self.p_date_to = self._entry(f, 1, "To date:", width=14)
        self.p_reason = self._entry(
            f, 2, "Reason:", "Authorised holiday", width=32)

    def _build_clear_attendance_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "From date:", width=14)
        self.p_date_to = self._entry(f, 1, "To date:", width=14)
        self.p_only_status = self._combo(
            f, 2, "Restrict to (optional):",
            ["", "Present", "Late", "Absent", "Authorised"],
            default="")

    def _build_late_unauth_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "From date:", width=14)
        self.p_date_to = self._entry(f, 1, "To date:", width=14)
        self.p_over = self._entry(
            f, 2, "Convert when minutes_late >:", "15", width=8)
        self.p_reason = self._entry(
            f, 3, "Reason:",
            "Late > threshold — unauthorised", width=32)

    def _build_attendance_letters_form(self) -> None:
        f = self.params_frame
        self.p_window = self._entry(f, 0, "Window (days):", "28", width=8)
        self.p_s1 = self._entry(f, 1, "Stage 1 below %:", "95", width=8)
        self.p_s2 = self._entry(f, 2, "Stage 2 below %:", "90", width=8)
        self.p_s3 = self._entry(f, 3, "Stage 3 below %:", "85", width=8)
        self.p_sender = self._entry(f, 4, "Sender staff id:")
        self.p_send = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Actually send (uncheck to just queue/log)",
                         variable=self.p_send).grid(
            row=5, column=1, sticky="w", padx=6, pady=3)

    def _build_punctuality_form(self) -> None:
        f = self.params_frame
        self.p_date_from = self._entry(f, 0, "From date:", width=14)
        self.p_date_to = self._entry(
            f, 1, "To date:", _today(), width=14)
        self.p_sender = self._entry(f, 2, "Sender staff id:")

    def _build_register_closure_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text="Slots:").grid(row=0, column=0,
                                           sticky="ne", pady=3)
        list_frame = ttk.Frame(f)
        list_frame.grid(row=0, column=1, sticky="w", padx=6, pady=3)
        opts = self._slot_options()
        self._closure_slot_map: dict[str, int] = {}
        self.p_closure_slots_lb = tk.Listbox(
            list_frame, selectmode="extended",
            height=8, width=52, exportselection=False)
        for sid, lbl in opts:
            iid = self.p_closure_slots_lb.size()
            self.p_closure_slots_lb.insert("end", lbl)
            self._closure_slot_map[str(iid)] = sid
        vs = ttk.Scrollbar(list_frame, orient="vertical",
                            command=self.p_closure_slots_lb.yview)
        self.p_closure_slots_lb.configure(yscrollcommand=vs.set)
        self.p_closure_slots_lb.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.p_date_from = self._entry(f, 1, "From date:", width=14)
        self.p_date_to = self._entry(f, 2, "To date:", width=14)
        self.p_default = self._combo(
            f, 3, "Fill blanks as:",
            ["Present", "Absent", "Authorised"], default="Present")
        self.p_notes = self._entry(f, 4, "Notes:")
