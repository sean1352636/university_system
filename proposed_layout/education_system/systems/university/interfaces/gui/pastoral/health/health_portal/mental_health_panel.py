"""
Mental Health & Wellness panel for the Health Portal GUI.

Self-contained Tkinter panel that mirrors the "Mental Health & Wellness"
section of the health portal CLI
(``domain/health/portal/health_portal_core.py`` -> WellnessCLI). It wires
directly to the SAME persistence layer the CLI uses:
``student_affairs.wellness.services.wellness_service.WellnessService``.

Wire-up (done by the orchestrator / nav owner, NOT this module):

    from ...mental_health_panel import MentalHealthWellnessPanel
    MentalHealthWellnessPanel(self.content_frame, self.auth)

Suggested nav label: "Mental Health & Wellness"

The panel exposes the seven CLI actions:
    * Schedule Counseling Appointment   -> WellnessService.schedule_counseling / get_counseling_appointments
    * Wellness Check-in                 -> WellnessService.create_checkin / get_recent_checkins
    * Peer Support Matching             -> static informational view
    * Mindfulness & Meditation          -> static informational view
    * Crisis Hotline Information         -> WellnessService.get_crisis_resources
    * Counselor Profiles                -> read/display view
    * Track Wellness Progress           -> WellnessService.get_comprehensive_wellness_report /
                                           analyze_wellness_patterns
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from education_system.systems.university.domain.pastoral.wellbeing.wellness.services.wellness_service import (
    WellnessService,
)


class MentalHealthWellnessPanel:
    """Mental Health & Wellness panel embedded into a parent Tk container.

    Args:
        parent: a Tk container (Frame/LabelFrame) to build into.
        auth:   the shared auth object (optional). When present and the current
                user is a student, the student id is pre-filled and locked.
    """

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.service = WellnessService()

        # Resolve a default student id from the logged-in user, if any.
        self._default_student_id = ""
        self._is_student = False
        try:
            current = getattr(auth, "current_user", None)
            if current:
                self._is_student = current.get("role") == "student"
                self._default_student_id = str(current.get("id") or "")
        except Exception:
            pass

        self._build()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def _build(self):
        title = ttk.Label(
            self.parent, text="Mental Health & Wellness", style="Title.TLabel"
        )
        title.grid(row=0, column=0, pady=10, sticky=tk.W)

        notebook = ttk.Notebook(self.parent)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(1, weight=1)

        counseling_tab = ttk.Frame(notebook)
        notebook.add(counseling_tab, text="Schedule Counseling")
        self._build_counseling_tab(counseling_tab)

        checkin_tab = ttk.Frame(notebook)
        notebook.add(checkin_tab, text="Wellness Check-in")
        self._build_checkin_tab(checkin_tab)

        progress_tab = ttk.Frame(notebook)
        notebook.add(progress_tab, text="Wellness Progress")
        self._build_progress_tab(progress_tab)

        peer_tab = ttk.Frame(notebook)
        notebook.add(peer_tab, text="Peer Support")
        self._build_peer_support_tab(peer_tab)

        mindfulness_tab = ttk.Frame(notebook)
        notebook.add(mindfulness_tab, text="Mindfulness")
        self._build_mindfulness_tab(mindfulness_tab)

        counselor_tab = ttk.Frame(notebook)
        notebook.add(counselor_tab, text="Counselor Profiles")
        self._build_counselor_profiles_tab(counselor_tab)

        crisis_tab = ttk.Frame(notebook)
        notebook.add(crisis_tab, text="Crisis Hotline")
        self._build_crisis_tab(crisis_tab)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _student_id_row(self, parent, var, row=0):
        ttk.Label(parent, text="Student ID:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        entry = ttk.Entry(parent, textvariable=var, width=20)
        entry.grid(row=row, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        if self._default_student_id:
            var.set(self._default_student_id)
        if self._is_student:
            entry.config(state="readonly")
        return entry

    @staticmethod
    def _readonly_text(parent, height=18, width=70):
        txt = tk.Text(parent, height=height, width=width, wrap="word", font=("Courier", 10))
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        return txt

    @staticmethod
    def _set_text(widget, content):
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)
        widget.config(state="disabled")

    # ------------------------------------------------------------------ #
    # Tab: Schedule Counseling
    # ------------------------------------------------------------------ #
    def _build_counseling_tab(self, parent):
        form = ttk.LabelFrame(parent, text="Book a Counseling Appointment", padding=10)
        form.pack(fill="x", padx=10, pady=10)

        self.coun_student_id = tk.StringVar()
        self._student_id_row(form, self.coun_student_id, row=0)

        ttk.Label(form, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.coun_date = tk.StringVar(
            value=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        )
        ttk.Entry(form, textvariable=self.coun_date, width=20).grid(
            row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0)
        )

        ttk.Label(form, text="Time (HH:MM):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.coun_time = tk.StringVar(value="10:00")
        ttk.Entry(form, textvariable=self.coun_time, width=20).grid(
            row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0)
        )

        ttk.Label(form, text="Type:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.coun_type = tk.StringVar(value="Individual Counseling")
        ttk.Combobox(
            form,
            textvariable=self.coun_type,
            values=[
                "Individual Counseling",
                "Group Therapy",
                "Crisis Intervention",
                "Academic Stress",
                "Anxiety / Depression",
                "Follow-up",
            ],
            width=28,
        ).grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(form, text="Notes:").grid(row=4, column=0, sticky=(tk.W, tk.N), pady=5)
        self.coun_notes = tk.Text(form, width=40, height=3)
        self.coun_notes.grid(row=4, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Button(form, text="Schedule", command=self._save_counseling).grid(
            row=5, column=0, columnspan=2, pady=10
        )

        list_frame = ttk.LabelFrame(parent, text="My Counseling Appointments", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("ID", "Date", "Time", "Type", "Counselor", "Status")
        self.coun_tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", height=8
        )
        for col in columns:
            self.coun_tree.heading(col, text=col)
            self.coun_tree.column(col, width=60 if col == "ID" else 120)
        self.coun_tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.coun_tree.yview
        )
        scroll.pack(side="right", fill="y")
        self.coun_tree.configure(yscrollcommand=scroll.set)

        ttk.Button(parent, text="Refresh Appointments", command=self._load_counseling).pack(
            pady=(0, 10)
        )

        self._load_counseling()

    def _save_counseling(self):
        student_id = self.coun_student_id.get().strip()
        date_str = self.coun_date.get().strip()
        time_str = self.coun_time.get().strip()
        if not student_id or not date_str or not time_str:
            messagebox.showerror("Error", "Student ID, date and time are required.")
            return
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            datetime.strptime(time_str, "%H:%M")
        except ValueError:
            messagebox.showerror("Error", "Invalid date or time format.")
            return
        try:
            appt_id = self.service.schedule_counseling(
                student_id=student_id,
                appointment_date=date_str,
                appointment_time=time_str,
                appointment_type=self.coun_type.get().strip() or "Individual Counseling",
                notes=self.coun_notes.get("1.0", tk.END).strip() or None,
            )
            messagebox.showinfo(
                "Success", f"Counseling appointment scheduled (ID: {appt_id})."
            )
            self.coun_notes.delete("1.0", tk.END)
            self._load_counseling()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to schedule: {e}")

    def _load_counseling(self):
        for item in self.coun_tree.get_children():
            self.coun_tree.delete(item)
        student_id = self.coun_student_id.get().strip()
        if not student_id:
            return
        try:
            for appt in self.service.get_counseling_appointments(student_id):
                self.coun_tree.insert(
                    "",
                    tk.END,
                    values=(
                        appt.get("appointment_id"),
                        appt.get("appointment_date"),
                        appt.get("appointment_time"),
                        appt.get("appointment_type"),
                        appt.get("counselor_name") or "-",
                        appt.get("status"),
                    ),
                )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load appointments: {e}")

    # ------------------------------------------------------------------ #
    # Tab: Wellness Check-in
    # ------------------------------------------------------------------ #
    def _build_checkin_tab(self, parent):
        form = ttk.LabelFrame(parent, text="Daily Wellness Check-in (1-10)", padding=10)
        form.pack(fill="x", padx=10, pady=10)

        self.ci_student_id = tk.StringVar()
        self._student_id_row(form, self.ci_student_id, row=0)

        self.ci_mood = tk.IntVar(value=5)
        self.ci_stress = tk.IntVar(value=5)
        self.ci_sleep = tk.IntVar(value=5)
        self.ci_energy = tk.IntVar(value=5)
        self.ci_anxiety = tk.IntVar(value=5)

        sliders = [
            ("Overall Mood:", self.ci_mood),
            ("Stress Level:", self.ci_stress),
            ("Sleep Quality:", self.ci_sleep),
            ("Energy Level:", self.ci_energy),
            ("Anxiety Level:", self.ci_anxiety),
        ]
        for i, (label, var) in enumerate(sliders, start=1):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky=tk.W, pady=4)
            ttk.Scale(
                form, from_=1, to=10, orient=tk.HORIZONTAL, variable=var, length=200,
                command=lambda v, vr=var: vr.set(round(float(v))),
            ).grid(row=i, column=1, sticky=tk.W, pady=4, padx=(5, 0))
            ttk.Label(form, textvariable=var, width=3).grid(row=i, column=2, padx=5)

        ttk.Label(form, text="Notes:").grid(row=6, column=0, sticky=(tk.W, tk.N), pady=5)
        self.ci_notes = tk.Text(form, width=40, height=3)
        self.ci_notes.grid(row=6, column=1, columnspan=2, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Button(form, text="Submit Check-in", command=self._save_checkin).grid(
            row=7, column=0, columnspan=3, pady=10
        )

        history_frame = ttk.LabelFrame(parent, text="Recent Check-ins", padding=10)
        history_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.ci_history = self._readonly_text(history_frame, height=10)

        ttk.Button(parent, text="Refresh History", command=self._load_checkins).pack(
            pady=(0, 10)
        )
        self._load_checkins()

    def _save_checkin(self):
        student_id = self.ci_student_id.get().strip()
        if not student_id:
            messagebox.showerror("Error", "Student ID is required.")
            return
        try:
            checkin_id = self.service.create_checkin(
                student_id=student_id,
                overall_mood=int(self.ci_mood.get()),
                stress_level=int(self.ci_stress.get()),
                sleep_quality=int(self.ci_sleep.get()),
                energy_level=int(self.ci_energy.get()),
                anxiety_level=int(self.ci_anxiety.get()),
                notes=self.ci_notes.get("1.0", tk.END).strip() or None,
            )
            messagebox.showinfo(
                "Success", f"Check-in recorded (ID: {checkin_id}). +10 wellness points."
            )
            self.ci_notes.delete("1.0", tk.END)
            self._load_checkins()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to record check-in: {e}")

    def _load_checkins(self):
        student_id = self.ci_student_id.get().strip()
        if not student_id:
            self._set_text(self.ci_history, "Enter a Student ID to view check-ins.")
            return
        try:
            checkins = self.service.get_recent_checkins(student_id, days=30)
            if not checkins:
                self._set_text(self.ci_history, "No check-ins in the last 30 days.")
                return
            lines = []
            for c in checkins:
                lines.append(
                    f"{c['checkin_date']}  mood={c['overall_mood']} stress={c['stress_level']} "
                    f"sleep={c['sleep_quality']} energy={c['energy_level']} anxiety={c['anxiety_level']}"
                    + (f"  | {c['notes']}" if c.get("notes") else "")
                )
            self._set_text(self.ci_history, "\n".join(lines))
        except Exception as e:
            self._set_text(self.ci_history, f"Failed to load check-ins: {e}")

    # ------------------------------------------------------------------ #
    # Tab: Wellness Progress
    # ------------------------------------------------------------------ #
    def _build_progress_tab(self, parent):
        top = ttk.Frame(parent, padding=10)
        top.pack(fill="x")
        self.pr_student_id = tk.StringVar()
        self._student_id_row(top, self.pr_student_id, row=0)
        ttk.Button(top, text="Track Progress", command=self._load_progress).grid(
            row=0, column=2, padx=10
        )

        self.pr_text = self._readonly_text(parent, height=22)
        self._load_progress()

    def _load_progress(self):
        student_id = self.pr_student_id.get().strip()
        if not student_id:
            self._set_text(self.pr_text, "Enter a Student ID to view wellness progress.")
            return
        try:
            report = self.service.get_comprehensive_wellness_report(student_id, days=30)
            patterns = report.get("wellness_patterns", {})
            sleep = report.get("sleep_analytics", {})

            lines = ["WELLNESS PROGRESS (last 30 days)", "=" * 50, ""]
            if "averages" in patterns:
                a = patterns["averages"]
                lines.append(f"Total check-ins : {patterns.get('total_checkins', 0)}")
                lines.append(f"Avg mood        : {a['mood']}/10")
                lines.append(f"Avg stress      : {a['stress']}/10")
                lines.append(f"Avg sleep       : {a['sleep_quality']}/10")
                lines.append(f"Avg energy      : {a['energy']}/10")
                lines.append(f"Avg anxiety     : {a['anxiety']}/10")
                if patterns.get("concerns"):
                    lines.append("")
                    lines.append("Concerns:")
                    lines.extend(f"  - {c}" for c in patterns["concerns"])
                lines.append("")
                lines.append(f"Recommendation  : {patterns.get('recommendation', '')}")
            else:
                lines.append(patterns.get("message", "No check-in data available."))

            lines.append("")
            lines.append("SLEEP")
            lines.append("-" * 50)
            if "average_hours" in sleep:
                lines.append(f"Nights tracked  : {sleep.get('nights_tracked', 0)}")
                lines.append(f"Avg hours slept : {sleep['average_hours']}")
                lines.append(f"Avg quality     : {sleep.get('average_quality')}")
            else:
                lines.append(sleep.get("message", "No sleep data available."))

            lines.append("")
            lines.append(f"Total wellness points : {report.get('total_wellness_points', 0)}")
            lines.append(f"Active goals          : {report.get('active_goals_count', 0)}")
            for g in report.get("active_goals", []):
                lines.append(
                    f"  - [{g.get('goal_type')}] {g.get('goal_description')} "
                    f"({g.get('current_value')}/{g.get('target_value')})"
                )

            self._set_text(self.pr_text, "\n".join(lines))
        except Exception as e:
            self._set_text(self.pr_text, f"Failed to load progress: {e}")

    # ------------------------------------------------------------------ #
    # Tab: Crisis Hotline (from service crisis_resources)
    # ------------------------------------------------------------------ #
    def _build_crisis_tab(self, parent):
        text = self._readonly_text(parent, height=22)
        lines = ["CRISIS HOTLINE & EMERGENCY RESOURCES", "=" * 50, ""]
        try:
            resources = self.service.get_crisis_resources()
            if resources:
                for r in resources:
                    lines.append(f"{r['resource_name']}  ({r['resource_type']})")
                    lines.append(f"  Contact     : {r['contact_info']}")
                    lines.append(f"  Availability: {r.get('availability', '24/7')}")
                    if r.get("description"):
                        lines.append(f"  {r['description']}")
                    lines.append("")
            else:
                lines.append("No crisis resources configured.")
        except Exception as e:
            lines.append(f"Failed to load crisis resources: {e}")
        lines.append("")
        lines.append("If you or someone you know is in immediate danger, call 911.")
        self._set_text(text, "\n".join(lines))

    # ------------------------------------------------------------------ #
    # Tab: Counselor Profiles (read/display view)
    # ------------------------------------------------------------------ #
    def _build_counselor_profiles_tab(self, parent):
        text = self._readonly_text(parent, height=22)
        content = (
            "CAMPUS COUNSELOR PROFILES\n"
            + "=" * 50
            + "\n\n"
            "Dr. Amelia Hart, PhD  -  Clinical Psychologist\n"
            "  Focus : Anxiety, depression, academic stress\n"
            "  Hours : Mon-Fri, 9:00-16:00\n\n"
            "Marcus Lee, LCSW  -  Licensed Clinical Social Worker\n"
            "  Focus : Group therapy, relationship & family support\n"
            "  Hours : Tue-Thu, 10:00-18:00\n\n"
            "Priya Nair, LPC  -  Licensed Professional Counselor\n"
            "  Focus : Crisis intervention, trauma-informed care\n"
            "  Hours : Mon-Fri, 8:00-15:00\n\n"
            "To book time with a counselor, use the 'Schedule Counseling' tab.\n"
        )
        self._set_text(text, content)

    # ------------------------------------------------------------------ #
    # Tab: Peer Support Matching (informational view)
    # ------------------------------------------------------------------ #
    def _build_peer_support_tab(self, parent):
        text = self._readonly_text(parent, height=22)
        content = (
            "PEER SUPPORT MATCHING\n"
            + "=" * 50
            + "\n\n"
            "Peer support connects you with a trained student volunteer who has\n"
            "shared similar experiences.\n\n"
            "Available peer groups:\n"
            "  - First-Year Transition Circle\n"
            "  - International Students Network\n"
            "  - Stress & Burnout Support\n"
            "  - LGBTQ+ Peer Alliance\n"
            "  - Grief & Loss Companions\n\n"
            "To be matched, complete a Wellness Check-in so we can understand your\n"
            "current needs, then contact the Campus Counseling Center (see the\n"
            "Crisis Hotline tab) to request a peer match.\n"
        )
        self._set_text(text, content)

    # ------------------------------------------------------------------ #
    # Tab: Mindfulness & Meditation (informational view)
    # ------------------------------------------------------------------ #
    def _build_mindfulness_tab(self, parent):
        text = self._readonly_text(parent, height=22)
        content = (
            "MINDFULNESS & MEDITATION RESOURCES\n"
            + "=" * 50
            + "\n\n"
            "Guided practices:\n"
            "  - 5-minute breathing reset (box breathing 4-4-4-4)\n"
            "  - Body scan relaxation (10 min)\n"
            "  - Loving-kindness meditation (15 min)\n"
            "  - Grounding: 5-4-3-2-1 sensory exercise\n\n"
            "Daily habits that help:\n"
            "  - A consistent sleep schedule (log it in Wellness Check-in)\n"
            "  - Short walks between study sessions\n"
            "  - Screen-free wind-down 30 minutes before bed\n\n"
            "Campus mindfulness sessions run weekdays at 12:00 in the Wellness Suite.\n"
        )
        self._set_text(text, content)
