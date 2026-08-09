"""Compatibility façade for the split implementation."""

from . import finance_shared as _shared
from .finance_shared import *  # noqa: F401,F403

from .finance_parts import open_library_finance as _part_1
open_library_finance = _part_1.open_library_finance
_shared.open_library_finance = open_library_finance
_shared.__all__.append("open_library_finance") if "open_library_finance" not in _shared.__all__ else None

from .finance_parts import libraryfinancemanager_init as _part_2_1
from .finance_parts import libraryfinancemanager_create_overview_section as _part_2_2
from .finance_parts import libraryfinancemanager_process_payment_dialog as _part_2_3
from .finance_parts import libraryfinancemanager_process_library_refund as _part_2_4
from .finance_parts import libraryfinancemanager_add_book_cost_dialog as _part_2_5
class LibraryFinanceManager(_part_2_1.LibraryFinanceManager, _part_2_2.LibraryFinanceManager, _part_2_3.LibraryFinanceManager, _part_2_4.LibraryFinanceManager, _part_2_5.LibraryFinanceManager):
    """Manages all library-related financial operations - integrated into Library GUI"""
_shared.LibraryFinanceManager = LibraryFinanceManager
_shared.__all__.append("LibraryFinanceManager") if "LibraryFinanceManager" not in _shared.__all__ else None

from .finance_parts import get_library_settings as _part_3
get_library_settings = _part_3.get_library_settings
_shared.get_library_settings = get_library_settings
_shared.__all__.append("get_library_settings") if "get_library_settings" not in _shared.__all__ else None

from .finance_parts import update_library_setting as _part_4
update_library_setting = _part_4.update_library_setting
_shared.update_library_setting = update_library_setting
_shared.__all__.append("update_library_setting") if "update_library_setting" not in _shared.__all__ else None

from .finance_parts import set_auth as _part_5
set_auth = _part_5.set_auth
_shared.set_auth = set_auth
_shared.__all__.append("set_auth") if "set_auth" not in _shared.__all__ else None

from .finance_parts import get_current_user_id as _part_6
get_current_user_id = _part_6.get_current_user_id
_shared.get_current_user_id = get_current_user_id
_shared.__all__.append("get_current_user_id") if "get_current_user_id" not in _shared.__all__ else None

from .finance_parts import log_audit_event as _part_7
log_audit_event = _part_7.log_audit_event
_shared.log_audit_event = log_audit_event
_shared.__all__.append("log_audit_event") if "log_audit_event" not in _shared.__all__ else None

from .finance_parts import process_scanned_barcode as _part_8
process_scanned_barcode = _part_8.process_scanned_barcode
_shared.process_scanned_barcode = process_scanned_barcode
_shared.__all__.append("process_scanned_barcode") if "process_scanned_barcode" not in _shared.__all__ else None

from .finance_parts import get_db_connection as _part_9
get_db_connection = _part_9.get_db_connection
_shared.get_db_connection = get_db_connection
_shared.__all__.append("get_db_connection") if "get_db_connection" not in _shared.__all__ else None

from .finance_parts import start_gui_library_system as _part_10
start_gui_library_system = _part_10.start_gui_library_system
_shared.start_gui_library_system = start_gui_library_system
_shared.__all__.append("start_gui_library_system") if "start_gui_library_system" not in _shared.__all__ else None

from .finance_parts import setup_keyboard_shortcuts as _part_11
setup_keyboard_shortcuts = _part_11.setup_keyboard_shortcuts
_shared.setup_keyboard_shortcuts = setup_keyboard_shortcuts
_shared.__all__.append("setup_keyboard_shortcuts") if "setup_keyboard_shortcuts" not in _shared.__all__ else None

from .finance_parts import display_library_menu_gui as _part_12
display_library_menu_gui = _part_12.display_library_menu_gui
_shared.display_library_menu_gui = display_library_menu_gui
_shared.__all__.append("display_library_menu_gui") if "display_library_menu_gui" not in _shared.__all__ else None

from .finance_parts import run_library_gui as _part_13
run_library_gui = _part_13.run_library_gui
_shared.run_library_gui = run_library_gui
_shared.__all__.append("run_library_gui") if "run_library_gui" not in _shared.__all__ else None

from .finance_parts import run_library_system_with_gui_option as _part_14
run_library_system_with_gui_option = _part_14.run_library_system_with_gui_option
_shared.run_library_system_with_gui_option = run_library_system_with_gui_option
_shared.__all__.append("run_library_system_with_gui_option") if "run_library_system_with_gui_option" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['LibraryFinanceManager', 'display_library_menu_gui', 'get_current_user_id', 'get_db_connection', 'get_library_settings', 'log_audit_event', 'open_library_finance', 'process_scanned_barcode', 'run_library_gui', 'run_library_system_with_gui_option', 'set_auth', 'setup_keyboard_shortcuts', 'start_gui_library_system', 'update_library_setting']}
for _module in [_part_1, _part_2_1, _part_2_2, _part_2_3, _part_2_4, _part_2_5, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2_1, _part_2_2, _part_2_3, _part_2_4, _part_2_5, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['LibraryFinanceManager', 'display_library_menu_gui', 'get_current_user_id', 'get_db_connection', 'get_library_settings', 'log_audit_event', 'open_library_finance', 'process_scanned_barcode', 'run_library_gui', 'run_library_system_with_gui_option', 'set_auth', 'setup_keyboard_shortcuts', 'start_gui_library_system', 'update_library_setting']
