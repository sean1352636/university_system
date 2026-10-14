"""Dependencies shared by the POS controller, panels and dialogs."""
from education_system.systems.university.plugins.campus_commerce.domain.bakery_shop._common import *  # noqa: F401,F403

class POSContext:
    """Explicit host dependency contract used by POSTabMixin."""
    required_attributes = ("root", "pos_tab", "colors", "products")
    required_methods = ("_connect", "_lazy_subnotebook")

__all__ = [name for name in globals() if not name.startswith("__")]
