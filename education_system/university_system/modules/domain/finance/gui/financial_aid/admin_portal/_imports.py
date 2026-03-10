"""
Shared imports for admin portal submodules.

Re-exports everything needed by the admin portal mixin modules.
"""

from typing import Any, Dict

from ..common_imports import (
    tk,
    ttk,
    messagebox,
    filedialog,
    scrolledtext,
    logging,
    datetime,
    date,
    json,
    csv,
    get_connection,
    transaction,
    log_activity,
    get_auth,
    get_current_user,
    confirm_action,
    FinancialAidManager,
    clear_frame,
    create_data_table,
    create_stat_card,
    create_scrollable_frame,
    format_currency,
    format_date,
    show_error,
    show_success,
    show_warning,
    get_current_academic_year,
    get_academic_year_list,
    get_status_color,
    send_email,
    export_to_csv,
    COLORS,
)
from education_system.university_system.modules.shared.utils.i18n import get_text
from education_system.university_system.infrastructure.email.template_utils import render_template

logger = logging.getLogger(__name__)
