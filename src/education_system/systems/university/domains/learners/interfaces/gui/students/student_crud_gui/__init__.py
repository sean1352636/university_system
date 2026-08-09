# Package split from the original student_crud_gui.py.
# Re-exports preserve the public import path used by main_gui.py.

from .create import create_student_dialog
from .update import update_student_dialog
from .delete import delete_student_dialog, select_student_for_deletion
from .grades import manage_student_grades
from .attendance import view_student_attendance
from .timetable import view_student_timetable
from .modules_reassign import reassign_modules

from .importers import _open_sixth_form_import_dialog, _open_bulk_csv_import_dialog
from .widgets import _DOBPicker, _safe_set_combobox, _safe_entry_insert
from .sync.visa import _create_visa_record_for_new_student
from .sync.atas import _resync_atas_after_module_change
from .sync.auth import _ensure_shared_auth_user, _purge_user_from_all_chat_rooms
from .sync.chat_rooms import (
    _auto_join_module_chat_rooms,
    _resolve_module_name,
    _sync_module_chat_rooms,
)

__all__ = [
    "create_student_dialog",
    "update_student_dialog",
    "delete_student_dialog",
    "select_student_for_deletion",
    "manage_student_grades",
    "view_student_attendance",
    "view_student_timetable",
    "reassign_modules",
]
