"""Provider, dashboard and screening GUI panels for the Health Portal.

These panels close the gap between the appointment CLI
(``domain/health/appointments/appointment_booking.py``) and the Health Portal
GUI. They do **not** reimplement any persistence: every action drives the exact
same service function the CLI menus call. The service layer is print/input
oriented, so each panel captures the function's stdout for display and feeds
validated form values to ``input()``.

Each panel is a self-contained ``ttk.Frame`` constructed as
``Panel(parent, auth)`` (matching the embedded ``DentistGUI`` pattern). The
orchestrator is responsible for wiring these into the navigation.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, scrolledtext

# --- Service functions (the SAME ones the appointment CLI calls) -------------
from education_system.post_18.university_system.modules.domain.health.appointments.appointment_booking import (
    add_provider_schedule,
    view_provider_schedules,
    update_provider_schedule,
    manage_provider_time_off,
    schedule_templates,
    provider_availability_report,
    todays_schedule,
    provider_statistics,
    create_screening_schedule,
    schedule_screening_appointment,
)
from education_system.post_18.university_system.modules.domain.health.services import (
    block_time_slots,
    patient_queue,
    pending_tasks,
    quick_patient_lookup,
    critical_alerts_dashboard,
)
from education_system.post_18.university_system.modules.domain.health.records.clinical.lab_results import (
    recent_lab_results_dashboard,
)
from education_system.post_18.university_system.modules.domain.health.records.vaccinations.tracking import (
    vaccination_due_list,
)
from education_system.post_18.university_system.modules.domain.health.records.screening.schedules import (
    view_due_screenings,
    overdue_screenings,
)
from education_system.post_18.university_system.modules.domain.health.records.screening.results import (
    record_screening_results,
)
from education_system.post_18.university_system.modules.domain.health.records.screening.reminders import (
    screening_reminders,
    population_screening_reports,
)
from education_system.post_18.university_system.modules.domain.health.records.screening.guidelines import (
    screening_guidelines,
)


_MAX_INPUT_CALLS = 60  # guard against runaway input() validation loops


def run_service(func, auth, inputs=None):
    """Invoke a CLI service ``func(auth)``, feeding ``inputs`` to input() and
    returning everything the function printed. Persistence happens inside the
    service function exactly as it does from the CLI."""
    queue = list(inputs or [])
    calls = {"n": 0}

    def fake_input(prompt=""):
        calls["n"] += 1
        if calls["n"] > _MAX_INPUT_CALLS:
            raise RuntimeError("Too many input prompts; aborting to avoid a loop.")
        return queue.pop(0) if queue else ""

    buf = io.StringIO()
    real_input = builtins.input
    builtins.input = fake_input
    try:
        with contextlib.redirect_stdout(buf):
            func(auth)
    except Exception as exc:  # surface service errors in the output pane
        buf.write(f"\n[Error running operation: {exc}]\n")
    finally:
        builtins.input = real_input
    return buf.getvalue()


def _valid_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _valid_time(value):
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except ValueError:
        return False


class _ServicePanelBase(ttk.Frame):
    """Common layout: a heading, an action/form column and an output pane."""

    heading = "Panel"

    def __init__(self, parent, auth=None):
        super().__init__(parent, padding=10)
        self.auth = auth
        try:
            self.grid(row=0, column=0, sticky="nsew")
            parent.columnconfigure(0, weight=1)
            parent.rowconfigure(0, weight=1)
        except tk.TclError:
            self.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self, text=self.heading, font=("Arial", 15, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        self.body = ttk.Frame(self)
        self.body.grid(row=1, column=0, sticky="nsw", padx=(0, 10))

        out_frame = ttk.LabelFrame(self, text="Output", padding=5)
        out_frame.grid(row=1, column=1, sticky="nsew")
        self.output = scrolledtext.ScrolledText(out_frame, width=70, height=28,
                                                wrap="word", font=("Courier", 9))
        self.output.pack(fill=tk.BOTH, expand=True)

        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        self.build_controls()

    # -- helpers ------------------------------------------------------------
    def build_controls(self):  # pragma: no cover - overridden
        raise NotImplementedError

    def show(self, text):
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", text or "(no output)")

    def run(self, func, inputs=None):
        self.show(run_service(func, self.auth, inputs))

    def _add_button(self, row, text, command):
        ttk.Button(self.body, text=text, width=28, command=command).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=2
        )

    def _add_entry(self, row, label, default="", width=22):
        ttk.Label(self.body, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        var = tk.StringVar(value=default)
        ttk.Entry(self.body, textvariable=var, width=width).grid(
            row=row, column=1, sticky=tk.W, pady=2, padx=(5, 0)
        )
        return var


class ProviderSchedulePanel(_ServicePanelBase):
    """Provider Schedule Management — add/view/update schedules, block time,
    holiday/vacation, templates and the availability report."""

    heading = "Provider Schedule Management"
    nav_label = "Provider Schedules"

    _DAYS = [("Monday", 1), ("Tuesday", 2), ("Wednesday", 3), ("Thursday", 4),
             ("Friday", 5), ("Saturday", 6), ("Sunday", 7)]

    def build_controls(self):
        r = 0
        # --- Add schedule form ---
        ttk.Label(self.body, text="Add Provider Schedule",
                  font=("Arial", 10, "bold")).grid(row=r, column=0, columnspan=2, sticky=tk.W, pady=(4, 2)); r += 1
        self.a_provider = self._add_entry(r, "Provider name:"); r += 1
        ttk.Label(self.body, text="Day of week:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.a_day = tk.StringVar(value="Monday")
        ttk.Combobox(self.body, textvariable=self.a_day, width=20, state="readonly",
                     values=[d[0] for d in self._DAYS]).grid(row=r, column=1, sticky=tk.W, padx=(5, 0)); r += 1
        self.a_start = self._add_entry(r, "Start time (HH:MM):", "09:00"); r += 1
        self.a_end = self._add_entry(r, "End time (HH:MM):", "17:00"); r += 1
        self.a_max = self._add_entry(r, "Max appts/hour:", "4"); r += 1
        self.a_specialty = self._add_entry(r, "Specialty:", "General"); r += 1
        self.a_location = self._add_entry(r, "Location:", "Health Center"); r += 1
        self._add_button(r, "Add Schedule", self.on_add); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        # --- View / report / templates / holiday ---
        self.v_filter = self._add_entry(r, "View filter (provider):", ""); r += 1
        self._add_button(r, "View Schedules", self.on_view); r += 1
        self._add_button(r, "Availability Report", self.on_report); r += 1
        self._add_button(r, "Schedule Templates", self.on_templates); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        # --- Update schedule ---
        self.u_id = self._add_entry(r, "Update: schedule ID:", ""); r += 1
        self.u_start = self._add_entry(r, "New start (blank=keep):", ""); r += 1
        self.u_end = self._add_entry(r, "New end (blank=keep):", ""); r += 1
        self.u_max = self._add_entry(r, "New max (blank=keep):", ""); r += 1
        self._add_button(r, "Update Schedule", self.on_update); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        # --- Block time slots ---
        self.b_provider = self._add_entry(r, "Block: provider:", ""); r += 1
        self.b_date = self._add_entry(r, "Block date (YYYY-MM-DD):",
                                      datetime.now().strftime("%Y-%m-%d")); r += 1
        self.b_start = self._add_entry(r, "Block start (HH:MM):", "12:00"); r += 1
        self.b_end = self._add_entry(r, "Block end (HH:MM):", "13:00"); r += 1
        self.b_reason = self._add_entry(r, "Block reason:", "Lunch"); r += 1
        self._add_button(r, "Block Time Slots", self.on_block); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        # --- Holiday / vacation ---
        self.h_provider = self._add_entry(r, "Holiday: provider:", ""); r += 1
        self._add_button(r, "View Time Off", self.on_view_timeoff); r += 1

    # -- actions ------------------------------------------------------------
    def on_add(self):
        if not self.a_provider.get().strip():
            messagebox.showerror("Error", "Provider name is required."); return
        if not (_valid_time(self.a_start.get()) and _valid_time(self.a_end.get())):
            messagebox.showerror("Error", "Start/End must be HH:MM."); return
        day_num = dict(self._DAYS)[self.a_day.get()]
        self.run(add_provider_schedule, [
            self.a_provider.get().strip(),
            str(day_num),
            self.a_start.get().strip(),
            self.a_end.get().strip(),
            self.a_max.get().strip(),
            self.a_specialty.get().strip(),
            self.a_location.get().strip(),
        ])

    def on_view(self):
        self.run(view_provider_schedules, [self.v_filter.get().strip()])

    def on_report(self):
        self.run(provider_availability_report, [])

    def on_templates(self):
        # feed "4" (return) so the templates list is shown without side effects
        self.run(schedule_templates, ["4"])

    def on_update(self):
        if not self.u_id.get().strip():
            messagebox.showerror("Error", "Schedule ID is required."); return
        self.run(update_provider_schedule, [
            self.u_id.get().strip(),
            self.u_start.get().strip(),
            self.u_end.get().strip(),
            self.u_max.get().strip(),
        ])

    def on_block(self):
        if not self.b_provider.get().strip():
            messagebox.showerror("Error", "Provider is required."); return
        if not _valid_date(self.b_date.get()):
            messagebox.showerror("Error", "Block date must be YYYY-MM-DD."); return
        if not (_valid_time(self.b_start.get()) and _valid_time(self.b_end.get())):
            messagebox.showerror("Error", "Block start/end must be HH:MM."); return
        self.run(block_time_slots, [
            self.b_provider.get().strip(),
            self.b_date.get().strip(),
            self.b_start.get().strip(),
            self.b_end.get().strip(),
            self.b_reason.get().strip(),
        ])

    def on_view_timeoff(self):
        # manage_provider_time_off: [provider, menu-choice]; "2" = view
        self.run(manage_provider_time_off, [self.h_provider.get().strip(), "2"])


class ProviderDashboardPanel(_ServicePanelBase):
    """Provider Dashboard — read-oriented views rendered from the service data."""

    heading = "Provider Dashboard"
    nav_label = "Provider Dashboard"

    def build_controls(self):
        r = 0
        self._add_button(r, "Today's Schedule", lambda: self.run(todays_schedule, [])); r += 1
        self._add_button(r, "Patient Queue", lambda: self.run(patient_queue, [""])); r += 1
        self._add_button(r, "Critical Alerts", lambda: self.run(critical_alerts_dashboard, [])); r += 1
        self._add_button(r, "Pending Tasks", lambda: self.run(pending_tasks, [])); r += 1
        self._add_button(r, "Recent Lab Results", lambda: self.run(recent_lab_results_dashboard, [])); r += 1
        self._add_button(r, "Vaccination Due List", lambda: self.run(vaccination_due_list, ["n"])); r += 1
        self._add_button(r, "Provider Statistics", lambda: self.run(provider_statistics, [])); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        self.lookup = self._add_entry(r, "Quick lookup:", ""); r += 1
        self._add_button(r, "Quick Patient Lookup", self.on_lookup); r += 1

    def on_lookup(self):
        term = self.lookup.get().strip()
        if not term:
            messagebox.showerror("Error", "Enter a search term."); return
        # feed the term, then "1" to auto-select the first match if several
        self.run(quick_patient_lookup, [term, "1"])


class ScreeningSchedulePanel(_ServicePanelBase):
    """Screening Schedule Management — create, view-due, schedule, record,
    reminders, population reports, guidelines and overdue."""

    heading = "Screening Schedule Management"
    nav_label = "Screening Schedules"

    _TYPES = [
        "Annual Physical Exam", "Blood Pressure Screening", "Cholesterol Screening",
        "Diabetes Screening", "Mental Health Screening", "STI Screening",
        "Cancer Screening", "Vision Screening", "Hearing Screening", "Other",
    ]

    def build_controls(self):
        r = 0
        ttk.Label(self.body, text="Create Screening Schedule",
                  font=("Arial", 10, "bold")).grid(row=r, column=0, columnspan=2, sticky=tk.W, pady=(4, 2)); r += 1
        self.c_student = self._add_entry(r, "Student ID:"); r += 1
        ttk.Label(self.body, text="Screening type:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.c_type = tk.StringVar(value=self._TYPES[0])
        ttk.Combobox(self.body, textvariable=self.c_type, width=20, state="readonly",
                     values=self._TYPES).grid(row=r, column=1, sticky=tk.W, padx=(5, 0)); r += 1
        self.c_custom = self._add_entry(r, "If Other, type:", ""); r += 1
        self.c_due = self._add_entry(r, "Due date (blank=auto):", ""); r += 1
        self.c_provider = self._add_entry(r, "Provider (blank=you):", ""); r += 1
        self._add_button(r, "Create Schedule", self.on_create); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        self._add_button(r, "View Due Screenings", lambda: self.run(view_due_screenings, [])); r += 1
        self._add_button(r, "Overdue Screenings", lambda: self.run(overdue_screenings, ["n"])); r += 1
        self._add_button(r, "Screening Reminders", lambda: self.run(screening_reminders, ["n"])); r += 1
        self._add_button(r, "Population Reports", lambda: self.run(population_screening_reports, [])); r += 1
        self._add_button(r, "Screening Guidelines", lambda: self.run(screening_guidelines, [])); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        ttk.Label(self.body, text="Schedule Screening Appointment",
                  font=("Arial", 10, "bold")).grid(row=r, column=0, columnspan=2, sticky=tk.W, pady=(4, 2)); r += 1
        self.s_id = self._add_entry(r, "Screening ID:"); r += 1
        self.s_date = self._add_entry(r, "Appt date (YYYY-MM-DD):",
                                      datetime.now().strftime("%Y-%m-%d")); r += 1
        self.s_time = self._add_entry(r, "Appt time (HH:MM):", "09:00"); r += 1
        self.s_provider = self._add_entry(r, "Provider (blank=you):", ""); r += 1
        self._add_button(r, "Schedule Appointment", self.on_schedule); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        ttk.Label(self.body, text="Record Screening Results",
                  font=("Arial", 10, "bold")).grid(row=r, column=0, columnspan=2, sticky=tk.W, pady=(4, 2)); r += 1
        self.r_id = self._add_entry(r, "Screening ID:"); r += 1
        self.r_date = self._add_entry(r, "Completed (blank=today):", ""); r += 1
        self.r_results = self._add_entry(r, "Results:", "Normal"); r += 1
        self._add_button(r, "Record Results", self.on_record); r += 1

    # -- actions ------------------------------------------------------------
    def on_create(self):
        if not self.c_student.get().strip():
            messagebox.showerror("Error", "Student ID is required."); return
        due = self.c_due.get().strip()
        if due and not _valid_date(due):
            messagebox.showerror("Error", "Due date must be YYYY-MM-DD."); return
        idx = self._TYPES.index(self.c_type.get()) + 1  # menu is 1-based
        inputs = [self.c_student.get().strip(), str(idx)]
        if self.c_type.get() == "Other":
            inputs.append(self.c_custom.get().strip() or "General Screening")
        inputs += [due, self.c_provider.get().strip()]
        self.run(create_screening_schedule, inputs)

    def on_schedule(self):
        if not self.s_id.get().strip():
            messagebox.showerror("Error", "Screening ID is required."); return
        if not _valid_date(self.s_date.get()) or not _valid_time(self.s_time.get()):
            messagebox.showerror("Error", "Date must be YYYY-MM-DD and time HH:MM."); return
        self.run(schedule_screening_appointment, [
            self.s_id.get().strip(),
            self.s_date.get().strip(),
            self.s_time.get().strip(),
            self.s_provider.get().strip(),
        ])

    def on_record(self):
        if not self.r_id.get().strip():
            messagebox.showerror("Error", "Screening ID is required."); return
        due = self.r_date.get().strip()
        if due and not _valid_date(due):
            messagebox.showerror("Error", "Completed date must be YYYY-MM-DD."); return
        self.run(record_screening_results, [
            self.r_id.get().strip(),
            due,
            self.r_results.get().strip(),
        ])


# Convenience registry for an orchestrator wiring the navigation.
PANELS = {
    "provider_schedules": ProviderSchedulePanel,
    "provider_dashboard": ProviderDashboardPanel,
    "screening_schedules": ScreeningSchedulePanel,
}
