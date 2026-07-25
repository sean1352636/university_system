"""
Takeaway System Module
Campus food ordering and delivery service
"""

from education_system.systems.university.domain.operations.commerce.services.takeaway.takeaway_service import (
    init_takeaway_db,
    setup_takeaway_permissions,
    display_takeaway_menu,
    set_auth,
)

__all__ = [
    'init_takeaway_db',
    'setup_takeaway_permissions',
    'display_takeaway_menu',
    'set_auth',
]
