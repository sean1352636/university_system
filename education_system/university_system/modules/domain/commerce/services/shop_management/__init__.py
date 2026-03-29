# shop_management package
# Split from the monolithic shop_management.py for maintainability.
# All public functions are re-exported here for backwards compatibility.

from education_system.university_system.modules.domain.commerce.services.shop_management.config import (
    auth,
    set_auth,
    format_currency,
    calculate_tax,
    get_system_settings,
    HAS_AUTH,
    # Re-export the logging decorators that were previously importable from this module
    log_activity,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_menu_navigation,
    log_dynamic_activity,
)

from education_system.university_system.modules.domain.commerce.services.shop_management.database import (
    init_shop_db,
    setup_shop_permissions,
)

from education_system.university_system.infrastructure.database.db import get_connection

from education_system.university_system.modules.domain.commerce.services.shop_management.menus import (
    display_shop_menu,
    display_product_management_menu,
    display_inventory_management_menu,
    display_discount_management_menu,
    display_sales_reports_menu,
    display_textbook_menu,
    display_main_menu_extended,
    add_shop_system_to_main_menu,
    setup_shop_system,
    integrate_shop_with_main,
)

from education_system.university_system.modules.domain.commerce.services.shop_management.shopping import (
    browse_products,
    add_to_shopping_cart,
    view_shopping_cart,
    checkout_process,
    view_purchase_history,
    view_all_transactions,
    validate_inventory_before_checkout,
)

from education_system.university_system.modules.domain.commerce.services.shop_management.products import (
    add_new_product,
    edit_product,
    toggle_product_status,
    view_all_products,
    search_products,
    get_popular_products,
    validate_product_data,
    quick_add_product,
    bulk_update_prices,
)

from education_system.university_system.modules.domain.commerce.services.shop_management.inventory import (
    update_stock_levels,
    restock_products,
    view_low_stock_products,
    adjust_restock_thresholds,
    get_low_stock_alert,
    send_low_stock_notification,
    get_inventory_valuation,
)

from education_system.university_system.modules.domain.commerce.services.shop_management.discounts import (
    create_discount,
    edit_discount,
    toggle_discount_status,
    view_all_discounts,
    calculate_discount_for_transaction,
    cleanup_expired_discounts,
)

from education_system.university_system.modules.domain.commerce.services.shop_management.reports import (
    generate_daily_sales_report,
    generate_weekly_sales_report,
    generate_monthly_sales_report,
    generate_product_sales_report,
    generate_category_sales_report,
    export_sales_data,
    get_sales_statistics,
    display_dashboard,
)

from education_system.university_system.modules.domain.commerce.services.shop_management.analytics import (
    get_customer_analytics,
    display_customer_analytics,
)

from education_system.university_system.modules.domain.commerce.services.shop_management.receipts import (
    generate_pdf_receipt,
    generate_barcode,
    print_product_labels,
)

from education_system.university_system.modules.domain.commerce.services.shop_management.utils import (
    log_shop_activity,
    get_transaction_summary,
    backup_shop_database,
    test_shop_system,
)
