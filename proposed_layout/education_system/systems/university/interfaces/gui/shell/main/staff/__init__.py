"""Staff CRUD Management Module"""

from education_system.systems.university.interfaces.gui.shell.main.staff.staff_crud_gui import (
    create_staff_dialog,
    update_staff_dialog,
    view_staff,
    delete_staff_dialog,
    search_staff_dialog
)

__all__ = [
    'create_staff_dialog',
    'update_staff_dialog',
    'view_staff',
    'delete_staff_dialog',
    'search_staff_dialog'
]
