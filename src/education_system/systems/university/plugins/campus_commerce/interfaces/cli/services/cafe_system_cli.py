"""Backward-compatible façade for the modular café CLI."""

from functools import wraps

from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH
from education_system.systems.university.plugins.campus_commerce.domain import cafe as _base
from education_system.systems.university.plugins.campus_commerce.domain.cafe.integrations import user_context as _users
from education_system.systems.university.plugins.campus_commerce.domain.cafe.persistence import inventory_repository as _inventory
from education_system.systems.university.plugins.campus_commerce.domain.cafe.persistence import loyalty_repository as _loyalty
from education_system.systems.university.plugins.campus_commerce.domain.cafe.persistence import menu_repository as _menu
from education_system.systems.university.plugins.campus_commerce.domain.cafe.persistence import order_repository as _orders
from education_system.systems.university.plugins.campus_commerce.domain.cafe.persistence import reservation_repository as _reservations
from education_system.systems.university.plugins.campus_commerce.domain.cafe.persistence import schedule_repository as _schedules
from education_system.systems.university.plugins.campus_commerce.domain.cafe.persistence import schema as _schema
from education_system.systems.university.plugins.campus_commerce.domain.cafe.persistence import supplier_repository as _suppliers
from education_system.systems.university.plugins.campus_commerce.domain.cafe.services import checkout as _checkout
from education_system.systems.university.plugins.campus_commerce.domain.cafe.services import permissions as _permissions
from education_system.systems.university.plugins.campus_commerce.domain.cafe.services import reporting as _reporting
from .cafe import app as _app
from .cafe import context as _context
from .cafe.commands import inventory as _inventory_command
from .cafe.commands import loyalty as _loyalty_command
from .cafe.commands import menu_management as _menu_command
from .cafe.commands import order_history as _order_command
from .cafe.commands import point_of_sale as _pos_command
from .cafe.commands import reports as _reports_command
from .cafe.commands import reservations as _reservations_command
from .cafe.commands import staff_scheduling as _scheduling_command
from .cafe.commands import suppliers as _suppliers_command
from .cafe.commands import view_menu as _view_menu_command

CATEGORIES = _base.CATEGORIES
HAS_AUTH = _base.HAS_AUTH
FINANCE_ACCOUNT_AVAILABLE = _base.FINANCE_ACCOUNT_AVAILABLE
ACTIVITY_LOGGER_AVAILABLE = _base.ACTIVITY_LOGGER_AVAILABLE
auth = None

_COMPAT_MODULES = (
    _base, _schema, _menu, _orders, _inventory, _suppliers, _reservations,
    _loyalty, _schedules, _permissions, _reporting, _context, _app,
    _view_menu_command, _pos_command, _menu_command, _order_command,
    _inventory_command, _reports_command, _suppliers_command,
    _reservations_command, _loyalty_command, _scheduling_command,
)


def _sync_compatibility_state():
    """Propagate historically patchable façade settings to split modules."""
    for module in _COMPAT_MODULES:
        module.DEFAULT_DB_PATH = DEFAULT_DB_PATH
        module.FINANCE_ACCOUNT_AVAILABLE = FINANCE_ACCOUNT_AVAILABLE
        module.ACTIVITY_LOGGER_AVAILABLE = ACTIVITY_LOGGER_AVAILABLE
        module.auth = auth


def _compat(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        _sync_compatibility_state()
        return function(*args, **kwargs)
    return wrapper


def set_auth(auth_instance):
    """Set authentication state for every split CLI component."""
    global auth
    auth = auth_instance
    _sync_compatibility_state()
    _users.set_auth(auth_instance)


get_db_connection = _compat(_schema.get_db_connection)
init_cafe_db = _compat(_schema.init_cafe_db)
setup_cafe_permissions = _compat(_permissions.setup_cafe_permissions)

get_all_menu_items = _compat(_menu.get_all_menu_items)
get_menu_item = _compat(_menu.get_menu_item)
add_menu_item = _compat(_menu.add_menu_item)
update_menu_item = _compat(_menu.update_menu_item)
delete_menu_item = _compat(_menu.delete_menu_item)

create_order = _compat(_checkout.create_order)  # posts to Finance
get_orders = _compat(_orders.get_orders)
get_order_items = _compat(_orders.get_order_items)

update_stock = _compat(_inventory.update_stock)
get_inventory_transactions = _compat(_inventory.get_inventory_transactions)
get_sales_summary = _compat(_reporting.get_sales_summary)
get_popular_items = _compat(_reporting.get_popular_items)
get_low_stock_items = _compat(_reporting.get_low_stock_items)

add_supplier = _compat(_suppliers.add_supplier)
get_all_suppliers = _compat(_suppliers.get_all_suppliers)
get_supplier = _compat(_suppliers.get_supplier)
update_supplier = _compat(_suppliers.update_supplier)
delete_supplier = _compat(_suppliers.delete_supplier)
link_supplier_to_product = _compat(_suppliers.link_supplier_to_product)
get_supplier_products = _compat(_suppliers.get_supplier_products)

create_reservation = _compat(_reservations.create_reservation)
get_all_reservations = _compat(_reservations.get_all_reservations)
get_reservation = _compat(_reservations.get_reservation)
update_reservation_details = _compat(_reservations.update_reservation_details)
cancel_reservation = _compat(_reservations.cancel_reservation)

get_or_create_loyalty_account = _compat(_loyalty.get_or_create_loyalty_account)
get_loyalty_account = _compat(_loyalty.get_loyalty_account)
get_all_loyalty_accounts = _compat(_loyalty.get_all_loyalty_accounts)
add_loyalty_points = _compat(_loyalty.add_loyalty_points)
redeem_loyalty_points = _compat(_loyalty.redeem_loyalty_points)
get_loyalty_log = _compat(_loyalty.get_loyalty_log)

add_staff_schedule = _compat(_schedules.add_staff_schedule)
get_all_staff_schedules = _compat(_schedules.get_all_staff_schedules)
get_staff_schedule_by_name = _compat(_schedules.get_staff_schedule_by_name)
update_staff_schedule_entry = _compat(_schedules.update_staff_schedule_entry)
delete_staff_schedule_entry = _compat(_schedules.delete_staff_schedule_entry)
get_unique_staff_names = _compat(_schedules.get_unique_staff_names)

display_cafe_menu = _compat(_app.display_cafe_menu)
view_menu_cli = _compat(_view_menu_command.view_menu_cli)
point_of_sale_cli = _compat(_pos_command.point_of_sale_cli)
menu_management_cli = _compat(_menu_command.menu_management_cli)
order_history_cli = _compat(_order_command.order_history_cli)
inventory_management_cli = _compat(_inventory_command.inventory_management_cli)
reports_cli = _compat(_reports_command.reports_cli)
supplier_management_cli = _compat(_suppliers_command.supplier_management_cli)
reservations_cli = _compat(_reservations_command.reservations_cli)
loyalty_points_cli = _compat(_loyalty_command.loyalty_points_cli)
staff_scheduling_cli = _compat(_scheduling_command.staff_scheduling_cli)

__all__ = [name for name in globals() if not name.startswith("_")]
