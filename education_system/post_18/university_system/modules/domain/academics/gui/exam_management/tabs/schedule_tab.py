"""Schedule overview tab for the Exam Scheduling System."""

import tkinter as tk
from tkinter import ttk

# i18n import
try:
    from education_system.post_18.university_system.core.i18n import get_text as _
except ImportError:
    def _(key, **kwargs):
        return key


class ScheduleTabMixin:
    """Mixin providing the schedule overview tab and its operations."""

    def create_schedule_tab(self):
        """Create the main schedule overview tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("exam_scheduler.tabs.schedule_overview"))

        # Top controls
        controls_frame = ttk.Frame(tab)
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        # Filter by date
        ttk.Label(controls_frame, text=_("exam_scheduler.labels.filter_by_date")).pack(side=tk.LEFT, padx=(0, 5))
        self.filter_date_var = tk.StringVar()
        date_entry = ttk.Entry(controls_frame, textvariable=self.filter_date_var, width=12)
        date_entry.pack(side=tk.LEFT, padx=(0, 10))
        date_entry.insert(0, _("exam_scheduler.placeholders.date_format"))
        date_entry.bind('<FocusIn>', lambda e: date_entry.delete(0, tk.END) if date_entry.get() == _("exam_scheduler.placeholders.date_format") else None)

        ttk.Button(controls_frame, text=_("exam_scheduler.buttons.filter"), command=self.filter_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_("exam_scheduler.buttons.clear_filter"), command=self.clear_filter).pack(side=tk.LEFT, padx=5)

        # Advanced filters
        ttk.Button(controls_frame, text="Advanced Filters", command=self.show_advanced_filters).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Export Selected", command=self.export_selected_exams).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Find Conflicts", command=self.find_all_conflicts).pack(side=tk.LEFT, padx=5)

        ttk.Button(controls_frame, text=_("exam_scheduler.buttons.refresh"), command=self.refresh_exam_list).pack(side=tk.RIGHT)

        # Schedule treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('id', 'module', 'name', 'date', 'time', 'room', 'instructor', 'students')
        self.schedule_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')

        # Configure columns
        self.schedule_tree.heading('id', text=_("exam_scheduler.columns.id"))
        self.schedule_tree.heading('module', text=_("exam_scheduler.columns.module_code"))
        self.schedule_tree.heading('name', text=_("exam_scheduler.columns.module_name"))
        self.schedule_tree.heading('date', text=_("exam_scheduler.columns.date"))
        self.schedule_tree.heading('time', text=_("exam_scheduler.columns.time"))
        self.schedule_tree.heading('room', text=_("exam_scheduler.columns.room"))
        self.schedule_tree.heading('instructor', text=_("exam_scheduler.columns.instructor"))
        self.schedule_tree.heading('students', text=_("exam_scheduler.columns.students"))

        self.schedule_tree.column('id', width=50)
        self.schedule_tree.column('module', width=100)
        self.schedule_tree.column('name', width=200)
        self.schedule_tree.column('date', width=100)
        self.schedule_tree.column('time', width=120)
        self.schedule_tree.column('room', width=100)
        self.schedule_tree.column('instructor', width=150)
        self.schedule_tree.column('students', width=80)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.schedule_tree.yview)
        self.schedule_tree.configure(yscrollcommand=scrollbar.set)

        self.schedule_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Statistics frame
        stats_frame = ttk.LabelFrame(tab, text=_("exam_scheduler.frames.statistics"), padding="10")
        stats_frame.pack(fill=tk.X, pady=(10, 0))

        self.stats_label = ttk.Label(stats_frame, text="")
        self.stats_label.pack()

    def refresh_exam_list(self):
        """Refresh the exam list in all views."""
        # Tabs build lazily; only clear/populate trees that already exist.
        trees = [t for t in (getattr(self, "schedule_tree", None),
                             getattr(self, "exam_tree", None)) if t is not None]
        for tree in trees:
            for item in tree.get_children():
                tree.delete(item)

        # Sort exams by date and time
        sorted_exams = sorted(self.data_manager.exams, key=lambda x: (x.date, x.start_time))

        if getattr(self, "schedule_tree", None) is not None:
            for exam in sorted_exams:
                time_str = f"{exam.start_time} - {exam.end_time}"
                self.schedule_tree.insert('', tk.END, values=(
                    exam.id, exam.module_code, exam.module_name, exam.date,
                    time_str, exam.room, exam.instructor_name, exam.students_enrolled
                ))

        if getattr(self, "exam_tree", None) is not None:
            for exam in sorted_exams:
                self.exam_tree.insert('', tk.END, values=(
                    exam.id, exam.module_code, exam.module_name, exam.date, exam.room
                ))

        if hasattr(self, "stats_label"):
            self.update_statistics()

        if hasattr(self, "calendar_frame"):
            self.update_calendar()

    def update_statistics(self):
        """Update the statistics display with enhanced information."""
        total_exams = len(self.data_manager.exams)
        total_students = sum(e.students_enrolled for e in self.data_manager.exams)

        # Count unique dates
        unique_dates = len(set(e.date for e in self.data_manager.exams))

        # Count rooms in use
        rooms_used = len(set(e.room for e in self.data_manager.exams))

        # Count unique instructors
        instructors_used = len(set(e.instructor_id for e in self.data_manager.exams if e.instructor_id))

        # Calculate average students per exam
        avg_students = total_students / total_exams if total_exams > 0 else 0

        # Find busiest day
        busiest_day = ""
        if self.data_manager.exams:
            date_counts = {}
            for exam in self.data_manager.exams:
                date_counts[exam.date] = date_counts.get(exam.date, 0) + 1
            busiest_date = max(date_counts, key=date_counts.get)
            busiest_count = date_counts[busiest_date]
            busiest_day = f"  |  Busiest Day: {busiest_date} ({busiest_count} exams)"

        stats_text = (f"{_('exam_scheduler.stats.total_exams')}: {total_exams}  |  "
                     f"{_('exam_scheduler.stats.total_students')}: {total_students} "
                     f"(Avg: {avg_students:.1f})  |  "
                     f"{_('exam_scheduler.stats.exam_days')}: {unique_dates}  |  "
                     f"Rooms: {rooms_used}  |  "
                     f"Instructors: {instructors_used}"
                     f"{busiest_day}")
        self.stats_label.config(text=stats_text)

    def filter_schedule(self):
        """Filter schedule by date."""
        filter_date = self.filter_date_var.get().strip()
        if not filter_date or filter_date == "YYYY-MM-DD":
            return

        for item in self.schedule_tree.get_children():
            self.schedule_tree.delete(item)

        filtered = [e for e in self.data_manager.exams if e.date == filter_date]
        filtered.sort(key=lambda x: x.start_time)

        for exam in filtered:
            time_str = f"{exam.start_time} - {exam.end_time}"
            self.schedule_tree.insert('', tk.END, values=(
                exam.id, exam.module_code, exam.module_name, exam.date,
                time_str, exam.room, exam.instructor_name, exam.students_enrolled
            ))

    def clear_filter(self):
        """Clear the date filter."""
        self.filter_date_var.set("")
        self.refresh_exam_list()
