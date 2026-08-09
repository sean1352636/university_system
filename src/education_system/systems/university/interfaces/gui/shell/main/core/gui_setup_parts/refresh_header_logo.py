"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def refresh_header_logo(self):
    """Reload the header's institution logo from the branding settings.

    Safe to call any time after ``create_header``; a no-op if the header
    has not been built yet. Call after an admin saves branding so the
    change lands without a restart.
    """
    label = getattr(self, '_header_logo_label', None)
    if label is None:
        return
    try:
        from education_system.systems.university.interfaces.gui.shell.admin.branding_config_gui import (
            load_logo_image,
        )
        # Held on self so Tk does not garbage-collect the image.
        # 24px rendered a wordmark logo too small to read (a 246x95 logo
        # scaled to 62x24). 40 keeps the header a single button-height row
        # while leaving the text legible.
        self._header_logo_image = load_logo_image(max_height=40)
        label.configure(image=self._header_logo_image or '')
    except Exception:
        logger.debug("Could not load institution logo for header", exc_info=True)
