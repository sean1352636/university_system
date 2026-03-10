"""Backwards-compatible alias for restaurant operations modules."""

from __future__ import annotations

# Re-export all public items from restaurant operations modules for backwards compatibility
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.audit import (
    log_audit_action,
    view_audit_logs,
    view_user_activity_logs,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.backup import (
    backup_database,
    backup_full_system,
    system_backup,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.connection import (
    get_db_connection,
    init_db,
    initialize_default_data,
    safe_db_operation,
    set_auth,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.restaurant_context import (
    DATABASE_FILE,
    analyze_query_performance,
    auth,
    backup_before_operation,
    configure_logging,
    database_optimization,
    display_auth_menu,
    display_backup_menu,
    display_main_menu,
    expense_analytics,
    export_expense_report,
    export_payroll_report,
    get_log_file,
    logger,
    log_path,
    manage_notifications,
    optimize_table_structure,
    send_confirmation_email,
    system_maintenance,
    user_management,
    view_audit_logs,
    view_user_activity_logs,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.exports import (
    export_expense_data,
    export_profit_loss_data,
    export_tax_data,
    generate_annual_tax_summary,
    generate_employee_tax_summary,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.financials import (
    add_expense,
    budget_management,
    budget_vs_actual,
    create_budget,
    expense_tracking,
    profit_loss_statement,
    update_budget,
    view_budgets,
    view_expenses,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.forecasting import (
    cash_flow_projection,
    expense_forecast,
    growth_projections,
    revenue_forecast,
    seasonal_analysis,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.maintenance import (
    clear_cache,
    clear_old_logs,
    database_cleanup,
    database_optimization,
    defragment_database,
    rebuild_indexes,
    reset_system_counters,
    system_health_check,
    system_maintenance,
    update_statistics,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.notifications import (
    clear_old_notifications,
    create_notification,
    manage_notifications,
    mark_notification_read,
    view_notifications,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.staff.payroll import (
    calculate_individual_payroll,
    calculate_monthly_payroll,
    calculate_weekly_payroll,
    payroll_calculations,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.settings import (
    display_system_settings,
    update_system_settings,
    view_system_settings,
)

# Note: cli.py and users.py from restaurant_misc are deprecated and not re-exported
# Use the main restaurant CLI and auth system instead

__all__ = [
    # audit
    "log_audit_action",
    "view_audit_logs",
    "view_user_activity_logs",
    # backup
    "backup_database",
    "backup_full_system",
    "system_backup",
    # connection
    "get_db_connection",
    "init_db",
    "initialize_default_data",
    "safe_db_operation",
    "set_auth",
    # context
    "DATABASE_FILE",
    "UserAuth",
    "analyze_query_performance",
    "auth",
    "backup_before_operation",
    "configure_logging",
    "database_optimization",
    "display_auth_menu",
    "display_backup_menu",
    "display_main_menu",
    "expense_analytics",
    "export_expense_report",
    "export_payroll_report",
    "get_log_file",
    "logger",
    "log_path",
    "manage_notifications",
    "optimize_table_structure",
    "send_confirmation_email",
    "system_maintenance",
    "user_management",
    "view_audit_logs",
    "view_user_activity_logs",
    # exports
    "export_expense_data",
    "export_profit_loss_data",
    "export_tax_data",
    "generate_annual_tax_summary",
    "generate_employee_tax_summary",
    # financials
    "add_expense",
    "budget_management",
    "budget_vs_actual",
    "create_budget",
    "expense_tracking",
    "profit_loss_statement",
    "update_budget",
    "view_budgets",
    "view_expenses",
    # forecasting
    "cash_flow_projection",
    "expense_forecast",
    "growth_projections",
    "revenue_forecast",
    "seasonal_analysis",
    # maintenance
    "clear_cache",
    "clear_old_logs",
    "database_cleanup",
    "database_optimization",
    "defragment_database",
    "rebuild_indexes",
    "reset_system_counters",
    "system_health_check",
    "system_maintenance",
    "update_statistics",
    # notifications
    "clear_old_notifications",
    "create_notification",
    "manage_notifications",
    "mark_notification_read",
    "view_notifications",
    # payroll
    "calculate_individual_payroll",
    "calculate_monthly_payroll",
    "calculate_weekly_payroll",
    "payroll_calculations",
    # settings
    "display_system_settings",
    "update_system_settings",
    "view_system_settings",
]
