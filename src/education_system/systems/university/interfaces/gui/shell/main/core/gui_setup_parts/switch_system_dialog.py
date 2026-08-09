"""Extracted function implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _switch_system_dialog(self):
    """Open the shared system-picker and, on selection, request a
    switch to the chosen system and tear the university GUI down.

    Hidden when the user isn't a superadmin (see ``create_header``).
    """
    try:
        from education_system import switch as _switch
        from education_system.launcher.system_switch import pick_system_gui
        target = pick_system_gui(
            self.root,
            getattr(self.auth, "current_user", None),
            "university",
        )
    except Exception:
        logger.exception("System-switch picker failed")
        return
    if not target:
        return
    if not messagebox.askyesno(
        _t('gui.shell.main.core.gui_setup_parts.switch_system_dialog.dialogs.switch_system', default="Switch System"),
        _t('gui.shell.main.core.gui_setup_parts.switch_system_dialog.dialogs.close_the_university_gui_and_open_the_selected_system', default="Close the University GUI and open the selected system?"),
        parent=self.root,
    ):
        return
    _switch.request_switch(target, "gui")
    try:
        self.root.destroy()
    except Exception:
        logger.exception("Failed to destroy root during system switch")
