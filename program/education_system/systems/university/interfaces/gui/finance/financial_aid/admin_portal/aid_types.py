"""
Aid types display mixin for AdminPortal.
"""

from education_system.systems.university.interfaces.gui.finance.financial_aid.admin_portal._imports import (
    ttk, logging,
    get_connection,
    clear_frame, create_data_table,
    format_currency,
    get_text,
)

logger = logging.getLogger(__name__)


class AidTypesMixin:
    """Methods for displaying financial aid types."""

    def show_aid_types(self):
        """Show aid types management"""
        self._prepare_view_parent()

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.aid_types.title", "Manage Aid Types"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.admin_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Aid types table
        table_frame = ttk.Frame(self.parent_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = [get_text("financial_aid.admin_portal.columns.aid_type_id", "Aid Type ID"), get_text("financial_aid.admin_portal.columns.name", "Name"), get_text("financial_aid.admin_portal.columns.category", "Category"), get_text("financial_aid.admin_portal.columns.max_amount", "Max Amount"), get_text("financial_aid.admin_portal.columns.renewable", "Renewable"), get_text("financial_aid.admin_portal.columns.requires_repayment", "Requires Repayment")]
        tree = create_data_table(table_frame, columns, {
            get_text("financial_aid.admin_portal.columns.aid_type_id", "Aid Type ID"): 100, get_text("financial_aid.admin_portal.columns.name", "Name"): 200, get_text("financial_aid.admin_portal.columns.category", "Category"): 120, get_text("financial_aid.admin_portal.columns.max_amount", "Max Amount"): 100, get_text("financial_aid.admin_portal.columns.renewable", "Renewable"): 100, get_text("financial_aid.admin_portal.columns.requires_repayment", "Requires Repayment"): 150
        })

        try:
            with get_connection() as conn:
                aid_types = conn.execute("""
                    SELECT * FROM financial_aid_types
                    ORDER BY aid_category, aid_name
                """).fetchall()

                for aid_type in aid_types:
                    # Convert Row to dict for safe .get() usage
                    aid_dict = dict(aid_type)
                    tree.insert('', 'end', values=(
                        aid_dict['aid_type_id'],
                        aid_dict['aid_name'],
                        aid_dict.get('aid_category', 'N/A'),
                        format_currency(aid_dict.get('max_amount', 0)),
                        get_text("financial_aid.admin_portal.values.yes", "Yes") if aid_dict.get('is_renewable') else get_text("financial_aid.admin_portal.values.no", "No"),
                        get_text("financial_aid.admin_portal.values.yes", "Yes") if aid_dict.get('requires_repayment') else get_text("financial_aid.admin_portal.values.no", "No")
                    ))

        except Exception as e:
            logger.error(f"Error loading aid types: {e}")
            ttk.Label(table_frame, text=get_text("financial_aid.admin_portal.errors.error_loading_aid_types", "Error loading aid types"), foreground='red').pack()
