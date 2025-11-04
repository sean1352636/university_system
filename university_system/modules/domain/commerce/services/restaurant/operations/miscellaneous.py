"""Backwards-compatible alias for services.restaurant_misc."""

from __future__ import annotations

# Re-export all public items from restaurant_misc for backwards compatibility
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.core.services.restaurant_misc.audit import (
    log_audit_action,
    view_audit_logs,
    view_user_activity_logs,
)
from university_system.modules.core.services.restaurant_misc.backup import (
    backup_database,
    backup_full_system,
    system_backup,
)
from university_system.modules.core.services.restaurant_misc.cli import main
from university_system.modules.core.services.restaurant_misc.connection import (
    get_db_connection,
    init_db,
    initialize_default_data,
    safe_db_operation,
    set_auth,
)
from university_system.modules.core.services.restaurant_misc.restaurant_context import (
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
from university_system.modules.core.services.restaurant_misc.exports import (
    export_expense_data,
    export_profit_loss_data,
    export_tax_data,
    generate_annual_tax_summary,
    generate_employee_tax_summary,
)
from university_system.modules.core.services.restaurant_misc.financials import (
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
from university_system.modules.core.services.restaurant_misc.forecasting import (
    cash_flow_projection,
    expense_forecast,
    growth_projections,
    revenue_forecast,
    seasonal_analysis,
)
from university_system.modules.core.services.restaurant_misc.maintenance import (
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
from university_system.modules.core.services.restaurant_misc.notifications import (
    clear_old_notifications,
    create_notification,
    manage_notifications,
    mark_notification_read,
    view_notifications,
)
from university_system.modules.core.services.restaurant_misc.payroll import (
    calculate_individual_payroll,
    calculate_monthly_payroll,
    calculate_weekly_payroll,
    payroll_calculations,
)
from university_system.modules.core.services.restaurant_misc.settings import (
    display_system_settings,
    update_system_settings,
    view_system_settings,
)
from university_system.modules.core.services.restaurant_misc.users import user_management

__all__ = [
    # audit
    "log_audit_action",
    "view_audit_logs",
    "view_user_activity_logs",
    # backup
    "backup_database",
    "backup_full_system",
    "system_backup",
    # cli
    "main",
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
    # users
    "user_management",
]
