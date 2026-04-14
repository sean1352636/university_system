"""
Deadlines mixin - upcoming scholarship deadline tracking.
"""

from education_system.university_system.modules.domain.finance.gui.financial_aid.common_imports import (
    tk,
    ttk,
    logging,
    datetime,
    clear_frame,
    create_data_table,
    format_date,
    show_error,
)
from education_system.university_system.modules.shared.utils.i18n import get_text

logger = logging.getLogger(__name__)


class DeadlinesMixin:
    """Deadline tracking functionality"""

    def show_deadlines(self):
        """Display upcoming deadlines calendar"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.deadlines.title", "Upcoming Deadlines"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Control frame
        control_frame = ttk.Frame(self.parent_frame)
        control_frame.pack(pady=10)

        ttk.Label(control_frame, text=get_text("financial_aid.student_portal.deadlines.show_within", "Show deadlines within:")).pack(side='left', padx=5)
        self.deadline_days_var = tk.StringVar(value="14")
        ttk.Entry(control_frame, textvariable=self.deadline_days_var, width=10).pack(side='left', padx=5)
        ttk.Label(control_frame, text=get_text("financial_aid.student_portal.deadlines.days_unit", "days")).pack(side='left', padx=5)

        ttk.Button(control_frame, text=get_text("financial_aid.student_portal.buttons.refresh", "Refresh"), command=self._load_deadlines).pack(side='left', padx=10)

        # Deadlines table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        col_scholarship = get_text("financial_aid.student_portal.deadlines.columns.scholarship", "Scholarship")
        col_deadline = get_text("financial_aid.student_portal.deadlines.columns.deadline", "Deadline")
        col_days_left = get_text("financial_aid.student_portal.deadlines.columns.days_left", "Days Left")
        col_status = get_text("financial_aid.student_portal.deadlines.columns.status", "Status")
        col_progress = get_text("financial_aid.student_portal.deadlines.columns.progress", "Progress")
        col_urgency = get_text("financial_aid.student_portal.deadlines.columns.urgency", "Urgency")
        columns = [col_scholarship, col_deadline, col_days_left, col_status, col_progress, col_urgency]
        self.deadline_tree = create_data_table(table_frame, columns, {
            col_scholarship: 300, col_deadline: 120, col_days_left: 100,
            col_status: 120, col_progress: 150, col_urgency: 100
        })

        # Load deadlines
        self._load_deadlines()

    def _load_deadlines(self):
        """Load and display upcoming deadlines"""
        try:
            # Clear tree
            for item in self.deadline_tree.get_children():
                self.deadline_tree.delete(item)

            days = int(self.deadline_days_var.get().strip())

            from education_system.university_system.modules.domain.finance.scholarship_finder.services.scholarship_service import ApplicationManager

            deadlines = ApplicationManager.get_upcoming_deadlines(self.student_id, days)

            for app in deadlines:
                deadline = datetime.strptime(app['deadline_date'], '%Y-%m-%d')
                days_left = (deadline - datetime.now()).days

                if days_left <= 3:
                    urgency = get_text("financial_aid.student_portal.deadlines.urgency.urgent", "URGENT!")
                elif days_left <= 7:
                    urgency = get_text("financial_aid.student_portal.deadlines.urgency.soon", "Soon")
                else:
                    urgency = get_text("financial_aid.student_portal.deadlines.urgency.upcoming", "Upcoming")

                progress = app.get('application_progress', 0)
                progress_bar = "\u2588" * int(progress / 10) + "\u2591" * (10 - int(progress / 10))

                self.deadline_tree.insert('', 'end', values=(
                    app['scholarship_name'][:45],
                    app['deadline_date'],
                    get_text("financial_aid.student_portal.deadlines.days_left", "{count} days", count=days_left),
                    app['status'].upper(),
                    f"{progress_bar} {progress:.0f}%",
                    urgency
                ))

            # Color code by urgency
            urgent_text = get_text("financial_aid.student_portal.deadlines.urgency.urgent", "URGENT!")
            soon_text = get_text("financial_aid.student_portal.deadlines.urgency.soon", "Soon")
            for item in self.deadline_tree.get_children():
                values = self.deadline_tree.item(item)['values']
                urgency = values[5]
                if urgency == urgent_text:
                    self.deadline_tree.item(item, tags=('urgent',))
                elif urgency == soon_text:
                    self.deadline_tree.item(item, tags=('soon',))

            self.deadline_tree.tag_configure('urgent', background='#f8d7da', foreground='darkred')
            self.deadline_tree.tag_configure('soon', background='#fff3cd')

        except Exception as e:
            logger.error(f"Error loading deadlines: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"), get_text("financial_aid.student_portal.errors.failed_load_deadlines", "Failed to load deadlines: {error}", error=str(e)))
