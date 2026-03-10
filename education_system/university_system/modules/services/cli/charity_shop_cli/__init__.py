"""
Charity Shop Stock Management CLI
A command-line interface for managing charity shop inventory.
Features: Stock tracking, sold status, revenue calculation, and reporting.

Integrated with the University Management System.
"""

from ._imports import set_auth
from .db import init_charity_shop_db, setup_charity_shop_permissions
from .inventory import (
    get_all_stock, search_stock, add_item, update_item,
    mark_as_sold, mark_as_available, delete_item,
    get_stock_summary, get_revenue_summary, get_revenue_by_category, get_stock_by_category,
    bulk_import_items, bulk_export_items,
    adjust_stock_quantity, set_low_stock_alert, view_low_stock_items,
    merge_duplicate_items,
)
from .archive import (
    archive_old_items, restore_archived_items, get_archived_items,
    transfer_between_locations, get_all_locations, add_location,
)
from .pricing import (
    barcode_scanner_integration, set_item_barcode,
    apply_discount, create_sale_bundle, get_bundles,
    price_history_tracker, dynamic_pricing_suggestions,
)
from .promotions import (
    create_promotional_event, get_active_promotions, process_refund,
    layaway_system, get_layaways, gift_card_management, loyalty_points_system,
)
from .reporting import (
    calculate_profit_margin,
    generate_daily_sales_report, generate_weekly_sales_report, generate_monthly_sales_report,
    best_selling_items_report, slow_moving_items_report,
    revenue_trend_analysis, category_performance_comparison, seasonal_trends_report,
    donor_contribution_report, tax_deduction_report,
)
from .customers import (
    register_customer, get_customer, customer_purchase_history,
    customer_wishlist, send_customer_notifications,
    customer_feedback_system, vip_customer_management,
    customer_birthday_discounts, customer_referral_program,
)
from .donations import (
    record_donation, generate_donation_receipt, donor_database,
    donation_value_estimator, donation_drive_tracker, thank_you_letter_generator,
)
from .staff import (
    register_staff, get_all_staff,
    staff_performance_tracker, shift_scheduling,
    task_assignment_system, volunteer_hours_tracker,
    opening_closing_checklist, cash_register_reconciliation,
)
from .menus import (
    display_charity_shop_menu,
    inventory_management_cli, sales_pricing_cli,
    customer_management_cli, donation_management_cli, staff_operations_cli,
)

__all__ = [
    'display_charity_shop_menu',
    'init_charity_shop_db',
    'setup_charity_shop_permissions',
    'set_auth',
    # Menu functions
    'inventory_management_cli',
    'sales_pricing_cli',
    'customer_management_cli',
    'donation_management_cli',
    'staff_operations_cli',
    # Inventory
    'get_all_stock', 'search_stock', 'add_item', 'update_item',
    'mark_as_sold', 'mark_as_available', 'delete_item',
    'get_stock_summary', 'get_revenue_summary', 'get_revenue_by_category', 'get_stock_by_category',
    'bulk_import_items', 'bulk_export_items',
    'adjust_stock_quantity', 'set_low_stock_alert', 'view_low_stock_items',
    'merge_duplicate_items',
    # Archive & locations
    'archive_old_items', 'restore_archived_items', 'get_archived_items',
    'transfer_between_locations', 'get_all_locations', 'add_location',
    # Pricing
    'barcode_scanner_integration', 'set_item_barcode',
    'apply_discount', 'create_sale_bundle', 'get_bundles',
    'price_history_tracker', 'dynamic_pricing_suggestions',
    # Promotions
    'create_promotional_event', 'get_active_promotions', 'process_refund',
    'layaway_system', 'get_layaways', 'gift_card_management', 'loyalty_points_system',
    # Reporting
    'calculate_profit_margin',
    'generate_daily_sales_report', 'generate_weekly_sales_report', 'generate_monthly_sales_report',
    'best_selling_items_report', 'slow_moving_items_report',
    'revenue_trend_analysis', 'category_performance_comparison', 'seasonal_trends_report',
    'donor_contribution_report', 'tax_deduction_report',
    # Customers
    'register_customer', 'get_customer', 'customer_purchase_history',
    'customer_wishlist', 'send_customer_notifications',
    'customer_feedback_system', 'vip_customer_management',
    'customer_birthday_discounts', 'customer_referral_program',
    # Donations
    'record_donation', 'generate_donation_receipt', 'donor_database',
    'donation_value_estimator', 'donation_drive_tracker', 'thank_you_letter_generator',
    # Staff
    'register_staff', 'get_all_staff',
    'staff_performance_tracker', 'shift_scheduling',
    'task_assignment_system', 'volunteer_hours_tracker',
    'opening_closing_checklist', 'cash_register_reconciliation',
]
