"""Provider, dashboard and screening GUI panels for the Health Portal.

These panels close the gap between the appointment CLI
(``domain/health/appointments/appointment_booking.py``) and the Health Portal
GUI. They do **not** reimplement any persistence: every action drives the exact
same service function the CLI menus call, directly: the form values go in
as the service's ``values`` (``domain/health/prompting.ask``), and what it
prints is shown in the output pane. ``input()`` is never patched. Time off
and schedule templates call the clinic diary (``application/health/diary``).

Each panel is a self-contained ``ttk.Frame`` constructed as
``Panel(parent, auth)`` (matching the embedded ``DentistGUI`` pattern). The
orchestrator is responsible for wiring these into the navigation.
"""

from __future__ import annotations

from education_system.systems.university.infrastructure.i18n import get_text as _t

import contextlib
import io
import tkinter as tk
from datetime import datetime
from tkinter import ttk, scrolledtext
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import messagebox

# --- Service functions (the SAME ones the appointment CLI calls) -------------
from education_system.systems.university.domains.health.domain.health.appointments.appointment_booking import (
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
from education_system.systems.university.domains.health.domain.health.services import (
    block_time_slots,
    patient_queue,
    pending_tasks,
    quick_patient_lookup,
    critical_alerts_dashboard,
)
from education_system.systems.university.domains.health.domain.health.records.clinical.lab_results import (
    recent_lab_results_dashboard,
)
from education_system.systems.university.domains.health.domain.health.records.vaccinations.tracking import (
    vaccination_due_list,
)
from education_system.systems.university.domains.health.domain.health.records.screening.schedules import (
    view_due_screenings,
    overdue_screenings,
)
from education_system.systems.university.domains.health.domain.health.records.screening.results import (
    record_screening_results,
)
from education_system.systems.university.domains.health.domain.health.records.screening.reminders import (
    screening_reminders,
    population_screening_reports,
)
from education_system.systems.university.domains.health.domain.health.records.screening.guidelines import (
    screening_guidelines,
)


def run_service(func, auth, values=None):
    """Call the CLI service ``func`` directly — ``func(auth, values=...)``
    when answers are given, ``func(auth)`` for a read-only view — and return
    everything it printed. Persistence happens inside the service exactly as
    from the CLI."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            if values is None:
                func(auth)
            else:
                func(auth, values=dict(values))
    except Exception as exc:  # surface service errors in the output pane
        buf.write(f"\n[Error running operation: {exc}]\n")
    return buf.getvalue()


def run_diary(func):
    """Run ``func(conn)`` on a clinic-diary connection, commit, and return its text."""
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection()
    try:
        text = func(conn)
        conn.commit()
        return text
    except Exception as exc:
        conn.rollback()
        return f"[Error running operation: {exc}]"
    finally:
        conn.close()


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
        # Provider schedules, dashboards and screening lists name students
        # and their care: the health team only.
        from education_system.systems.university.domains.health.interfaces.gui.health.health_portal import (
            access_ui,
        )
        if not access_ui.is_clinician(auth):
            ttk.Label(self, text=f"{self.heading} is for the health team.").grid(
                row=1, column=0, sticky=tk.W)
            return
        if not access_ui.record_view(self, auth, "provider_" + type(self).__name__):
            return

        self.body = ttk.Frame(self)
        self.body.grid(row=1, column=0, sticky="nsw", padx=(0, 10))

        out_frame = ttk.LabelFrame(self, text=_t('gui.pastoral.health.health_portal.provider_panels.labels.output', default="Output"), padding=5)
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

    def run(self, func, values=None):
        self.show(run_service(func, self.auth, values))

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
        ttk.Label(self.body, text=_t('gui.pastoral.health.health_portal.provider_panels.labels.add_provider_schedule', default="Add Provider Schedule"),
                  font=("Arial", 10, "bold")).grid(row=r, column=0, columnspan=2, sticky=tk.W, pady=(4, 2)); r += 1
        self.a_provider = self._add_entry(r, "Provider name:"); r += 1
        ttk.Label(self.body, text=_t('gui.pastoral.health.health_portal.provider_panels.labels.day_of_week', default="Day of week:")).grid(row=r, column=0, sticky=tk.W, pady=2)
        self.a_day = tk.StringVar(value=_t('gui.pastoral.health.health_portal.provider_panels.values.monday', default="Monday"))
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
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.provider_name_is_required', default="Provider name is required.")); return
        if not (_valid_time(self.a_start.get()) and _valid_time(self.a_end.get())):
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.start_end_must_be_hh_mm', default="Start/End must be HH:MM.")); return
        day_num = dict(self._DAYS)[self.a_day.get()]
        self.run(add_provider_schedule, {
            "provider_name": self.a_provider.get().strip(),
            "day": str(day_num),
            "start_time": self.a_start.get().strip(),
            "end_time": self.a_end.get().strip(),
            "max_appointments": self.a_max.get().strip(),
            "specialty": self.a_specialty.get().strip(),
            "location": self.a_location.get().strip(),
        })

    def on_view(self):
        self.run(view_provider_schedules, {"provider_filter": self.v_filter.get().strip()})

    def on_report(self):
        self.run(provider_availability_report)

    def on_templates(self):
        """List the weekly templates; optionally apply one to a provider."""
        from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import simpledialog
        from education_system.systems.university.domains.health.application.health import diary
        days = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 0: "Sun"}

        def listing(conn):
            lines = ["Schedule templates:"]
            for t in diary.list_templates(conn):
                slots = ", ".join(f"{days[s['day']]} {s['start']}-{s['end']}" for s in t['pattern'])
                lines.append(f"  #{t['id']} {t['name']}  [{slots}; max {t['max_appointments']}/day]")
            return "\n".join(lines)

        text = run_diary(listing)
        self.show(text)
        provider = self.v_filter.get().strip() or self.a_provider.get().strip()
        if provider and messagebox.askyesno("Schedule Templates",
                                            f"Apply a template to {provider}?"):
            tid = simpledialog.askinteger("Schedule Templates", "Template number (#):",
                                          parent=self)
            if tid:
                self.show(text + "\n\n" + run_diary(lambda conn: (
                    f"Applied template #{tid} to {provider}: "
                    f"{diary.apply_template(conn, tid, provider)} weekly clinic(s); the "
                    "previous schedule rows were deactivated.")))

    def on_update(self):
        if not self.u_id.get().strip():
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.schedule_id_is_required', default="Schedule ID is required.")); return
        self.run(update_provider_schedule, {
            "schedule_id": self.u_id.get().strip(),
            "start_time": self.u_start.get().strip(),
            "end_time": self.u_end.get().strip(),
            "max_appointments": self.u_max.get().strip(),
        })

    def on_block(self):
        if not self.b_provider.get().strip():
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.provider_is_required', default="Provider is required.")); return
        if not _valid_date(self.b_date.get()):
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.block_date_must_be_yyyy_mm_dd', default="Block date must be YYYY-MM-DD.")); return
        if not (_valid_time(self.b_start.get()) and _valid_time(self.b_end.get())):
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.block_start_end_must_be_hh_mm', default="Block start/end must be HH:MM.")); return
        self.run(block_time_slots, {
            "provider_name": self.b_provider.get().strip(),
            "block_date": self.b_date.get().strip(),
            "start_time": self.b_start.get().strip(),
            "end_time": self.b_end.get().strip(),
            "reason": self.b_reason.get().strip(),
        })

    def on_view_timeoff(self):
        """Upcoming time off (provider_time_off) for the provider, or everyone."""
        from education_system.systems.university.domains.health.application.health import diary
        provider = self.h_provider.get().strip()

        def listing(conn):
            rows = diary.list_time_off(conn, provider or None)
            lines = [f"Scheduled time off{' for ' + provider if provider else ''}:"]
            if not rows:
                lines.append("  None scheduled.")
            for r in rows:
                span = r['start_date'] if r['start_date'] == r['end_date'] else \
                    f"{r['start_date']} to {r['end_date']}"
                hours = f" {r['start_time']}-{r['end_time']}" if r['start_time'] else ""
                lines.append(f"  [{r['id']}] {r['provider']}: {span}{hours} — "
                             f"{r['reason'] or 'time off'}")
            return "\n".join(lines)

        self.show(run_diary(listing))


class ProviderDashboardPanel(_ServicePanelBase):
    """Provider Dashboard — read-oriented views rendered from the service data."""

    heading = "Provider Dashboard"
    nav_label = "Provider Dashboard"

    def build_controls(self):
        r = 0
        self._add_button(r, "Today's Schedule", lambda: self.run(todays_schedule)); r += 1
        self._add_button(r, "Patient Queue", lambda: self.run(patient_queue, {"action": ""})); r += 1
        self._add_button(r, "Critical Alerts", lambda: self.run(critical_alerts_dashboard)); r += 1
        self._add_button(r, "Pending Tasks", lambda: self.run(pending_tasks)); r += 1
        self._add_button(r, "Recent Lab Results", lambda: self.run(recent_lab_results_dashboard)); r += 1
        self._add_button(r, "Vaccination Due List", lambda: self.run(vaccination_due_list, {"generate_reminders": "n"})); r += 1
        self._add_button(r, "Provider Statistics", lambda: self.run(provider_statistics)); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        self.lookup = self._add_entry(r, "Quick lookup:", ""); r += 1
        self._add_button(r, "Quick Patient Lookup", self.on_lookup); r += 1

    def on_lookup(self):
        term = self.lookup.get().strip()
        if not term:
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.enter_a_search_term', default="Enter a search term.")); return
        # feed the term, then "1" to auto-select the first match if several
        self.run(quick_patient_lookup, {"search_term": term, "choice": "1"})


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
        ttk.Label(self.body, text=_t('gui.pastoral.health.health_portal.provider_panels.labels.create_screening_schedule', default="Create Screening Schedule"),
                  font=("Arial", 10, "bold")).grid(row=r, column=0, columnspan=2, sticky=tk.W, pady=(4, 2)); r += 1
        self.c_student = self._add_entry(r, "Student ID:"); r += 1
        ttk.Label(self.body, text=_t('gui.pastoral.health.health_portal.provider_panels.labels.screening_type', default="Screening type:")).grid(row=r, column=0, sticky=tk.W, pady=2)
        self.c_type = tk.StringVar(value=self._TYPES[0])
        ttk.Combobox(self.body, textvariable=self.c_type, width=20, state="readonly",
                     values=self._TYPES).grid(row=r, column=1, sticky=tk.W, padx=(5, 0)); r += 1
        self.c_custom = self._add_entry(r, "If Other, type:", ""); r += 1
        self.c_due = self._add_entry(r, "Due date (blank=auto):", ""); r += 1
        self.c_provider = self._add_entry(r, "Provider (blank=you):", ""); r += 1
        self._add_button(r, "Create Schedule", self.on_create); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        self._add_button(r, "View Due Screenings", lambda: self.run(view_due_screenings)); r += 1
        self._add_button(r, "Overdue Screenings", lambda: self.run(overdue_screenings, {"send_reminders": "n"})); r += 1
        self._add_button(r, "Screening Reminders", lambda: self.run(screening_reminders, {"send_reminders": "n"})); r += 1
        self._add_button(r, "Population Reports", lambda: self.run(population_screening_reports, {"email_report": "n"})); r += 1
        self._add_button(r, "Screening Guidelines", lambda: self.run(screening_guidelines)); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        ttk.Label(self.body, text=_t('gui.pastoral.health.health_portal.provider_panels.labels.schedule_screening_appointment', default="Schedule Screening Appointment"),
                  font=("Arial", 10, "bold")).grid(row=r, column=0, columnspan=2, sticky=tk.W, pady=(4, 2)); r += 1
        self.s_id = self._add_entry(r, "Screening ID:"); r += 1
        self.s_date = self._add_entry(r, "Appt date (YYYY-MM-DD):",
                                      datetime.now().strftime("%Y-%m-%d")); r += 1
        self.s_time = self._add_entry(r, "Appt time (HH:MM):", "09:00"); r += 1
        self.s_provider = self._add_entry(r, "Provider (blank=you):", ""); r += 1
        self._add_button(r, "Schedule Appointment", self.on_schedule); r += 1

        ttk.Separator(self.body, orient="horizontal").grid(
            row=r, column=0, columnspan=2, sticky="ew", pady=8); r += 1

        ttk.Label(self.body, text=_t('gui.pastoral.health.health_portal.provider_panels.labels.record_screening_results', default="Record Screening Results"),
                  font=("Arial", 10, "bold")).grid(row=r, column=0, columnspan=2, sticky=tk.W, pady=(4, 2)); r += 1
        self.r_id = self._add_entry(r, "Screening ID:"); r += 1
        self.r_date = self._add_entry(r, "Completed (blank=today):", ""); r += 1
        self.r_results = self._add_entry(r, "Results:", "Normal"); r += 1
        self._add_button(r, "Record Results", self.on_record); r += 1

    # -- actions ------------------------------------------------------------
    def on_create(self):
        if not self.c_student.get().strip():
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.student_id_is_required', default="Student ID is required.")); return
        due = self.c_due.get().strip()
        if due and not _valid_date(due):
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.due_date_must_be_yyyy_mm_dd', default="Due date must be YYYY-MM-DD.")); return
        idx = self._TYPES.index(self.c_type.get()) + 1  # menu is 1-based
        values = {"student_id": self.c_student.get().strip(), "screening_type_choice": str(idx),
                  "due_date": due, "provider": self.c_provider.get().strip()}
        if self.c_type.get() == "Other":
            values["screening_type"] = self.c_custom.get().strip() or "General Screening"
        self.run(create_screening_schedule, values)

    def on_schedule(self):
        if not self.s_id.get().strip():
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.screening_id_is_required', default="Screening ID is required.")); return
        if not _valid_date(self.s_date.get()) or not _valid_time(self.s_time.get()):
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.date_must_be_yyyy_mm_dd_and_time_hh_mm', default="Date must be YYYY-MM-DD and time HH:MM.")); return
        self.run(schedule_screening_appointment, {
            "screening_id": self.s_id.get().strip(),
            "appointment_date": self.s_date.get().strip(),
            "appointment_time": self.s_time.get().strip(),
            "provider": self.s_provider.get().strip(),
        })

    def on_record(self):
        if not self.r_id.get().strip():
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.screening_id_is_required', default="Screening ID is required.")); return
        due = self.r_date.get().strip()
        if due and not _valid_date(due):
            messagebox.showerror(_t('gui.pastoral.health.health_portal.provider_panels.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.provider_panels.dialogs.completed_date_must_be_yyyy_mm_dd', default="Completed date must be YYYY-MM-DD.")); return
        self.run(record_screening_results, {
            "screening_id": self.r_id.get().strip(),
            "completed_date": due,
            "results": self.r_results.get().strip(),
        })


# Convenience registry for an orchestrator wiring the navigation.
PANELS = {
    "provider_schedules": ProviderSchedulePanel,
    "provider_dashboard": ProviderDashboardPanel,
    "screening_schedules": ScreeningSchedulePanel,
}
