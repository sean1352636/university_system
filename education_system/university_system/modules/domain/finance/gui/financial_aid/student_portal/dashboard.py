"""
Dashboard mixin - main dashboard view and student statistics.
"""

from typing import Any, Dict

from education_system.university_system.modules.domain.finance.gui.financial_aid.common_imports import (
    ttk,
    logging,
    get_connection,
    clear_frame,
    create_data_table,
    create_stat_card,
    format_currency,
    format_date,
    get_status_color,
)
from education_system.university_system.modules.shared.utils.i18n import get_text

logger = logging.getLogger(__name__)


class DashboardMixin:
    """Dashboard display and student statistics"""

    def show_dashboard(self):
        """Display student dashboard"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.dashboard_title", "My Financial Aid Dashboard"), style='Title.TLabel').pack(anchor='w')

        # Statistics cards
        stats_frame = ttk.Frame(self.parent_frame)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            # Get student statistics
            stats = self._get_student_stats()

            # Create stat cards
            cards = [
                (get_text("financial_aid.student_portal.stats.total_awards", "Total Awards"), format_currency(stats['total_awards']), 'success'),
                (get_text("financial_aid.student_portal.stats.pending_applications", "Pending Applications"), str(stats['pending_apps']), 'warning'),
                (get_text("financial_aid.student_portal.stats.available_scholarships", "Available Scholarships"), str(stats['available_scholarships']), 'info'),
                (get_text("financial_aid.student_portal.stats.total_disbursed", "Total Disbursed"), format_currency(stats['total_disbursed']), 'primary')
            ]

            for i, (title, value, color) in enumerate(cards):
                card = create_stat_card(stats_frame, title, value, color)
                card.grid(row=0, column=i, padx=10, pady=5, sticky='ew')
                stats_frame.grid_columnconfigure(i, weight=1)

        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            ttk.Label(stats_frame, text=get_text("financial_aid.student_portal.errors.loading_statistics", "Error loading statistics"), foreground='red').pack()

        # Quick actions
        actions_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.student_portal.quick_actions", "Quick Actions"), padding=10)
        actions_frame.pack(fill='x', padx=10, pady=10)

        actions = [
            (get_text("financial_aid.student_portal.actions.browse_scholarships", "Browse Scholarships"), self.show_scholarships),
            (get_text("financial_aid.student_portal.actions.recommendations", "Recommendations"), self.show_recommendations),
            (get_text("financial_aid.student_portal.actions.my_applications", "My Applications"), self.show_my_applications),
            (get_text("financial_aid.student_portal.actions.deadlines", "Deadlines"), self.show_deadlines),
            (get_text("financial_aid.student_portal.actions.documents", "Documents"), self.show_documents),
            (get_text("financial_aid.student_portal.actions.profile", "My Profile"), self.show_profile),
            (get_text("financial_aid.student_portal.actions.apply_financial_aid", "Apply for Financial Aid"), self.show_apply_aid),
            (get_text("financial_aid.student_portal.actions.my_awards", "My Awards"), self.show_my_awards)
        ]

        for i, (text, command) in enumerate(actions):
            ttk.Button(actions_frame, text=text, command=command, width=20).grid(
                row=0, column=i, padx=5, pady=5, sticky='ew')
            actions_frame.grid_columnconfigure(i, weight=1)

        # Recent activity
        self._show_recent_activity()

    def _get_student_stats(self) -> Dict[str, Any]:
        """Get student statistics"""
        stats = {
            'total_awards': 0.0,
            'pending_apps': 0,
            'available_scholarships': 0,
            'total_disbursed': 0.0
        }

        try:
            with get_connection() as conn:
                # Total awards
                result = conn.execute("""
                    SELECT COALESCE(SUM(amount), 0) as total
                    FROM student_scholarships
                    WHERE student_id = ? AND status = 'awarded'
                """, (self.student_id,)).fetchone()
                stats['total_awards'] = float(result['total']) if result else 0.0

                # Pending applications
                result = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM scholarship_applications
                    WHERE student_id = ? AND status = 'pending'
                """, (self.student_id,)).fetchone()
                stats['pending_apps'] = result['count'] if result else 0

                # Available scholarships
                result = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM scholarships
                    WHERE is_active = 1 AND deadline >= date('now')
                """).fetchone()
                stats['available_scholarships'] = result['count'] if result else 0

                # Total disbursed
                try:
                    result = conn.execute("""
                        SELECT COALESCE(SUM(d.amount), 0) as total
                        FROM disbursements d
                        WHERE d.student_id = ? AND d.status = 'disbursed'
                    """, (self.student_id,)).fetchone()
                    stats['total_disbursed'] = float(result['total']) if result else 0.0
                except Exception:
                    # Disbursements table may not exist yet
                    stats['total_disbursed'] = 0.0

        except Exception as e:
            logger.error(f"Error fetching stats: {e}")

        return stats

    def _show_recent_activity(self):
        """Show recent activity section"""
        activity_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.student_portal.recent_activity", "Recent Activity"), padding=10)
        activity_frame.pack(fill='both', expand=True, padx=10, pady=10)

        try:
            with get_connection() as conn:
                # Get recent applications and awards
                activities = conn.execute("""
                    SELECT 'application' as type, sa.application_id as id,
                           s.scholarship_name as name, sa.application_date as date, sa.status
                    FROM scholarship_applications sa
                    JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                    WHERE sa.student_id = ?
                    UNION ALL
                    SELECT 'award' as type, ss.student_scholarship_id as id,
                           s.scholarship_name as name, ss.awarded_date as date, ss.status
                    FROM student_scholarships ss
                    JOIN scholarships s ON ss.scholarship_id = s.scholarship_id
                    WHERE ss.student_id = ?
                    ORDER BY date DESC
                    LIMIT 10
                """, (self.student_id, self.student_id)).fetchall()

                if activities:
                    tree = create_data_table(activity_frame,
                                           [get_text("financial_aid.student_portal.columns.type", "Type"),
                                            get_text("financial_aid.student_portal.columns.name", "Name"),
                                            get_text("financial_aid.student_portal.columns.date", "Date"),
                                            get_text("financial_aid.student_portal.columns.status", "Status")],
                                           {get_text("financial_aid.student_portal.columns.type", "Type"): 100,
                                            get_text("financial_aid.student_portal.columns.name", "Name"): 300,
                                            get_text("financial_aid.student_portal.columns.date", "Date"): 120,
                                            get_text("financial_aid.student_portal.columns.status", "Status"): 100})

                    for activity in activities:
                        tree.insert('', 'end', values=(
                            activity['type'].title(),
                            activity['name'],
                            format_date(activity['date']),
                            activity['status'].title()
                        ))
                else:
                    ttk.Label(activity_frame, text=get_text("financial_aid.student_portal.no_recent_activity", "No recent activity")).pack()

        except Exception as e:
            logger.error(f"Error loading activity: {e}")
            ttk.Label(activity_frame, text=get_text("financial_aid.student_portal.errors.loading_recent_activity", "Error loading recent activity"), foreground='red').pack()
