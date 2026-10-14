"""Compatibility façade for the split implementation."""

from . import gui_setup_shared as _shared
from .gui_setup_shared import *  # noqa: F401,F403

from .gui_setup_parts import load_pinned as _part_1
_load_pinned = _part_1._load_pinned
_shared._load_pinned = _load_pinned
_shared.__all__.append("_load_pinned") if "_load_pinned" not in _shared.__all__ else None

from .gui_setup_parts import save_pinned as _part_2
_save_pinned = _part_2._save_pinned
_shared._save_pinned = _save_pinned
_shared.__all__.append("_save_pinned") if "_save_pinned" not in _shared.__all__ else None

from .gui_setup_parts import create_fallback_interface as _part_3
create_fallback_interface = _part_3.create_fallback_interface
_shared.create_fallback_interface = create_fallback_interface
_shared.__all__.append("create_fallback_interface") if "create_fallback_interface" not in _shared.__all__ else None

from .gui_setup_parts import init_gui_managers as _part_4
init_gui_managers = _part_4.init_gui_managers
_shared.init_gui_managers = init_gui_managers
_shared.__all__.append("init_gui_managers") if "init_gui_managers" not in _shared.__all__ else None

from .gui_setup_parts import create_themed_toplevel as _part_5
create_themed_toplevel = _part_5.create_themed_toplevel
_shared.create_themed_toplevel = create_themed_toplevel
_shared.__all__.append("create_themed_toplevel") if "create_themed_toplevel" not in _shared.__all__ else None

from .gui_setup_parts import setup_gui as _part_6
setup_gui = _part_6.setup_gui
_shared.setup_gui = setup_gui
_shared.__all__.append("setup_gui") if "setup_gui" not in _shared.__all__ else None

from .gui_setup_parts import switch_system_dialog as _part_7
_switch_system_dialog = _part_7._switch_system_dialog
_shared._switch_system_dialog = _switch_system_dialog
_shared.__all__.append("_switch_system_dialog") if "_switch_system_dialog" not in _shared.__all__ else None

from .gui_setup_parts import create_header as _part_8
create_header = _part_8.create_header
_shared.create_header = create_header
_shared.__all__.append("create_header") if "create_header" not in _shared.__all__ else None

from .gui_setup_parts import refresh_header_logo as _part_9
refresh_header_logo = _part_9.refresh_header_logo
_shared.refresh_header_logo = refresh_header_logo
_shared.__all__.append("refresh_header_logo") if "refresh_header_logo" not in _shared.__all__ else None

from .gui_setup_parts import create_status_bar as _part_10
create_status_bar = _part_10.create_status_bar
_shared.create_status_bar = create_status_bar
_shared.__all__.append("create_status_bar") if "create_status_bar" not in _shared.__all__ else None

from .gui_setup_parts import detect_system_name as _part_11
_detect_system_name = _part_11._detect_system_name
_shared._detect_system_name = _detect_system_name
_shared.__all__.append("_detect_system_name") if "_detect_system_name" not in _shared.__all__ else None

from .gui_setup_parts import detect_version as _part_12
_detect_version = _part_12._detect_version
_shared._detect_version = _detect_version
_shared.__all__.append("_detect_version") if "_detect_version" not in _shared.__all__ else None

from .gui_setup_parts import notification_user_id as _part_13
_notification_user_id = _part_13._notification_user_id
_shared._notification_user_id = _notification_user_id
_shared.__all__.append("_notification_user_id") if "_notification_user_id" not in _shared.__all__ else None

from .gui_setup_parts import get_unread_notification_count as _part_14
_get_unread_notification_count = _part_14._get_unread_notification_count
_shared._get_unread_notification_count = _get_unread_notification_count
_shared.__all__.append("_get_unread_notification_count") if "_get_unread_notification_count" not in _shared.__all__ else None

from .gui_setup_parts import refresh_notification_badge as _part_15
_refresh_notification_badge = _part_15._refresh_notification_badge
_shared._refresh_notification_badge = _refresh_notification_badge
_shared.__all__.append("_refresh_notification_badge") if "_refresh_notification_badge" not in _shared.__all__ else None

from .gui_setup_parts import open_notifications as _part_16
_open_notifications = _part_16._open_notifications
_shared._open_notifications = _open_notifications
_shared.__all__.append("_open_notifications") if "_open_notifications" not in _shared.__all__ else None

from .gui_setup_parts import update_clock as _part_17
_update_clock = _part_17._update_clock
_shared._update_clock = _update_clock
_shared.__all__.append("_update_clock") if "_update_clock" not in _shared.__all__ else None

from .gui_setup_parts import focus_nav_search as _part_18
_focus_nav_search = _part_18._focus_nav_search
_shared._focus_nav_search = _focus_nav_search
_shared.__all__.append("_focus_nav_search") if "_focus_nav_search" not in _shared.__all__ else None

from .gui_setup_parts import create_navigation_panel as _part_19
create_navigation_panel = _part_19.create_navigation_panel
_shared.create_navigation_panel = create_navigation_panel
_shared.__all__.append("create_navigation_panel") if "create_navigation_panel" not in _shared.__all__ else None

from .gui_setup_parts import rebuild_navigation_panel as _part_20
rebuild_navigation_panel = _part_20.rebuild_navigation_panel
_shared.rebuild_navigation_panel = rebuild_navigation_panel
_shared.__all__.append("rebuild_navigation_panel") if "rebuild_navigation_panel" not in _shared.__all__ else None

from .gui_setup_parts import create_content_area as _part_21
create_content_area = _part_21.create_content_area
_shared.create_content_area = create_content_area
_shared.__all__.append("create_content_area") if "create_content_area" not in _shared.__all__ else None

from .gui_setup_parts import get_visible_buttons_for_role as _part_22
get_visible_buttons_for_role = _part_22.get_visible_buttons_for_role
_shared.get_visible_buttons_for_role = get_visible_buttons_for_role
_shared.__all__.append("get_visible_buttons_for_role") if "get_visible_buttons_for_role" not in _shared.__all__ else None

from .gui_setup_parts import clear_content as _part_23
clear_content = _part_23.clear_content
_shared.clear_content = clear_content
_shared.__all__.append("clear_content") if "clear_content" not in _shared.__all__ else None

from .gui_setup_parts import open_in_workspace as _part_24
open_in_workspace = _part_24.open_in_workspace
_shared.open_in_workspace = open_in_workspace
_shared.__all__.append("open_in_workspace") if "open_in_workspace" not in _shared.__all__ else None

from .gui_setup_parts import show_welcome as _part_25
show_welcome = _part_25.show_welcome
_shared.show_welcome = show_welcome
_shared.__all__.append("show_welcome") if "show_welcome" not in _shared.__all__ else None

from .gui_setup_parts import show_main_interface as _part_26
show_main_interface = _part_26.show_main_interface
_shared.show_main_interface = show_main_interface
_shared.__all__.append("show_main_interface") if "show_main_interface" not in _shared.__all__ else None

from .gui_setup_parts import deferred_navigation_rebuild as _part_27
_deferred_navigation_rebuild = _part_27._deferred_navigation_rebuild
_shared._deferred_navigation_rebuild = _deferred_navigation_rebuild
_shared.__all__.append("_deferred_navigation_rebuild") if "_deferred_navigation_rebuild" not in _shared.__all__ else None

from .gui_setup_parts import update_status as _part_28
update_status = _part_28.update_status
_shared.update_status = update_status
_shared.__all__.append("update_status") if "update_status" not in _shared.__all__ else None

from .gui_setup_parts import restart_gui as _part_29
restart_gui = _part_29.restart_gui
_shared.restart_gui = restart_gui
_shared.__all__.append("restart_gui") if "restart_gui" not in _shared.__all__ else None

from .gui_setup_parts import cancel_timers as _part_30
_cancel_timers = _part_30._cancel_timers
_shared._cancel_timers = _cancel_timers
_shared.__all__.append("_cancel_timers") if "_cancel_timers" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['_cancel_timers', '_deferred_navigation_rebuild', '_detect_system_name', '_detect_version', '_focus_nav_search', '_get_unread_notification_count', '_load_pinned', '_notification_user_id', '_open_notifications', '_refresh_notification_badge', '_save_pinned', '_switch_system_dialog', '_update_clock', 'clear_content', 'create_content_area', 'create_fallback_interface', 'create_header', 'create_navigation_panel', 'create_status_bar', 'create_themed_toplevel', 'get_visible_buttons_for_role', 'init_gui_managers', 'open_in_workspace', 'rebuild_navigation_panel', 'refresh_header_logo', 'restart_gui', 'setup_gui', 'show_main_interface', 'show_welcome', 'update_status']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27, _part_28, _part_29, _part_30]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27, _part_28, _part_29, _part_30]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['_cancel_timers', '_deferred_navigation_rebuild', '_detect_system_name', '_detect_version', '_focus_nav_search', '_get_unread_notification_count', '_load_pinned', '_notification_user_id', '_open_notifications', '_refresh_notification_badge', '_save_pinned', '_switch_system_dialog', '_update_clock', 'clear_content', 'create_content_area', 'create_fallback_interface', 'create_header', 'create_navigation_panel', 'create_status_bar', 'create_themed_toplevel', 'get_visible_buttons_for_role', 'init_gui_managers', 'open_in_workspace', 'rebuild_navigation_panel', 'refresh_header_logo', 'restart_gui', 'setup_gui', 'show_main_interface', 'show_welcome', 'update_status']
