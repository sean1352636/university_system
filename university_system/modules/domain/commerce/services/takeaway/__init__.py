"""
Takeaway System Module
Campus food ordering and delivery service
"""

from university_system.modules.domain.commerce.services.takeaway.takeaway_service import (
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
