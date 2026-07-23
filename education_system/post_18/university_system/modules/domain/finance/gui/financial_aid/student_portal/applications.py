"""
Applications mixin - tracking scholarship and financial aid applications.
"""

from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.common_imports import (
    ttk,
    logging,
    get_connection,
    clear_frame,
    create_data_table,
    format_currency,
    format_date,
    get_status_color,
)
from education_system.post_18.university_system.core.i18n import get_text

logger = logging.getLogger(__name__)


class ApplicationsMixin:
    """Application tracking functionality"""

    def show_my_applications(self):
        """Show student's applications"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.my_applications_title", "My Applications"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Tabs for different application types
        notebook = ttk.Notebook(self.parent_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Scholarship applications tab
        scholarship_frame = ttk.Frame(notebook)
        notebook.add(scholarship_frame, text=get_text("financial_aid.student_portal.tabs.scholarship_applications", "Scholarship Applications"))
        self._show_scholarship_applications(scholarship_frame)

        # Financial aid applications tab
        aid_frame = ttk.Frame(notebook)
        notebook.add(aid_frame, text=get_text("financial_aid.student_portal.tabs.financial_aid_applications", "Financial Aid Applications"))
        self._show_aid_applications(aid_frame)

    def _show_scholarship_applications(self, parent):
        """Show scholarship applications in tab"""
        try:
            with get_connection() as conn:
                applications = conn.execute("""
                    SELECT sa.*, s.scholarship_name, s.amount
                    FROM scholarship_applications sa
                    JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                    WHERE sa.student_id = ?
                    ORDER BY sa.application_date DESC
                """, (self.student_id,)).fetchall()

                if applications:
                    columns = [get_text("financial_aid.student_portal.columns.app_id", "App ID"),
                               get_text("financial_aid.student_portal.columns.scholarship", "Scholarship"),
                               get_text("financial_aid.student_portal.columns.amount", "Amount"),
                               get_text("financial_aid.student_portal.columns.submitted", "Submitted"),
                               get_text("financial_aid.student_portal.columns.status", "Status")]
                    tree = create_data_table(parent, columns, {
                        get_text("financial_aid.student_portal.columns.app_id", "App ID"): 80,
                        get_text("financial_aid.student_portal.columns.scholarship", "Scholarship"): 250,
                        get_text("financial_aid.student_portal.columns.amount", "Amount"): 100,
                        get_text("financial_aid.student_portal.columns.submitted", "Submitted"): 120,
                        get_text("financial_aid.student_portal.columns.status", "Status"): 100
                    })

                    for app in applications:
                        tree.insert('', 'end', values=(
                            app['application_id'],
                            app['scholarship_name'],
                            format_currency(app['amount']),
                            format_date(app['application_date']),
                            app['status'].title()
                        ), tags=(app['status'],))

                    # Status-based colors
                    tree.tag_configure('pending', foreground=get_status_color('pending'))
                    tree.tag_configure('approved', foreground=get_status_color('approved'))
                    tree.tag_configure('denied', foreground=get_status_color('denied'))
                else:
                    ttk.Label(parent, text=get_text("financial_aid.student_portal.no_scholarship_applications", "No scholarship applications found")).pack(expand=True)

        except Exception as e:
            logger.error(f"Error loading scholarship applications: {e}")
            ttk.Label(parent, text=get_text("financial_aid.student_portal.errors.loading_applications", "Error loading applications"), foreground='red').pack()

    def _show_aid_applications(self, parent):
        """Show financial aid applications in tab"""
        try:
            with get_connection() as conn:
                applications = conn.execute("""
                    SELECT * FROM student_financial_aid
                    WHERE student_id = ?
                    ORDER BY application_date DESC
                """, (self.student_id,)).fetchall()

                if applications:
                    columns = [get_text("financial_aid.student_portal.columns.aid_id", "Aid ID"),
                               get_text("financial_aid.student_portal.columns.type", "Type"),
                               get_text("financial_aid.student_portal.columns.awarded", "Awarded"),
                               get_text("financial_aid.student_portal.columns.disbursed", "Disbursed"),
                               get_text("financial_aid.student_portal.columns.status", "Status"),
                               get_text("financial_aid.student_portal.columns.applied", "Applied")]
                    tree = create_data_table(parent, columns, {
                        get_text("financial_aid.student_portal.columns.aid_id", "Aid ID"): 80,
                        get_text("financial_aid.student_portal.columns.type", "Type"): 150,
                        get_text("financial_aid.student_portal.columns.awarded", "Awarded"): 100,
                        get_text("financial_aid.student_portal.columns.disbursed", "Disbursed"): 100,
                        get_text("financial_aid.student_portal.columns.status", "Status"): 100,
                        get_text("financial_aid.student_portal.columns.applied", "Applied"): 120
                    })

                    for app in applications:
                        tree.insert('', 'end', values=(
                            app['aid_id'],
                            app.get('aid_type_id', 'N/A'),
                            format_currency(app.get('awarded_amount', 0)),
                            format_currency(app.get('disbursed_amount', 0)),
                            app['status'].title(),
                            format_date(app.get('application_date'))
                        ))
                else:
                    ttk.Label(parent, text=get_text("financial_aid.student_portal.no_aid_applications", "No financial aid applications found")).pack(expand=True)

        except Exception as e:
            logger.error(f"Error loading aid applications: {e}")
            ttk.Label(parent, text=get_text("financial_aid.student_portal.errors.loading_applications", "Error loading applications"), foreground='red').pack()
