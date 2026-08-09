"""Notifications Hub module.

The Hub is now an **unread inbox** built on the shared unified-inbox panel
(University ``messages`` + cross-system messages). The legacy
``notifications`` table, its ``NotificationsService`` and the standalone
CLI have been retired; only the GUI window remains.
"""


__all__ = ["NotificationsGUI", "launch_notifications_gui"]

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "NotificationsGUI": "education_system.systems.university.interfaces.gui.operations.communications.notifications.notifications_gui",
    "launch_notifications_gui": "education_system.systems.university.interfaces.gui.operations.communications.notifications.notifications_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
