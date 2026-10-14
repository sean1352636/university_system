"""Compatibility façade for the split implementation."""

from . import butcher_cli_shared as _shared
from .butcher_cli_shared import *  # noqa: F401,F403

from .butcher_cli_parts import print_header as _part_1
print_header = _part_1.print_header
_shared.print_header = print_header
_shared.__all__.append("print_header") if "print_header" not in _shared.__all__ else None

from .butcher_cli_parts import print_subheader as _part_2
print_subheader = _part_2.print_subheader
_shared.print_subheader = print_subheader
_shared.__all__.append("print_subheader") if "print_subheader" not in _shared.__all__ else None

from .butcher_cli_parts import get_current_user as _part_3
get_current_user = _part_3.get_current_user
_shared.get_current_user = get_current_user
_shared.__all__.append("get_current_user") if "get_current_user" not in _shared.__all__ else None

from .butcher_cli_parts import is_admin as _part_4
is_admin = _part_4.is_admin
_shared.is_admin = is_admin
_shared.__all__.append("is_admin") if "is_admin" not in _shared.__all__ else None

from .butcher_cli_parts import validate_positive_number as _part_5
validate_positive_number = _part_5.validate_positive_number
_shared.validate_positive_number = validate_positive_number
_shared.__all__.append("validate_positive_number") if "validate_positive_number" not in _shared.__all__ else None

from .butcher_cli_parts import format_currency as _part_6
format_currency = _part_6.format_currency
_shared.format_currency = format_currency
_shared.__all__.append("format_currency") if "format_currency" not in _shared.__all__ else None

from .butcher_cli_parts import format_date as _part_7
format_date = _part_7.format_date
_shared.format_date = format_date
_shared.__all__.append("format_date") if "format_date" not in _shared.__all__ else None

from .butcher_cli_parts import get_stock_status_icon as _part_8
get_stock_status_icon = _part_8.get_stock_status_icon
_shared.get_stock_status_icon = get_stock_status_icon
_shared.__all__.append("get_stock_status_icon") if "get_stock_status_icon" not in _shared.__all__ else None

from .butcher_cli_parts import browse_products_by_category as _part_9
browse_products_by_category = _part_9.browse_products_by_category
_shared.browse_products_by_category = browse_products_by_category
_shared.__all__.append("browse_products_by_category") if "browse_products_by_category" not in _shared.__all__ else None

from .butcher_cli_parts import view_product_details as _part_10
view_product_details = _part_10.view_product_details
_shared.view_product_details = view_product_details
_shared.__all__.append("view_product_details") if "view_product_details" not in _shared.__all__ else None

from .butcher_cli_parts import search_products as _part_11
search_products = _part_11.search_products
_shared.search_products = search_products
_shared.__all__.append("search_products") if "search_products" not in _shared.__all__ else None

from .butcher_cli_parts import add_product as _part_12
add_product = _part_12.add_product
_shared.add_product = add_product
_shared.__all__.append("add_product") if "add_product" not in _shared.__all__ else None

from .butcher_cli_parts import update_product as _part_13
update_product = _part_13.update_product
_shared.update_product = update_product
_shared.__all__.append("update_product") if "update_product" not in _shared.__all__ else None

from .butcher_cli_parts import convert_units as _part_14
convert_units = _part_14.convert_units
_shared.convert_units = convert_units
_shared.__all__.append("convert_units") if "convert_units" not in _shared.__all__ else None

from .butcher_cli_parts import place_order as _part_15
place_order = _part_15.place_order
_shared.place_order = place_order
_shared.__all__.append("place_order") if "place_order" not in _shared.__all__ else None

from .butcher_cli_parts import view_my_orders as _part_16
view_my_orders = _part_16.view_my_orders
_shared.view_my_orders = view_my_orders
_shared.__all__.append("view_my_orders") if "view_my_orders" not in _shared.__all__ else None

from .butcher_cli_parts import view_order_receipt as _part_17
view_order_receipt = _part_17.view_order_receipt
_shared.view_order_receipt = view_order_receipt
_shared.__all__.append("view_order_receipt") if "view_order_receipt" not in _shared.__all__ else None

from .butcher_cli_parts import cancel_order as _part_18
cancel_order = _part_18.cancel_order
_shared.cancel_order = cancel_order
_shared.__all__.append("cancel_order") if "cancel_order" not in _shared.__all__ else None

from .butcher_cli_parts import view_inventory as _part_19
view_inventory = _part_19.view_inventory
_shared.view_inventory = view_inventory
_shared.__all__.append("view_inventory") if "view_inventory" not in _shared.__all__ else None

from .butcher_cli_parts import adjust_inventory as _part_20
adjust_inventory = _part_20.adjust_inventory
_shared.adjust_inventory = adjust_inventory
_shared.__all__.append("adjust_inventory") if "adjust_inventory" not in _shared.__all__ else None

from .butcher_cli_parts import view_low_stock_alerts as _part_21
view_low_stock_alerts = _part_21.view_low_stock_alerts
_shared.view_low_stock_alerts = view_low_stock_alerts
_shared.__all__.append("view_low_stock_alerts") if "view_low_stock_alerts" not in _shared.__all__ else None

from .butcher_cli_parts import manage_expiry_dates as _part_22
manage_expiry_dates = _part_22.manage_expiry_dates
_shared.manage_expiry_dates = manage_expiry_dates
_shared.__all__.append("manage_expiry_dates") if "manage_expiry_dates" not in _shared.__all__ else None

from .butcher_cli_parts import add_expiry_batch as _part_23
add_expiry_batch = _part_23.add_expiry_batch
_shared.add_expiry_batch = add_expiry_batch
_shared.__all__.append("add_expiry_batch") if "add_expiry_batch" not in _shared.__all__ else None

from .butcher_cli_parts import view_expiring_products as _part_24
view_expiring_products = _part_24.view_expiring_products
_shared.view_expiring_products = view_expiring_products
_shared.__all__.append("view_expiring_products") if "view_expiring_products" not in _shared.__all__ else None

from .butcher_cli_parts import mark_batch_disposed as _part_25
mark_batch_disposed = _part_25.mark_batch_disposed
_shared.mark_batch_disposed = mark_batch_disposed
_shared.__all__.append("mark_batch_disposed") if "mark_batch_disposed" not in _shared.__all__ else None

from .butcher_cli_parts import sales_reports as _part_26
sales_reports = _part_26.sales_reports
_shared.sales_reports = sales_reports
_shared.__all__.append("sales_reports") if "sales_reports" not in _shared.__all__ else None

from .butcher_cli_parts import inventory_valuation_report as _part_27
inventory_valuation_report = _part_27.inventory_valuation_report
_shared.inventory_valuation_report = inventory_valuation_report
_shared.__all__.append("inventory_valuation_report") if "inventory_valuation_report" not in _shared.__all__ else None

from .butcher_cli_parts import popular_products_analysis as _part_28
popular_products_analysis = _part_28.popular_products_analysis
_shared.popular_products_analysis = popular_products_analysis
_shared.__all__.append("popular_products_analysis") if "popular_products_analysis" not in _shared.__all__ else None

from .butcher_cli_parts import customer_purchase_history as _part_29
customer_purchase_history = _part_29.customer_purchase_history
_shared.customer_purchase_history = customer_purchase_history
_shared.__all__.append("customer_purchase_history") if "customer_purchase_history" not in _shared.__all__ else None

from .butcher_cli_parts import view_all_orders as _part_30
view_all_orders = _part_30.view_all_orders
_shared.view_all_orders = view_all_orders
_shared.__all__.append("view_all_orders") if "view_all_orders" not in _shared.__all__ else None

from .butcher_cli_parts import update_order_status as _part_31
update_order_status = _part_31.update_order_status
_shared.update_order_status = update_order_status
_shared.__all__.append("update_order_status") if "update_order_status" not in _shared.__all__ else None

from .butcher_cli_parts import butcher_menu as _part_32
butcher_menu = _part_32.butcher_menu
_shared.butcher_menu = butcher_menu
_shared.__all__.append("butcher_menu") if "butcher_menu" not in _shared.__all__ else None

from .butcher_cli_parts import launch_butcher_cli as _part_33
launch_butcher_cli = _part_33.launch_butcher_cli
_shared.launch_butcher_cli = launch_butcher_cli
_shared.__all__.append("launch_butcher_cli") if "launch_butcher_cli" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['add_expiry_batch', 'add_product', 'adjust_inventory', 'browse_products_by_category', 'butcher_menu', 'cancel_order', 'convert_units', 'customer_purchase_history', 'format_currency', 'format_date', 'get_current_user', 'get_stock_status_icon', 'inventory_valuation_report', 'is_admin', 'launch_butcher_cli', 'manage_expiry_dates', 'mark_batch_disposed', 'place_order', 'popular_products_analysis', 'print_header', 'print_subheader', 'sales_reports', 'search_products', 'update_order_status', 'update_product', 'validate_positive_number', 'view_all_orders', 'view_expiring_products', 'view_inventory', 'view_low_stock_alerts', 'view_my_orders', 'view_order_receipt', 'view_product_details']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27, _part_28, _part_29, _part_30, _part_31, _part_32, _part_33]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27, _part_28, _part_29, _part_30, _part_31, _part_32, _part_33]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['add_expiry_batch', 'add_product', 'adjust_inventory', 'browse_products_by_category', 'butcher_menu', 'cancel_order', 'convert_units', 'customer_purchase_history', 'format_currency', 'format_date', 'get_current_user', 'get_stock_status_icon', 'inventory_valuation_report', 'is_admin', 'launch_butcher_cli', 'manage_expiry_dates', 'mark_batch_disposed', 'place_order', 'popular_products_analysis', 'print_header', 'print_subheader', 'sales_reports', 'search_products', 'update_order_status', 'update_product', 'validate_positive_number', 'view_all_orders', 'view_expiring_products', 'view_inventory', 'view_low_stock_alerts', 'view_my_orders', 'view_order_receipt', 'view_product_details']

if __name__ == "__main__":
    butcher_menu()
