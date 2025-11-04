"""Convenience exports for restaurant operations helpers."""

from __future__ import annotations

from university_system.modules.core.services.restaurant_misc.connection import (
    get_db_connection,
    init_db,
    initialize_default_data,
    safe_db_operation,
    set_auth,
)
from university_system.modules.core.services.restaurant_misc.audit import log_audit_action, view_audit_logs, view_user_activity_logs
from university_system.modules.core.services.restaurant_misc.cli import main
from university_system.modules.core.services.restaurant_misc.payroll import (
    calculate_individual_payroll,
    calculate_monthly_payroll,
    calculate_weekly_payroll,
    payroll_calculations,
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
from university_system.modules.core.services.restaurant_misc.users import user_management
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
from university_system.modules.core.services.restaurant_misc.backup import backup_database, backup_full_system, system_backup
from university_system.modules.core.services.restaurant_misc.forecasting import (
    cash_flow_projection,
    expense_forecast,
    growth_projections,
    revenue_forecast,
    seasonal_analysis,
)
from university_system.modules.core.services.restaurant_misc.exports import (
    export_expense_data,
    export_profit_loss_data,
    export_tax_data,
    generate_annual_tax_summary,
    generate_employee_tax_summary,
)
from university_system.modules.core.services.restaurant_misc.settings import (
    display_system_settings,
    update_system_settings,
    view_system_settings,
)

# Import context module last to avoid circular imports
from university_system.modules.core.services.restaurant_misc import restaurant_context as context

__all__ = [
    "add_expense",
    "backup_database",
    "backup_full_system",
    "budget_management",
    "budget_vs_actual",
    "calculate_individual_payroll",
    "calculate_monthly_payroll",
    "calculate_weekly_payroll",
    "cash_flow_projection",
    "clear_cache",
    "clear_old_logs",
    "clear_old_notifications",
    "context",  # Export context for backward compatibility
    "create_budget",
    "create_notification",
    "database_cleanup",
    "database_optimization",
    "defragment_database",
    "display_system_settings",
    "export_expense_data",
    "export_profit_loss_data",
    "export_tax_data",
    "expense_forecast",
    "expense_tracking",
    "generate_annual_tax_summary",
    "generate_employee_tax_summary",
    "get_db_connection",
    "growth_projections",
    "init_db",
    "initialize_default_data",
    "log_audit_action",
    "main",
    "manage_notifications",
    "mark_notification_read",
    "payroll_calculations",
    "profit_loss_statement",
    "rebuild_indexes",
    "reset_system_counters",
    "revenue_forecast",
    "safe_db_operation",
    "seasonal_analysis",
    "set_auth",
    "system_backup",
    "system_health_check",
    "system_maintenance",
    "update_budget",
    "update_statistics",
    "update_system_settings",
    "user_management",
    "view_audit_logs",
    "view_budgets",
    "view_expenses",
    "view_notifications",
    "view_system_settings",
    "view_user_activity_logs",
]
