"""
Awards mixin - viewing awarded scholarships and financial aid.
"""

from typing import Any, Dict

from education_system.systems.university.interfaces.gui.finance.financial_aid.common_imports import (
    ttk,
    logging,
    get_connection,
    clear_frame,
    create_data_table,
    format_currency,
    format_date,
    show_error,
)
from education_system.systems.university.infrastructure.i18n import get_text

logger = logging.getLogger(__name__)


class AwardsMixin:
    """Awards viewing functionality"""

    def show_my_awards(self):
        """Show student's awards"""
        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.student_portal.my_awards_title", "My Awards"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.student_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Summary stats
        stats_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.student_portal.award_summary", "Award Summary"), padding=10)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            stats = self._get_award_stats()

            summary_text = f"""
{get_text("financial_aid.student_portal.summary.total_awards", "Total Awards")}: {format_currency(stats['total_awarded'])}
{get_text("financial_aid.student_portal.summary.total_disbursed", "Total Disbursed")}: {format_currency(stats['total_disbursed'])}
{get_text("financial_aid.student_portal.summary.remaining", "Remaining")}: {format_currency(stats['remaining'])}
{get_text("financial_aid.student_portal.summary.active_awards", "Active Awards")}: {stats['active_count']}
            """
            ttk.Label(stats_frame, text=summary_text, font=('Arial', 10)).pack()

        except Exception as e:
            logger.error(f"Error loading award stats: {e}")
            ttk.Label(stats_frame, text=get_text("financial_aid.student_portal.errors.loading_statistics", "Error loading statistics"), foreground='red').pack()

        # Awards table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = [get_text("financial_aid.student_portal.columns.award_id", "Award ID"),
                   get_text("financial_aid.student_portal.columns.type", "Type"),
                   get_text("financial_aid.student_portal.columns.name", "Name"),
                   get_text("financial_aid.student_portal.columns.amount", "Amount"),
                   get_text("financial_aid.student_portal.columns.awarded_date", "Awarded Date"),
                   get_text("financial_aid.student_portal.columns.status", "Status")]
        tree = create_data_table(table_frame, columns, {
            get_text("financial_aid.student_portal.columns.award_id", "Award ID"): 80,
            get_text("financial_aid.student_portal.columns.type", "Type"): 100,
            get_text("financial_aid.student_portal.columns.name", "Name"): 200,
            get_text("financial_aid.student_portal.columns.amount", "Amount"): 100,
            get_text("financial_aid.student_portal.columns.awarded_date", "Awarded Date"): 120,
            get_text("financial_aid.student_portal.columns.status", "Status"): 100
        })

        self._load_student_awards(tree)

    def _get_award_stats(self) -> Dict[str, Any]:
        """Get award statistics"""
        stats = {
            'total_awarded': 0.0,
            'total_disbursed': 0.0,
            'remaining': 0.0,
            'active_count': 0
        }

        try:
            with get_connection() as conn:
                # Scholarship awards
                result = conn.execute("""
                    SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
                    FROM student_scholarships
                    WHERE student_id = ? AND status = 'awarded'
                """, (self.student_id,)).fetchone()
                stats['total_awarded'] = float(result['total']) if result else 0.0
                stats['active_count'] = result['count'] if result else 0

                # Disbursements
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

                stats['remaining'] = stats['total_awarded'] - stats['total_disbursed']

        except Exception as e:
            logger.error(f"Error fetching award stats: {e}")

        return stats

    def _load_student_awards(self, tree):
        """Load student awards into tree"""
        try:
            with get_connection() as conn:
                # Scholarship awards
                scholarships = conn.execute("""
                    SELECT ss.student_scholarship_id, 'Scholarship' as type,
                           s.scholarship_name as name, ss.amount, ss.awarded_date, ss.status
                    FROM student_scholarships ss
                    JOIN scholarships s ON ss.scholarship_id = s.scholarship_id
                    WHERE ss.student_id = ?
                    ORDER BY ss.awarded_date DESC
                """, (self.student_id,)).fetchall()

                for award in scholarships:
                    tree.insert('', 'end', values=(
                        award['student_scholarship_id'],
                        award['type'],
                        award['name'],
                        format_currency(award['amount']),
                        format_date(award['awarded_date']),
                        award['status'].title()
                    ))

                # Financial aid awards
                aid = conn.execute("""
                    SELECT sfa.aid_id, 'Financial Aid' as type,
                           fat.aid_name as name, sfa.awarded_amount, sfa.approval_date, sfa.status
                    FROM student_financial_aid sfa
                    LEFT JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE sfa.student_id = ? AND sfa.status = 'approved'
                    ORDER BY sfa.approval_date DESC
                """, (self.student_id,)).fetchall()

                for award in aid:
                    tree.insert('', 'end', values=(
                        award['aid_id'],
                        award['type'],
                        award['name'] or get_text("financial_aid.student_portal.general_aid", "General Aid"),
                        format_currency(award['awarded_amount']),
                        format_date(award['approval_date']),
                        award['status'].title()
                    ))

        except Exception as e:
            logger.error(f"Error loading awards: {e}")
            show_error(get_text("financial_aid.student_portal.errors.title", "Error"),
                      get_text("financial_aid.student_portal.errors.failed_load_awards", "Failed to load awards"))
