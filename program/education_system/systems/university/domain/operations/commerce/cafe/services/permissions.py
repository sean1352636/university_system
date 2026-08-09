from education_system.systems.university.domain.operations.commerce.cafe import *  # noqa: F401,F403
from education_system.systems.university.domain.operations.commerce.cafe.persistence.schema import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.menu_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.order_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.inventory_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.supplier_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.reservation_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.loyalty_repository import *
from education_system.systems.university.domain.operations.commerce.cafe.persistence.schedule_repository import *

def setup_cafe_permissions(auth_instance=None) -> None:
    """Setup permissions for the cafe module."""
    if auth_instance is None:
        auth_instance = auth or get_auth()

    if auth_instance is None:
        logger.warning("No auth instance available for setting up cafe permissions")
        return

    # Define cafe permissions
    permissions = [
        'view_cafe_menu',
        'add_cafe_item',
        'edit_cafe_item',
        'delete_cafe_item',
        'process_cafe_order',
        'view_cafe_orders',
        'manage_cafe_inventory',
        'view_cafe_reports',
        'manage_cafe',
    ]

    # Add permissions to roles
    try:
        if hasattr(auth_instance, 'add_permission_to_role'):
            # Admin gets all permissions
            for perm in permissions:
                try:
                    auth_instance.add_permission_to_role('admin', perm)
                except Exception:
                    pass

            # Staff gets most permissions
            staff_perms = [p for p in permissions if 'delete' not in p]
            for perm in staff_perms:
                try:
                    auth_instance.add_permission_to_role('staff', perm)
                except Exception:
                    pass

            # Students can view menu and place orders
            for perm in ['view_cafe_menu', 'process_cafe_order']:
                try:
                    auth_instance.add_permission_to_role('student', perm)
                    auth_instance.add_permission_to_role('instructor', perm)
                except Exception:
                    pass

            logger.info("Cafe permissions setup complete")
    except Exception as e:
        logger.warning(f"Could not setup cafe permissions: {e}")

