"""Calendar view tab for the Exam Scheduling System."""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

# i18n import
try:
    from education_system.systems.university.infrastructure.i18n import get_text as _
except ImportError:
    def _(key, **kwargs):
        return key


class CalendarTabMixin:
    """Mixin providing the calendar view tab and its operations."""

    def create_calendar_tab(self):
        """Create a calendar view tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("exam_scheduler.tabs.calendar_view"))

        # Week navigation
        nav_frame = ttk.Frame(tab)
        nav_frame.pack(fill=tk.X, pady=(0, 10))

        self.current_week_start = datetime.now() - timedelta(days=datetime.now().weekday())

        ttk.Button(nav_frame, text=_("exam_scheduler.buttons.previous_week"), command=self.prev_week).pack(side=tk.LEFT)
        self.week_label = ttk.Label(nav_frame, text="", font=('Helvetica', 12, 'bold'))
        self.week_label.pack(side=tk.LEFT, expand=True)
        ttk.Button(nav_frame, text=_("exam_scheduler.buttons.next_week"), command=self.next_week).pack(side=tk.RIGHT)

        # Calendar grid
        self.calendar_frame = ttk.Frame(tab)
        self.calendar_frame.pack(fill=tk.BOTH, expand=True)

        self.root.after_idle(self.update_calendar)

    def update_calendar(self):
        """Update the calendar view."""
        # Clear existing
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        # Update label
        week_end = self.current_week_start + timedelta(days=6)
        self.week_label.config(text=f"{self.current_week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}")

        # Create day columns
        days = [
            _("exam_scheduler.days.monday"),
            _("exam_scheduler.days.tuesday"),
            _("exam_scheduler.days.wednesday"),
            _("exam_scheduler.days.thursday"),
            _("exam_scheduler.days.friday"),
            _("exam_scheduler.days.saturday"),
            _("exam_scheduler.days.sunday")
        ]

        for col, day in enumerate(days):
            current_date = self.current_week_start + timedelta(days=col)
            date_str = current_date.strftime('%Y-%m-%d')

            # Day header
            day_frame = ttk.LabelFrame(self.calendar_frame, text=f"{day}\n{current_date.strftime('%m/%d')}")
            day_frame.grid(row=0, column=col, sticky='nsew', padx=2, pady=2)

            # Get exams for this day
            day_exams = [e for e in self.data_manager.exams if e.date == date_str]
            day_exams.sort(key=lambda x: x.start_time)

            if day_exams:
                for exam in day_exams:
                    exam_frame = ttk.Frame(day_frame, relief='raised', borderwidth=1)
                    exam_frame.pack(fill=tk.X, padx=2, pady=2)

                    ttk.Label(exam_frame, text=exam.module_code, font=('Helvetica', 9, 'bold')).pack(anchor='w')
                    ttk.Label(exam_frame, text=f"{exam.start_time}-{exam.end_time}", font=('Helvetica', 8)).pack(anchor='w')
                    ttk.Label(exam_frame, text=exam.room, font=('Helvetica', 8)).pack(anchor='w')
            else:
                ttk.Label(day_frame, text=_("exam_scheduler.labels.no_exams"), foreground='gray').pack(pady=20)

            self.calendar_frame.columnconfigure(col, weight=1)

        self.calendar_frame.rowconfigure(0, weight=1)

    def prev_week(self):
        self.current_week_start -= timedelta(days=7)
        self.update_calendar()

    def next_week(self):
        self.current_week_start += timedelta(days=7)
        self.update_calendar()
